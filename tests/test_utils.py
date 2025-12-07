import getpass
import io
import subprocess
from pathlib import Path

import datalad.api as dlapi
import pandas as pd
import pytest
import yaml

from babs.utils import (
    app_output_settings_from_config,
    combine_inclusion_dataframes,
    get_git_show_ref_shasum,
    get_immediate_subdirectories,
    get_repo_hash,
    get_results_branches,
    get_username,
    identify_running_jobs,
    parse_select_arg,
    read_yaml,
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


def test_get_username():
    """Test that get_username returns the current username."""
    # Get the expected username using Python's getpass module
    expected_username = getpass.getuser()

    # Test the function
    username = get_username()

    # Check that it returns the expected username
    assert username == expected_username
    assert isinstance(username, str)
    assert len(username) > 0


def test_read_yaml(tmp_path):
    """Test read_yaml function with and without filelock."""
    # Create a test YAML file
    test_data = {'key1': 'value1', 'key2': {'nested_key': 'nested_value'}, 'numbers': [1, 2, 3]}

    yaml_file = tmp_path / 'test_config.yaml'
    with open(yaml_file, 'w') as f:
        yaml.dump(test_data, f)

    # Test without filelock
    result = read_yaml(str(yaml_file))
    assert result == test_data

    # Test with filelock
    # This is more for coverage since verifying the lock is complex
    result_with_lock = read_yaml(str(yaml_file), use_filelock=True)
    assert result_with_lock == test_data

    # Verify the lock file was created (and clean it up)
    lock_file = Path(str(yaml_file) + '.lock')
    if lock_file.exists():
        lock_file.unlink()


def test_app_output_settings_from_config():
    """Test app_output_settings_from_config function with various configs."""
    # Test with basic config
    basic_config = {'zip_foldernames': {'output1': 'v1.0.0'}}

    result_basic, output_dir_basic = app_output_settings_from_config(basic_config)
    assert result_basic == basic_config['zip_foldernames']
    assert output_dir_basic == 'outputs'

    # Test with all_results_in_one_zip set to True
    single_zip_config = {'zip_foldernames': {'output1': 'v1.0.0'}, 'all_results_in_one_zip': True}

    result_single, output_dir_single = app_output_settings_from_config(single_zip_config)
    assert result_single == single_zip_config['zip_foldernames']
    assert output_dir_single == 'outputs/output1'

    # Test with empty zip_foldernames (should raise exception)
    empty_config = {'zip_foldernames': {}}

    with pytest.raises(Exception, match='No output folder name provided'):
        app_output_settings_from_config(empty_config)

    # Test with multiple foldernames and all_results_in_one_zip (should raise exception)
    multiple_folders_config = {
        'zip_foldernames': {'output1': 'v1.0.0', 'output2': 'v1.0.0'},
        'all_results_in_one_zip': True,
    }

    with pytest.raises(Exception, match='create more than one output folder'):
        app_output_settings_from_config(multiple_folders_config)


def create_git_repo(tmp_path):
    """Helper function to create a git repository."""
    repo_path = tmp_path / 'git_repo'
    repo_path.mkdir()

    # Initialize the git repo
    subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True)

    # Configure git user name and email (required for commits)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_path, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'], cwd=repo_path, capture_output=True
    )

    # Create a test file and commit it
    (repo_path / 'test_file.txt').write_text('Test content')
    subprocess.run(['git', 'add', 'test_file.txt'], cwd=repo_path, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_path, capture_output=True)

    return repo_path


def test_get_repo_hash(tmp_path):
    """Test get_repo_hash function."""
    # Create a git repository
    repo_path = create_git_repo(tmp_path)

    # Get the hash with our function
    hash_result = get_repo_hash(repo_path)

    # Get the hash directly with git
    expected_hash = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=repo_path, capture_output=True, text=True
    ).stdout.strip()

    # They should match
    assert hash_result == expected_hash
    assert len(hash_result) == 40  # SHA-1 is 40 chars long

    # Test with invalid repo path
    invalid_path = tmp_path / 'not_a_repo'
    invalid_path.mkdir()
    with pytest.raises(ValueError, match='Error getting the hash'):
        get_repo_hash(invalid_path)


def test_git_show_ref_shasum(tmp_path):
    """Test get_git_show_ref_shasum function."""
    # Create a git repository
    repo_path = create_git_repo(tmp_path)

    # Get the current branch name
    branch_name = subprocess.run(
        ['git', 'branch', '--show-current'], cwd=repo_path, capture_output=True, text=True
    ).stdout.strip()

    # Get the ref with our function
    git_ref, msg = get_git_show_ref_shasum(branch_name, repo_path)

    # Check the result
    assert git_ref
    assert isinstance(git_ref, str)
    assert len(git_ref) == 40  # SHA-1 hash length
    assert branch_name in msg  # The message should contain the branch name

    # Test with non-existent branch
    with pytest.raises(subprocess.CalledProcessError):
        get_git_show_ref_shasum('nonexistent-branch', repo_path)


