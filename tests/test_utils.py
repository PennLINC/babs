import subprocess

import datalad.api as dlapi
import pandas as pd
import pytest

from babs.utils import (
    get_results_branches,
    identify_running_jobs,
    results_branch_dataframe,
    update_results_status,
)


def datalad_dataset_with_branches(ds_path, branch_list):
    """Create a DataLad dataset with branches from the provided list."""
    ds = dlapi.create(path=ds_path)
    ds.save(message='Initial commit')

    for branch in branch_list:
        subprocess.run(['git', 'checkout', '-b', branch], cwd=ds_path, capture_output=True)
        (ds_path / f'{branch}.txt').write_text(f'Content for {branch}')
        ds.save(message=f'Add content for {branch}')
        subprocess.run(['git', 'checkout', 'main'], cwd=ds_path, capture_output=True)

    return ds_path


BRANCH_LISTS = [
    ['job-123-1-sub-01', 'job-123-2-sub-02', 'job-124-1-sub-03'],
    ['job-125-1-sub-01-ses-01', 'job-125-2-sub-01-ses-02', 'job-126-1-sub-02-ses-01'],
]


@pytest.mark.parametrize('branch_list', BRANCH_LISTS)
def test_results_branch_dataframe(tmp_path_factory, branch_list):
    """Test that branch info is correctly extracted to dataframe."""
    ds_path = datalad_dataset_with_branches(tmp_path_factory.mktemp('test_df'), branch_list)
    branch_list = get_results_branches(ds_path)
    if not len(branch_list) == len(branch_list):
        raise ValueError('branch_list should have the same length as the number of branches')

    df = results_branch_dataframe(branch_list)

    assert df.shape[0] == len(branch_list)


def test_update_job_status():
    # One session has results in the results branch
    has_results_df = pd.DataFrame(
        {
            'sub_id': ['sub-0002', 'sub-0002'],
            'ses_id': ['ses-01', 'ses-02'],
            'job_id': [2, 1],
            'task_id': [1, 1],
            'has_results': [True, True],
        }
    )

    # The previous status was checked before submitting the new jobs
    previous_status_df = pd.DataFrame(
        {
            'sub_id': ['sub-0001', 'sub-0001', 'sub-0002', 'sub-0002'],
            'ses_id': ['ses-01', 'ses-02', 'ses-01', 'ses-02'],
            'job_id': [-1, -1, -1, 1],
            'task_id': [-1, -1, -1, 1],
            'submitted': [False, False, False, True],
            'state': [pd.NA, pd.NA, pd.NA, 'R'],
            'time_used': [pd.NA, pd.NA, pd.NA, '10:00'],
            'time_limit': ['5-00:00:00', '5-00:00:00', '5-00:00:00', '5-00:00:00'],
            'nodes': [pd.NA, pd.NA, pd.NA, 1],
            'cpus': [pd.NA, pd.NA, pd.NA, 1],
            'partition': [pd.NA, pd.NA, pd.NA, 'normal'],
            'name': [pd.NA, pd.NA, pd.NA, 'first_run'],
            'has_results': [pd.NA, pd.NA, pd.NA, True],
            # Fields for tracking:
            'needs_resubmit': [False, False, False, False],
            'is_failed': [pd.NA, pd.NA, pd.NA, False],
            'log_filename': [pd.NA, pd.NA, pd.NA, 'test_array_job.log'],
            'last_line_stdout_file': [pd.NA, pd.NA, pd.NA, 'SUCCESS'],
            'alert_message': [pd.NA, pd.NA, pd.NA, pd.NA],
        }
    )

    current_status_df = update_results_status(previous_status_df, has_results_df)

    assert current_status_df.shape[0] == previous_status_df.shape[0]


def test_update_currently_running_jobs_df():
    # This is the list of the most recently submitted jobs
    last_submitted_jobs_df = pd.DataFrame(
        {
            'sub_id': ['sub-0001', 'sub-0001', 'sub-0002', 'sub-0002'],
            'ses_id': ['ses-01', 'ses-02', 'ses-01', 'ses-02'],
            'task_id': [1, 2, 3, 4],
            'job_id': [1, 1, 1, 1],
        }
    )

    # Currently 3 jobs are submitted
    currently_running_df = pd.DataFrame(
        {
            'job_id': [1, 1, 1],
            'task_id': [2, 3, 1],
            'state': ['R', 'PD', 'PD'],
            'time_used': ['0:00', '0:00', '0:01'],
            'time_limit': ['5-00:00:00', '5-00:00:00', '5-00:00:00'],
            'nodes': [1, 1, 1],
            'cpus': [1, 1, 1],
            'partition': ['normal', 'normal', 'normal'],
            'name': ['test_array_job', 'test_array_job', 'test_array_job'],
        }
    )

    identified_running_df = identify_running_jobs(last_submitted_jobs_df, currently_running_df)

    assert set(identified_running_df.columns) == set(currently_running_df.columns) | {
        'sub_id',
        'ses_id',
    }
    assert identified_running_df.shape[0] == 3


def test_update_job_batch_status():
    job_submit_df = pd.DataFrame(
        {
            'sub_id': ['sub-0001', 'sub-0001'],
            'ses_id': ['ses-01', 'ses-02'],
            'job_id': [3, 3],
            'task_id': [1, 2],
            'state': ['R', 'PD'],
            'time_used': ['0:30', '0:00'],
            'time_limit': ['5-00:00:00', '5-00:00:00'],
            'nodes': [1, 1],
            'cpus': [1, 1],
            'partition': ['normal', 'normal'],
            'name': ['third_run', 'third_run'],
        }
    )

    # The previous status was checked before submitting the new jobs
    status_df = pd.DataFrame(
        {
            'sub_id': ['sub-0001', 'sub-0001', 'sub-0002', 'sub-0002'],
            'ses_id': ['ses-01', 'ses-02', 'ses-01', 'ses-02'],
            'job_id': [-1, -1, 2, 1],
            'task_id': [-1, -1, 1, 1],
            'submitted': [False, False, True, True],
            'state': [pd.NA, pd.NA, 'R', 'R'],
            'time_used': [pd.NA, pd.NA, pd.NA, '10:00'],
            'time_limit': ['5-00:00:00', '5-00:00:00', '5-00:00:00', '5-00:00:00'],
            'nodes': [pd.NA, pd.NA, 1, 1],
            'cpus': [pd.NA, pd.NA, 1, 1],
            'partition': [pd.NA, pd.NA, 'normal', 'normal'],
            'name': [pd.NA, pd.NA, 'second_run', 'first_run'],
            'has_results': [False, False, False, True],
            # Fields for tracking:
            'needs_resubmit': [False, False, False, False],
            'is_failed': [pd.NA, pd.NA, pd.NA, False],
            'log_filename': [pd.NA, pd.NA, pd.NA, 'test_array_job.log'],
            'last_line_stdout_file': [pd.NA, pd.NA, pd.NA, 'SUCCESS'],
            'alert_message': [pd.NA, pd.NA, pd.NA, pd.NA],
        }
    )
