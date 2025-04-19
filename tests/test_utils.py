import io
import subprocess

import datalad.api as dlapi
import pandas as pd
import pytest

from babs.utils import (
    combine_inclusion_dataframes,
    get_immediate_subdirectories,
    get_results_branches,
    identify_running_jobs,
    parse_select_arg,
    replace_placeholder_from_config,
    results_branch_dataframe,
    update_job_batch_status,
    update_results_status,
    update_submitted_job_ids,
    validate_processing_level,
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


def test_get_immediate_subdirectories(tmp_path):
    """Test get_immediate_subdirectories function."""
    # Create test directories
    subdirs = ['dir1', 'dir2', 'dir3']
    for subdir in subdirs:
        (tmp_path / subdir).mkdir()

    # Create a file (should be ignored)
    (tmp_path / 'test_file.txt').write_text('test content')

    # Get subdirectories
    result = get_immediate_subdirectories(tmp_path)

    # Sort both lists for comparison
    assert sorted(result) == sorted(subdirs)


def test_validate_processing_level():
    """Test validate_processing_level function."""
    # Test valid processing levels
    assert validate_processing_level('subject') == 'subject'
    assert validate_processing_level('session') == 'session'

    # Test invalid processing level
    with pytest.raises(ValueError, match='is not allowed'):
        validate_processing_level('invalid_level')


def test_replace_placeholder_from_config():
    """Test replace_placeholder_from_config function."""
    # Test $BABS_TMPDIR replacement
    assert replace_placeholder_from_config('$BABS_TMPDIR') == '"${PWD}/.git/tmp/wkdir"'

    # Test non-placeholder string
    value = 'not_a_placeholder'
    assert replace_placeholder_from_config(value) == value

    # Test with numeric input
    assert replace_placeholder_from_config(42) == '42'


def test_update_results_status():
    """Test update_results_status function."""
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
            'has_results': [False, False, False, True],
            # Fields for tracking:
            'needs_resubmit': [False, False, False, False],
            'is_failed': [pd.NA, pd.NA, pd.NA, False],
            'log_filename': [pd.NA, pd.NA, pd.NA, 'test_array_job.log'],
            'last_line_stdout_file': [pd.NA, pd.NA, pd.NA, 'SUCCESS'],
            'alert_message': [pd.NA, pd.NA, pd.NA, pd.NA],
        }
    )

    updated_df = update_results_status(previous_status_df, has_results_df)

    # Check the shape of the returned dataframe
    assert updated_df.shape[0] == previous_status_df.shape[0]

    # Check that job_id and task_id were updated for entries that have results
    assert updated_df.loc[2, 'job_id'] == 2
    assert updated_df.loc[2, 'task_id'] == 1
    assert updated_df.loc[3, 'job_id'] == 1
    assert updated_df.loc[3, 'task_id'] == 1

    # Check that has_results field was updated
    assert updated_df.loc[2, 'has_results']
    assert updated_df.loc[3, 'has_results']

    # Check that is_failed field was updated correctly
    assert not updated_df.loc[2, 'is_failed']
    assert not updated_df.loc[3, 'is_failed']


def test_combine_inclusion_dataframes():
    """Test combine_inclusion_dataframes function."""
    # Create test DataFrames
    df1 = pd.DataFrame(
        {
            'sub_id': ['sub-01', 'sub-02', 'sub-03'],
            'ses_id': ['ses-01', 'ses-01', 'ses-01'],
            'extra_col1': [1, 2, 3],
        }
    )

    df2 = pd.DataFrame(
        {
            'sub_id': ['sub-01', 'sub-02', 'sub-04'],
            'ses_id': ['ses-01', 'ses-01', 'ses-01'],
            'extra_col2': ['a', 'b', 'c'],
        }
    )

    df3 = pd.DataFrame(
        {
            'sub_id': ['sub-01', 'sub-02', 'sub-05'],
            'ses_id': ['ses-01', 'ses-01', 'ses-01'],
            'extra_col3': [True, False, True],
        }
    )

    # Test with single DataFrame
    result = combine_inclusion_dataframes([df1])
    assert result.equals(df1)

    # Test with multiple DataFrames
    result = combine_inclusion_dataframes([df1, df2, df3])

    # Should only include rows present in all DataFrames
    assert len(result) == 2
    assert set(result['sub_id']) == {'sub-01', 'sub-02'}

    # Should include all columns
    assert 'extra_col1' in result.columns
    assert 'extra_col2' in result.columns
    assert 'extra_col3' in result.columns

    # Test with empty list
    with pytest.raises(ValueError, match='No DataFrames provided'):
        combine_inclusion_dataframes([])


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

    new_status_df = update_job_batch_status(status_df, job_submit_df)

    assert new_status_df.shape[0] == status_df.shape[0]


def test_parse_select_arg():
    select_arg = ['sub-0001', 'sub-0002']
    assert parse_select_arg(select_arg).equals(pd.DataFrame({'sub_id': select_arg}))

    select_arg = ['sub-0001', 'ses-01', 'sub-0002', 'ses-02']
    assert parse_select_arg(select_arg).equals(
        pd.DataFrame({'sub_id': select_arg[::2], 'ses_id': select_arg[1::2]})
    )

    with pytest.raises(ValueError, match='When selecting specific sessions'):
        parse_select_arg(['sub-0001', 'ses-01', 'sub-0002'])

    with pytest.raises(ValueError, match='All subject IDs must start with "sub-"'):
        parse_select_arg(['notasub-0001', 'ses-01', 'notasub-0002', 'ses-02'])

    with pytest.raises(ValueError, match='All session IDs must start with "ses-"'):
        parse_select_arg(['sub-0001', 'notases-01', 'sub-0002', 'notases-02'])


job_status = """\
sub_id,ses_id,submitted,is_failed,state,time_used,time_limit,nodes,cpus,partition,name,job_id,task_id,has_results
sub-0001,ses-01,True,False,R,nan,nan,0,0,nan,nan,6959442,1,True
sub-0001,ses-02,False,False,nan,nan,nan,nan,nan,nan,nan,nan,nan,False
sub-0002,ses-01,False,False,nan,nan,nan,nan,nan,nan,nan,nan,nan,False"""

job_submit = """\
sub_id,ses_id,job_id,task_id
sub-0001,ses-02,6959620,1
sub-0002,ses-01,6959620,2
"""


def test_update_submitted_job_ids():
    job_status_df = pd.read_csv(io.StringIO(job_status))
    job_submit_df = pd.read_csv(io.StringIO(job_submit))
    updated_df = update_submitted_job_ids(job_status_df, job_submit_df)
    assert updated_df['submitted'].all()
