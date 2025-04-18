"""This is the main module."""

import os.path as op

import datalad.api as dlapi
import numpy as np
import pandas as pd

from babs.base import BABS
from babs.scheduler import (
    report_job_status,
    request_all_job_status,
    submit_array,
)
from babs.utils import (
    get_latest_submitted_jobs_columns,
    get_results_branches,
    identify_running_jobs,
    results_branch_dataframe,
    results_status_columns,
    status_dtypes,
    update_job_batch_status,
    update_results_status,
    update_submitted_job_ids,
)

EMPTY_JOB_STATUS_DF = pd.DataFrame(
    columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'has_results']
)
EMPTY_JOB_SUBMIT_DF = pd.DataFrame(columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'state'])


class BABSInteraction(BABS):
    """Implement interactions with a BABS project - submitting jobs and checking status."""

    def babs_submit(self, count=None, submit_df=None, skip_failed=False):
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
        """
        # update `analysis_datalad_handle`:
        if self.analysis_datalad_handle is None:
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)

        # Check if there are still jobs running
        currently_running_df = self.get_currently_running_jobs_df()
        if currently_running_df.shape[0] > 0:
            raise Exception(
                'There are still jobs running. Please wait for them to finish or cancel them.'
                f' Current running jobs:\n{currently_running_df}'
            )

        # Find the rows that don't have results yet
        status_df = self.get_results_status_df()
        df_needs_submit = status_df[~status_df['has_results']].reset_index(drop=True)
        if skip_failed:
            df_needs_submit = df_needs_submit[~df_needs_submit['submitted']]

        if submit_df is not None:
            df_needs_submit = submit_df

        # only run `babs submit` when there are subjects/sessions not yet submitted
        if df_needs_submit.empty:
            print('No jobs to submit')
            return

        # If count is positive, submit the first `count` jobs
        if count is not None:
            print(f'Submitting the first {count} jobs')
            df_needs_submit = df_needs_submit.head(min(count, df_needs_submit.shape[0]))

        # We know task_id ahead of time, so we can add it to the dataframe
        df_needs_submit['task_id'] = np.arange(1, df_needs_submit.shape[0] + 1)
        submit_cols = (
            ['sub_id', 'ses_id', 'job_id', 'task_id']
            if self.processing_level == 'session'
            else ['sub_id', 'job_id', 'task_id']
        )
        # Write the job submission dataframe to a csv file
        df_needs_submit[submit_cols].to_csv(self.job_submit_path_abs, index=False)
        job_id = submit_array(
            self.analysis_path,
            self.queue,
            df_needs_submit.shape[0],
        )

        df_needs_submit['job_id'] = job_id
        # Update the job submission dataframe with the new job id
        print(f'Submitting the following jobs:\n{df_needs_submit}')
        df_needs_submit[submit_cols].to_csv(self.job_submit_path_abs, index=False)

        # Update the results df
        updated_results_df = update_submitted_job_ids(
            self.get_results_status_df(), df_needs_submit[submit_cols]
        )
        updated_results_df.to_csv(self.job_status_path_abs, index=False)

    def _update_results_status(self):
        """
        Update the status of jobs based on results in the output RIA.
        """

        # Step 1: get a list of branches in the output ria to update the status
        list_branches = get_results_branches(self.output_ria_data_dir)
        previous_job_completion_df = self.get_results_status_df()

        if not list_branches:
            return
        # Update the results status
        job_completion_df = results_branch_dataframe(list_branches)
        current_status_df = update_results_status(previous_job_completion_df, job_completion_df)

        # Part 2: Update which jobs are running
        currently_running_df = self.get_currently_running_jobs_df()
        current_status_df = update_job_batch_status(current_status_df, currently_running_df)
        current_status_df['has_results'].fillna(False)
        current_status_df.to_csv(self.job_status_path_abs, index=False)

    def babs_status(self):
        """
        Check job status and makes a nice report.
        """
        self._update_results_status()
        currently_running_df = self.get_currently_running_jobs_df()
        current_results_df = self.get_results_status_df()
        report_job_status(current_results_df, currently_running_df, self.analysis_path)

    def get_latest_submitted_jobs_df(self):
        """
        Get the latest submitted jobs.

        Example:
        --------
        >>> bbs.get_latest_submitted_jobs_df()

            sub_id  job_id  task_id
        0  sub-0001       1        1
        1  sub-0002       1        2

        """
        if not op.exists(self.job_submit_path_abs):
            return EMPTY_JOB_STATUS_DF
        df = pd.read_csv(self.job_submit_path_abs)
        for column_name in get_latest_submitted_jobs_columns(self.processing_level):
            df[column_name] = df[column_name].astype(status_dtypes[column_name])
        return df

    def get_currently_running_jobs_df(self):
        """
        Get the currently running jobs. Subject/session information is added.

        This only reflects currently running jobs, not all of those that have been submitted.
        It is a quick check on job status.

        Examples:
        ---------
        Right after submitting the jobs:
        >>> bbs.get_currently_running_jobs_df()
        job_id  task_id state time_used  time_limit  nodes  cpus partition name    sub_id
        0       1        2    PD      0:00  5-00:00:00      1     1    normal  sim  sub-0002
        1       1        1     R      0:27  5-00:00:00      1     1    normal  sim  sub-0001

        After waiting for a while, the queue will empty:
        >>> bbs.get_currently_running_jobs_df()
        Empty DataFrame
        Columns: [
            job_id, task_id, state, time_used, time_limit, nodes, cpus,
            partition, name, sub_id]
        Index: []

        """
        last_submitted_jobs_df = self.get_latest_submitted_jobs_df()
        if last_submitted_jobs_df.empty:
            return EMPTY_JOB_SUBMIT_DF
        job_ids = last_submitted_jobs_df['job_id'].unique()
        if not len(job_ids) == 1:
            raise Exception(f'Expected 1 job id, got {len(job_ids)}')
        job_id = job_ids[0]
        currently_running_df = request_all_job_status(self.queue, job_id)
        return identify_running_jobs(last_submitted_jobs_df, currently_running_df)

    def get_results_status_df(self):
        """
        Get the results status dataframe.
        """
        if not op.exists(self.job_status_path_abs):
            return EMPTY_JOB_STATUS_DF
        df = pd.read_csv(self.job_status_path_abs)
        for column_name in results_status_columns:
            df[column_name] = df[column_name].astype(status_dtypes[column_name])

        df['has_results'] = df['has_results'].fillna(False)

        return df
