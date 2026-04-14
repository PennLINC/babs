"""This is the main module."""

import os.path as op

import datalad.api as dlapi
import pandas as pd

from babs.base import BABS
from babs.status import (
    JobStatus,
    SchedulerState,
    read_job_status_csv,
    write_job_status_csv,
)

EMPTY_JOB_STATUS_DF = pd.DataFrame(
    columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'has_results']
)
EMPTY_JOB_SUBMIT_DF = pd.DataFrame(columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'state'])


class BABSUpdate(BABS):
    """Implement updates to a BABS project - code and input datasets."""

    def babs_sync_code(self, commit_message='Update code'):
        """
        This function syncs the code in the BABS project with the code in the repository.
        """
        updated_files = [
            status
            for status in self.analysis_datalad_handle.status(eval_subdataset_state='commit')
            if status['state'] != 'clean'
        ]

        self.datalad_save(
            path=[status['path'] for status in updated_files],
            message=commit_message,
        )

        self.analysis_datalad_handle.push(to='input')
        self.analysis_datalad_handle.push(to='output')

    def babs_update_input_data(
        self, dataset_name='BIDS', initial_inclusion_df: pd.DataFrame | None = None
    ):
        """
        This function updates the input data in the BABS project.
        """
        # Get the input data dataset
        dataset_to_update = self.input_datasets[dataset_name]

        # Check that there are no results branches: if there are you need to merge first
        results_branches = self._get_results_branches()
        if results_branches:
            raise ValueError('You must run `babs merge` before updating input data.')

        if dataset_to_update.is_up_to_date:
            print(f'Input dataset {dataset_name} is up to date.')
            return

        # Ensure the dataset in babs is present
        self.analysis_datalad_handle.get(
            dataset_to_update.path_in_babs, get_data=False, recursive=False
        )
        in_babs_ds = dlapi.Dataset(dataset_to_update.babs_project_analysis_path)

        # Update the in-babs version with the origin version
        self.analysis_datalad_handle.update(sibling='output', how='merge')

        in_babs_ds.update(sibling='origin', how='merge')

        self.analysis_datalad_handle.save(
            message=f'Update {dataset_name} from origin',
        )

        pre_update_inclusion_df = self.inclusion_dataframe.copy()
        self._update_inclusion_dataframe(initial_inclusion_df)
        post_update_inclusion_df = self.inclusion_dataframe

        # Find added rows (in post but not in pre)
        added_rows = post_update_inclusion_df.merge(
            pre_update_inclusion_df, how='left', indicator=True
        ).loc[lambda x: x['_merge'] == 'left_only']
        added_rows = added_rows.drop('_merge', axis=1)

        # Find removed rows (in pre but not in post)
        removed_rows = pre_update_inclusion_df.merge(
            post_update_inclusion_df, how='left', indicator=True
        ).loc[lambda x: x['_merge'] == 'left_only']
        removed_rows = removed_rows.drop('_merge', axis=1)
        print('\nChanges in inclusion dataframe:')
        if not added_rows.empty:
            print(f'\nAdded {len(added_rows)} job(s) to process:')
            print(added_rows)
        if not removed_rows.empty:
            print(f'\nRemoved {len(removed_rows)} job(s) to process:')
            print(removed_rows)
        if added_rows.empty and removed_rows.empty:
            print('No changes detected in the inclusion dataframe.')

        self._update_job_status_with_new_inclusion(added_rows, removed_rows)

        # Send the results to input and output rias
        self.analysis_datalad_handle.push(to='input')
        self.analysis_datalad_handle.push(to='output')

    def _update_job_status_with_new_inclusion(
        self, added_rows: pd.DataFrame, removed_rows: pd.DataFrame
    ):
        """Update the job status with added/removed subjects or sessions."""
        if not op.exists(self.job_status_path_abs):
            statuses = {}
        else:
            statuses = read_job_status_csv(self.job_status_path_abs)

        if not removed_rows.empty:
            for _, row in removed_rows.iterrows():
                ses_id = row.get('ses_id') if 'ses_id' in removed_rows.columns else None
                key = (row['sub_id'], ses_id) if ses_id else (row['sub_id'],)
                statuses.pop(key, None)

        if not added_rows.empty:
            for _, row in added_rows.iterrows():
                ses_id = row.get('ses_id') if 'ses_id' in added_rows.columns else None
                sub_id = row['sub_id']
                key = (sub_id, ses_id) if ses_id else (sub_id,)
                if key not in statuses:
                    statuses[key] = JobStatus(
                        sub_id=sub_id,
                        ses_id=ses_id,
                        scheduler_state=SchedulerState.NOT_SUBMITTED,
                        has_results=False,
                        job_id=None,
                        task_id=None,
                        time_used='',
                        time_limit='',
                        nodes=0,
                        cpus=0,
                        partition='',
                        name='',
                    )

        write_job_status_csv(self.job_status_path_abs, statuses)