@pytest.mark.parametrize('branch_list', BRANCH_LISTS)
def test_results_branch_dataframe(tmp_path_factory, branch_list):
    """Test that branch info is correctly extracted to dataframe."""
    ds_path = datalad_dataset_with_branches(tmp_path_factory.mktemp('test_df'), branch_list)
    branch_list = get_results_branches(ds_path)
    if not len(branch_list) == len(branch_list):
        raise ValueError('branch_list should have the same length as the number of branches')

    df = results_branch_dataframe(branch_list, 'subject')

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


def test_running_jobs():
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

    # argparse with action='append' and nargs='+' produces list-of-lists
    nested_subjects = [['sub-0001'], ['sub-0002']]
    assert parse_select_arg(nested_subjects).equals(
        pd.DataFrame({'sub_id': ['sub-0001', 'sub-0002']})
    )

    nested_sub_ses = [['sub-0001', 'ses-01'], ['sub-0002', 'ses-02']]
    assert parse_select_arg(nested_sub_ses).equals(
        pd.DataFrame(
            {
                'sub_id': ['sub-0001', 'sub-0002'],
                'ses_id': ['ses-01', 'ses-02'],
            }
        )
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


def test_read_yaml_timeout(tmp_path, monkeypatch):
    """Test read_yaml with filelock timeout."""
    from unittest.mock import MagicMock, patch

    from filelock import Timeout

    yaml_file = tmp_path / 'test.yaml'
    yaml_file.write_text('key: value')

    with patch('babs.utils.FileLock') as mock_lock:
        mock_lock_instance = MagicMock()
        mock_lock.return_value = mock_lock_instance
        mock_lock_instance.acquire.side_effect = Timeout(lock_file=str(yaml_file) + '.lock')
        result = read_yaml(str(yaml_file), use_filelock=True)
        assert result == {'key': 'value'}


def test_repo_hashes_mismatch(tmp_path):
    """Test compare_repo_commit_hashes when hashes don't match."""
    import warnings

    from babs.utils import compare_repo_commit_hashes

    repo1_path = tmp_path / 'repo1'
    repo2_path = tmp_path / 'repo2'

    for repo_path in [repo1_path, repo2_path]:
        repo_path.mkdir()
        subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@test.com'],
            cwd=repo_path,
            capture_output=True,
        )
        (repo_path / 'file.txt').write_text('content')
        subprocess.run(['git', 'add', 'file.txt'], cwd=repo_path, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=repo_path, capture_output=True)

    (repo2_path / 'file2.txt').write_text('content2')
    subprocess.run(['git', 'add', 'file2.txt'], cwd=repo2_path, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Second'], cwd=repo2_path, capture_output=True)

    with pytest.raises(ValueError, match='does not match'):
        compare_repo_commit_hashes(
            str(repo1_path), str(repo2_path), 'repo1', 'repo2', raise_error=True
        )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = compare_repo_commit_hashes(
            str(repo1_path), str(repo2_path), 'repo1', 'repo2', raise_error=False
        )
        assert result is False
        assert len(w) > 0
        assert any('does not match' in str(warning.message) for warning in w)


def test_parse_select_string():
    """Test parse_select_arg with string input."""
    result = parse_select_arg('sub-0001')
    expected = pd.DataFrame({'sub_id': ['sub-0001']})
    pd.testing.assert_frame_equal(result, expected)


def test_parse_select_nested():
    """Test parse_select_arg with deeply nested lists."""
    nested = [[['sub-0001']], [['sub-0002']]]
    result = parse_select_arg(nested)
    expected = pd.DataFrame({'sub_id': ['sub-0001', 'sub-0002']})
    pd.testing.assert_frame_equal(result, expected)


def test_results_merged_zip():
    """Test update_results_status with merged_zip_completion_df."""
    previous_df = pd.DataFrame(
        {
            'sub_id': ['sub-0001', 'sub-0002'],
            'ses_id': ['ses-01', 'ses-01'],
            'job_id': [-1, -1],
            'task_id': [-1, -1],
            'submitted': [False, False],
            'has_results': [False, False],
            'state': ['', ''],
            'is_failed': [False, False],
        }
    )

    job_completion_df = pd.DataFrame(
        columns=['sub_id', 'ses_id', 'job_id', 'task_id', 'has_results']
    )

    merged_zip_completion_df = pd.DataFrame({'sub_id': ['sub-0001'], 'ses_id': ['ses-01']})

    result = update_results_status(previous_df, job_completion_df, merged_zip_completion_df)

    assert result.shape[0] == 2
    assert result.loc[0, 'has_results'] is True
    assert pd.isna(result.loc[0, 'job_id'])
    assert pd.isna(result.loc[0, 'task_id'])


def test_results_empty_previous():
    """Test update_results_status with empty previous dataframe."""
    previous_df = pd.DataFrame(
        columns=['sub_id', 'ses_id', 'job_id', 'task_id', 'submitted', 'has_results', 'state']
    )

    job_completion_df = pd.DataFrame(
        {
            'sub_id': ['sub-0001'],
            'ses_id': ['ses-01'],
            'job_id': [1],
            'task_id': [1],
            'has_results': [True],
        }
    )

    result = update_results_status(previous_df, job_completion_df)
    assert result.shape[0] == 0


def test_validate_inclusion_df():
    """Test validate_sub_ses_processing_inclusion with DataFrame input."""
    from babs.utils import validate_sub_ses_processing_inclusion

    df = pd.DataFrame({'sub_id': ['sub-0001', 'sub-0002'], 'ses_id': ['ses-01', 'ses-01']})
    result = validate_sub_ses_processing_inclusion(df, 'session')
    pd.testing.assert_frame_equal(result, df)


def test_inclusion_missing_ses():
    """Test validate_sub_ses_processing_inclusion with missing ses_id."""
    from babs.utils import validate_sub_ses_processing_inclusion

    df = pd.DataFrame({'sub_id': ['sub-0001', 'sub-0002']})

    with pytest.raises(Exception, match="There is no 'ses_id' column"):
        validate_sub_ses_processing_inclusion(df, 'session')


def test_inclusion_dup_subject():
    """Test validate_sub_ses_processing_inclusion with duplicated subjects."""
    from babs.utils import validate_sub_ses_processing_inclusion

    df = pd.DataFrame({'sub_id': ['sub-0001', 'sub-0001']})

    with pytest.raises(Exception, match="There are repeated 'sub_id'"):
        validate_sub_ses_processing_inclusion(df, 'subject')


def test_inclusion_dup_session():
    """Test validate_sub_ses_processing_inclusion with duplicated sessions."""
    from babs.utils import validate_sub_ses_processing_inclusion

    df = pd.DataFrame({'sub_id': ['sub-0001', 'sub-0001'], 'ses_id': ['ses-01', 'ses-01']})

    with pytest.raises(Exception, match='There are repeated combinations'):
        validate_sub_ses_processing_inclusion(df, 'session')


def test_inclusion_invalid_file(tmp_path):
    """Test validate_sub_ses_processing_inclusion with invalid file path."""
    from babs.utils import validate_sub_ses_processing_inclusion

    invalid_path = tmp_path / 'does_not_exist.csv'
    with pytest.raises(FileNotFoundError):
        validate_sub_ses_processing_inclusion(str(invalid_path), 'subject')


def test_inclusion_invalid_csv(tmp_path):
    """Test validate_sub_ses_processing_inclusion with invalid CSV file."""
    from babs.utils import validate_sub_ses_processing_inclusion

    invalid_csv = tmp_path / 'invalid.csv'
    invalid_csv.write_text('not,valid,csv\nbroken,file')

    with pytest.raises(Exception, match='Error reading'):
        validate_sub_ses_processing_inclusion(str(invalid_csv), 'subject')


def test_identify_running_jobs_error():
    """Test identify_running_jobs when merge fails."""
    last_submitted_df = pd.DataFrame({'sub_id': ['sub-0001'], 'job_id': [1], 'task_id': [1]})

    currently_running_df = pd.DataFrame({'job_id': [2], 'state': ['R']})

    with pytest.raises(ValueError, match='Error merging'):
        identify_running_jobs(last_submitted_df, currently_running_df)


def test_branch_no_matches():
    """Test results_branch_dataframe with branches that don't match pattern."""
    branches = ['not-a-job-branch', 'also-not-matching', 'master']
    df = results_branch_dataframe(branches, 'subject')

    assert df.empty
    assert list(df.columns) == ['job_id', 'task_id', 'sub_id', 'has_results']


def test_branch_session_level():
    """Test results_branch_dataframe with session-level processing."""
    branches = [
        'job-123-1-sub-0001-ses-01',
        'job-123-2-sub-0001-ses-02',
        'job-124-1-sub-0002-ses-01',
    ]
    df = results_branch_dataframe(branches, 'session')

    assert df.shape[0] == 3
    assert 'ses_id' in df.columns
    assert all(df['has_results'])


def test_submitted_multiple_jobs():
    """Test update_submitted_job_ids with multiple job IDs."""
    results_df = pd.DataFrame(
        {
            'sub_id': ['sub-0001', 'sub-0002'],
            'job_id': [-1, -1],
            'task_id': [-1, -1],
            'submitted': [False, False],
        }
    )

    submitted_df = pd.DataFrame(
        {'sub_id': ['sub-0001', 'sub-0002'], 'job_id': [1, 2], 'task_id': [1, 1]}
    )

    with pytest.raises(ValueError, match='There should be only one job id'):
        update_submitted_job_ids(results_df, submitted_df)


def test_submitted_missing_sub_id():
    """Test update_submitted_job_ids with missing sub_id column."""
    results_df = pd.DataFrame({'sub_id': ['sub-0001'], 'job_id': [-1], 'task_id': [-1]})

    submitted_df = pd.DataFrame({'job_id': [1], 'task_id': [1]})

    with pytest.raises(ValueError, match='job_submit_df must have a sub_id column'):
        update_submitted_job_ids(results_df, submitted_df)
