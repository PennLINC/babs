"""This is the main module."""

import datalad.api as dlapi
import pandas as pd

from babs.base import BABS

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
        """
        Update the job status dataframe with the new inclusion dataframe.
        """
        # Get the job status dataframe
        job_status_df = self.get_job_status_df()
        updated_job_status_df = job_status_df.copy()
        if not removed_rows.empty:
            # Use an anti-join to remove matching rows
            updated_job_status_df = (
                job_status_df.merge(removed_rows, how='left', indicator=True)
                .query('_merge == "left_only"')
                .drop('_merge', axis=1)
            )

        if not added_rows.empty:
            # Update the job status dataframe with the new inclusion dataframe
            updated_job_status_df = pd.concat(
                [job_status_df, added_rows], axis=0, ignore_index=True
            )

        # Ensure the has_results column is a boolean
        for column in ['has_results', 'submitted']:
            updated_job_status_df[column] = (
                updated_job_status_df[column].astype('boolean').fillna(False)
            )

        # Save the job status dataframe
        updated_job_status_df.to_csv(self.job_status_path_abs, index=False)
