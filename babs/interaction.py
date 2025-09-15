"""This is the main module."""

import numpy as np

from babs.base import BABS
from babs.scheduler import (
    report_job_status,
    submit_array,
)
from babs.utils import (
    update_submitted_job_ids,
)


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

        # Check if there are still jobs running
        currently_running_df = self.get_currently_running_jobs_df()
        if currently_running_df.shape[0] > 0:
            raise Exception(
                'There are still jobs running. Please wait for them to finish or cancel them.'
                f' Current running jobs:\n{currently_running_df}'
            )

        # Find the rows that don't have results yet
        status_df = self.get_job_status_df()
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

    def babs_status(self):
        """
        Check job status and makes a nice report.
        """
        self._update_results_status()
        currently_running_df = self.get_currently_running_jobs_df()
        current_results_df = self.get_job_status_df()
        report_job_status(current_results_df, currently_running_df, self.analysis_path)
