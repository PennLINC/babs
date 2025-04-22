"""This is the main module."""

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
