"""This is the main module."""

import datalad.api as dlapi
import pandas as pd

from babs.base import BABS
from babs.utils import get_results_branches

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

    def babs_update_input_data(self, dataset_name='BIDS'):
        """
        This function updates the input data in the BABS project.
        """
        # Get the input data dataset
        dataset_to_update = self.input_datasets[dataset_name]

        # Check that there are no results branches: if there are you need to merge first
        results_branches = get_results_branches(self.output_ria_data_dir)
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
