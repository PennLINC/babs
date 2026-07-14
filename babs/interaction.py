"""This is the main module."""

import json
import os.path as op
import sys
import time

import datalad.api as dlapi
import numpy as np

from babs.base import BABS
from babs.scheduler import (
    report_job_status,
    submit_array,
)
from babs.status import job_status_counts
from babs.utils import (
    update_submitted_job_ids,
)


class BABSInteraction(BABS):
    """Implement interactions with a BABS project - submitting jobs and checking status."""

    def ensure_container_images_available(self) -> None:
        """Retrieve configured container image contents before submitting jobs."""
        containers_path = op.join(self.analysis_path, 'containers')
        if not op.exists(op.join(containers_path, '.datalad', 'config')):
            raise FileNotFoundError(
                'There is no containers DataLad dataset in folder: ' + containers_path
            )

        print('\nEnsuring container image(s) are available locally...')
        for image_path in self.container_images:
            if op.isabs(image_path):
                image_path_abs = image_path
            else:
                image_path_abs = op.join(self.analysis_path, image_path)

            if op.exists(image_path_abs):
                print(f'Container image already available: {image_path}')
                continue

            print(f'Running `datalad get {image_path}`...')
            statuses = dlapi.get(path=image_path_abs, dataset=containers_path)
            if isinstance(statuses, dict):
                statuses = [statuses]
            elif statuses is None:
                statuses = []

            failed_statuses = [
                status for status in statuses if status.get('status') not in {'ok', 'notneeded'}
            ]
            if failed_statuses:
                raise RuntimeError(
                    'Unable to retrieve container image before job submission: '
                    f'{image_path}\nDataLad status: {failed_statuses}'
                )

            if not op.exists(image_path_abs):
                raise FileNotFoundError(
                    'Container image is still not available after `datalad get`: ' + image_path_abs
                )

    def babs_submit(self, count=None, submit_df=None, skip_failed=False, skip_running_jobs=False):
        """
        This function submits jobs that don't have results yet and prints out job status.

        Parameters
        ----------
        count: int or None
            number of jobs to be submitted
            default: 1
            negative value: to submit all jobs
        submit_df: pd.DataFrame
            dataframe of jobs to be submitted
            default: None
        skip_running_jobs: bool
            whether to allow submission when there are running/pending jobs
        """

        self.ensure_shared_group_runtime_ready()

        # Check if there are still jobs running
        currently_running_df = self.get_currently_running_jobs_df()
        running_pending_df = currently_running_df.copy()
        if currently_running_df.shape[0] > 0:
            non_cg_states = (
                currently_running_df['state'].fillna('').ne('CG')
                if 'state' in currently_running_df
                else np.array([True] * currently_running_df.shape[0])
            )
            if non_cg_states.any():
                if not skip_running_jobs:
                    raise Exception(
                        'There are still jobs running. '
                        'Please wait for them to finish or cancel them. '
                        'Current running jobs:\n'
                        f'{currently_running_df}'
                    )
                if 'state' in currently_running_df:
                    running_pending_df = currently_running_df[
                        currently_running_df['state'].isin(['PD', 'R'])
                    ]
            else:
                running_pending_df = currently_running_df.iloc[0:0]
                print('All currently running jobs are in CG state; proceeding with submission.')

        # Find the rows that don't have results yet
        status_df = self.get_job_status_df()
        df_needs_submit = status_df[~status_df['has_results']].reset_index(drop=True)
        if skip_failed:
            df_needs_submit = df_needs_submit[~df_needs_submit['submitted']]

        if submit_df is not None:
            df_needs_submit = submit_df

        if skip_running_jobs and not running_pending_df.empty:
            # Build (sub_id,) or (sub_id, ses_id) keys for set lookup
            if self.processing_level == 'session':
                running_keys = set(
                    zip(
                        running_pending_df['sub_id'],
                        running_pending_df['ses_id'],
                        strict=False,
                    )
                )
                submit_keys = list(
                    zip(df_needs_submit['sub_id'], df_needs_submit['ses_id'], strict=False)
                )
            else:
                running_keys = set(running_pending_df['sub_id'].tolist())
                submit_keys = df_needs_submit['sub_id'].tolist()

            # Mark which of the to-submit rows are still running/pending
            if running_keys:
                skip_mask = [key in running_keys for key in submit_keys]
            else:
                skip_mask = [False] * len(submit_keys)

            if any(skip_mask):
                # Report skipped job IDs and filter them out of the submission list
                skip_job_ids = sorted(running_pending_df['job_id'].dropna().unique().tolist())
                print(
                    'Skipping running/pending jobs from job IDs: '
                    + ', '.join(str(job_id) for job_id in skip_job_ids)
                )
                df_needs_submit = df_needs_submit.loc[~np.array(skip_mask)].reset_index(drop=True)

        # only run `babs submit` when there are subjects/sessions not yet submitted
        if df_needs_submit.empty:
            print('No jobs to submit')
            return

        # If count is positive, submit the first `count` jobs
        if count is not None:
            print(f'Submitting the first {count} jobs')
            df_needs_submit = df_needs_submit.head(min(count, df_needs_submit.shape[0]))

        self.ensure_container_images_available()

        # We know task_id ahead of time, so we can add it to the dataframe
        df_needs_submit['task_id'] = np.arange(1, df_needs_submit.shape[0] + 1)
        # Columns to write before we know the job_id (pre-submit)
        pre_submit_cols = (
            ['sub_id', 'ses_id', 'task_id']
            if self.processing_level == 'session'
            else ['sub_id', 'task_id']
        )
        # Write the job submission dataframe to a csv file before submitting
        df_needs_submit[pre_submit_cols].to_csv(self.job_submit_path_abs, index=False)
        job_id = submit_array(
            self.analysis_path,
            self.queue,
            df_needs_submit.shape[0],
        )

        df_needs_submit['job_id'] = job_id
        # Update the job submission dataframe with the new job id
        print(f'Submitting the following jobs:\n{df_needs_submit}')
        submit_cols = (
            ['sub_id', 'ses_id', 'job_id', 'task_id']
            if self.processing_level == 'session'
            else ['sub_id', 'job_id', 'task_id']
        )
        df_needs_submit[submit_cols].to_csv(self.job_submit_path_abs, index=False)

        # Update the results df
        updated_results_df = update_submitted_job_ids(
            self.get_job_status_df(), df_needs_submit[submit_cols]
        )
        updated_results_df.to_csv(self.job_status_path_abs, index=False)

    def babs_status(self, json_output=False):
        """
        Check job status and makes a nice report.

        Parameters
        ----------
        json_output: bool
            If True, emit only the machine-readable JSON summary to stdout
            (the interface contract) instead of the human-readable table.
        """
        self.ensure_shared_group_runtime_ready()
        statuses = self._update_results_status()
        if json_output:
            print(json.dumps(job_status_counts(statuses)))
        else:
            report_job_status(statuses, self.analysis_path)

    def babs_status_wait(self, interval=300):
        """Poll job status until all submitted jobs complete or fail.

        Exits 0 if nothing has been submitted or all submitted jobs
        succeeded; exits 1 only if a submitted job failed; exits 130
        on Ctrl-C.

        Parameters
        ----------
        interval: int
            Seconds between status checks.
        """
        try:
            while True:
                statuses = self._update_results_status()
                report_job_status(statuses, self.analysis_path)
                sys.stdout.flush()

                submitted = [j for j in statuses.values() if j.submitted]
                if not submitted:
                    print('No jobs have been submitted; nothing to wait on.')
                    return

                done = all(j.has_results or j.is_failed for j in submitted)
                if done:
                    n_results = sum(1 for j in submitted if j.has_results)
                    n_failed = sum(1 for j in submitted if j.is_failed)
                    print(
                        f'\nAll submitted jobs finished: {n_results} succeeded, {n_failed} failed.'
                    )
                    if n_failed > 0:
                        sys.exit(1)
                    return

                time.sleep(interval)
        except KeyboardInterrupt:
            print('\nInterrupted by user.')
            sys.exit(130)
