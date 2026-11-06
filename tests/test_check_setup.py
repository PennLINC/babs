"""Test the check_setup functionality."""

import os
import os.path as op
import shutil

import datalad.api as dlapi
import pytest

from babs import BABSCheckSetup
from babs.constants import CHECK_MARK
from babs.input_datasets import InputDatasets


def add_commit_to_ria(ria_path, temp_path):
    """Add and commit a file to the repository."""
    # Clone the dataset from ria_path to temp_path
    dl_handle = dlapi.clone(source=ria_path, path=temp_path)

    # Create new file in the cloned repository
    new_file = temp_path / 'new_file.txt'
    with open(new_file, 'w') as f:
        f.write('New file content')

    # Save and push changes
    dl_handle.save(path=new_file, message='Add new file')
    dl_handle.push(to='origin')


def test_input_shasum(tmp_path_factory, babs_project_sessionlevel, monkeypatch):
    """Test that the input_shasum is correctly checked."""

    project_root = babs_project_sessionlevel

    babs_proj = BABSCheckSetup(project_root)
    # Make sure we have the dataset ID
    babs_proj.wtf_key_info()

    # Mock read_yaml to avoid creating lock files
    def mock_read_yaml(path, use_filelock=False):
        import yaml

        with open(path) as file:
            return yaml.safe_load(file)

    monkeypatch.setattr('babs.check_setup.read_yaml', mock_read_yaml)

    # Run check-setup without test job
    babs_proj.babs_check_setup(submit_a_test_job=False)

    # make a change to the input ria
    add_commit_to_ria(
        f'ria+file://{babs_proj.input_ria_path}#{babs_proj.analysis_dataset_id}',
        tmp_path_factory.mktemp('in_ria'),
    )

    with pytest.raises(ValueError, match='does not match with that of `input RIA`'):
        babs_proj.babs_check_setup(submit_a_test_job=False)


def test_output_shasum(tmp_path_factory, babs_project_sessionlevel, monkeypatch):
    """Test that the input_shasum is correctly checked."""

    project_root = babs_project_sessionlevel

    babs_proj = BABSCheckSetup(project_root)
    # Make sure we have the dataset ID
    babs_proj.wtf_key_info()

    # Mock read_yaml to avoid creating lock files
    def mock_read_yaml(path, use_filelock=False):
        import yaml

        with open(path) as file:
            return yaml.safe_load(file)

    monkeypatch.setattr('babs.check_setup.read_yaml', mock_read_yaml)

    # Run check-setup without test job
    babs_proj.babs_check_setup(submit_a_test_job=False)

    # make a change to the input ria
    add_commit_to_ria(
        f'ria+file://{babs_proj.output_ria_path}#{babs_proj.analysis_dataset_id}',
        tmp_path_factory.mktemp('in_ria'),
    )

    with pytest.raises(ValueError, match='does not match with that of `output RIA`'):
        babs_proj.babs_check_setup(submit_a_test_job=False)


@pytest.mark.skipif(not shutil.which('sbatch'), reason='sbatch command not available')
def test_submit_test_job(babs_project_sessionlevel, monkeypatch):
    """Test _submit_test_job method."""
    babs_proj = BABSCheckSetup(babs_project_sessionlevel)

    # Create check_env.yaml in expected location with valid content
    check_env_path = (
        babs_project_sessionlevel / 'analysis' / 'code' / 'check_setup' / 'check_env.yaml'
    )
    with open(check_env_path, 'w') as f:
        f.write('workspace_writable: true\n')
        f.write("which_python: '/usr/bin/python3'\n")
        f.write('version:\n')
        f.write("  datalad: 'datalad 0.18.0'\n")
        f.write("  git: 'git version 2.34.1'\n")
        f.write("  git-annex: 'git-annex version 10.20220127'\n")
        f.write("  datalad_containers: 'datalad_containers 1.1.6'\n")

    # Mock functions to avoid actual job submission
    def mock_submit_job(*args, **kwargs):
        return 12345  # fake job ID

    def mock_request_status(*args, **kwargs):
        import pandas as pd

        # First call returns a job in the queue, second returns empty
        nonlocal first_call
        if first_call:
            first_call = False
            df = pd.DataFrame(
                {'job_id': [12345], 'task_id': [1], 'name': ['sim_test_job'], 'state': ['RUNNING']}
            )
            return df
        else:
            return pd.DataFrame()  # empty to indicate job completed

    first_call = True
    monkeypatch.setattr('babs.scheduler.submit_one_test_job', mock_submit_job)
    monkeypatch.setattr('babs.scheduler.request_all_job_status', mock_request_status)

    # Create log file as if job ran successfully
    logs_dir = babs_project_sessionlevel / 'analysis' / 'logs'
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / 'sim_test_job.o12345_1'
    with open(log_path, 'w') as f:
        f.write('Job ran successfully\n')

    # Mock print function to capture output
    printed_messages = []
    monkeypatch.setattr(
        'builtins.print', lambda *args, **kwargs: printed_messages.append(' '.join(map(str, args)))
    )

    # Run the test job submission
    babs_proj._submit_test_job()

    # Debug: Print all captured messages to see what's actually being printed
    import sys

    sys.stdout.write('DEBUG: All captured printed messages:\n')
    for i, msg in enumerate(printed_messages):
        sys.stdout.write(f'  {i}: {msg!r}\n')
    sys.stdout.flush()

    # Check expected messages and behavior
    assert any('Submitting test job' in msg for msg in printed_messages)
    assert any('Test job has been submitted' in msg for msg in printed_messages)
    assert any(f'{CHECK_MARK} All good in test job!' in msg for msg in printed_messages)


def test_check_setup_with_non_clean_status(babs_project_sessionlevel):
    """Test check_setup behavior with non-clean datalad status."""
    babs_proj = BABSCheckSetup(babs_project_sessionlevel)

    # Make an uncommitted change to the analysis dataset
    new_file = babs_project_sessionlevel / 'analysis' / 'uncommitted_file.txt'
    with open(new_file, 'w') as f:
        f.write('Uncommitted change')

    # Check setup should raise a ValueError about non-clean status
    with pytest.raises(ValueError, match='Consider running `babs sync-code`'):
        babs_proj.babs_check_setup(submit_a_test_job=False)


@pytest.mark.skipif(os.geteuid() == 0, reason='Test cannot run as root user')
def test_check_setup_no_writable_workspace(babs_project_sessionlevel, monkeypatch):
    """Test check_setup behavior when workspace is not writable."""
    babs_proj = BABSCheckSetup(babs_project_sessionlevel)

    # Mock _submit_test_job to create a check_env.yaml indicating non-writable workspace
    def mock_submit_test_job(*args, **kwargs):
        check_env_path = (
            babs_project_sessionlevel / 'analysis' / 'code' / 'check_setup' / 'check_env.yaml'
        )
        with open(check_env_path, 'w') as f:
            f.write('workspace_writable: false\n')
            f.write("which_python: '/usr/bin/python3'\n")
            f.write('version:\n')
            f.write("  datalad: 'datalad 0.18.0'\n")

        # Create log file
        logs_dir = babs_project_sessionlevel / 'analysis' / 'logs'
        logs_dir.mkdir(exist_ok=True)
        log_path = logs_dir / 'sim_test_job.o12345_1'
        with open(log_path, 'w') as f:
            f.write('Job ran successfully\n')

    monkeypatch.setattr(BABSCheckSetup, '_submit_test_job', mock_submit_test_job)

    # Check setup should raise an Exception about non-writable workspace
    with pytest.raises(Exception, match='The designated workspace is not writable'):
        babs_proj.babs_check_setup(submit_a_test_job=True)


# def test_check_setup_missing_packages(babs_project_sessionlevel, monkeypatch):
#     """Test check_setup behavior when required packages are not installed."""
#     babs_proj = BABSCheckSetup(babs_project_sessionlevel)

#     # Mock _submit_test_job to create a check_env.yaml with missing packages
#     def mock_submit_test_job(*args, **kwargs):
#         check_env_path = (
#             babs_project_sessionlevel / 'analysis' / 'code' / 'check_setup' / 'check_env.yaml'
#         )
#         with open(check_env_path, 'w') as f:
#             f.write('workspace_writable: true\n')
#             f.write("which_python: '/usr/bin/python3'\n")
#             f.write('version:\n')
#             f.write("  datalad: 'datalad 0.18.0'\n")
#             f.write("  git: 'git version 2.34.1'\n")
#             f.write("  git-annex: 'not_installed'\n")  # Missing package

#         # Create log file
#         logs_dir = babs_project_sessionlevel / 'analysis' / 'logs'
#         logs_dir.mkdir(exist_ok=True)
#         log_path = logs_dir / 'sim_test_job.o12345_1'
#         with open(log_path, 'w') as f:
#             f.write('Job ran successfully\n')

#     monkeypatch.setattr(BABSCheckSetup, '_submit_test_job', mock_submit_test_job)

#     # Check setup should raise an Exception about missing packages
#     with pytest.raises(Exception, match='Some required package'):
#         babs_proj.babs_check_setup(submit_a_test_job=True)


def mock_read_yaml(path, use_filelock=False):
    """Read a yaml file without creating lock files."""
    import yaml

    with open(path) as file:
        return yaml.safe_load(file)


def test_check_setup_custom_path_in_babs(babs_project_subjectlevel_study_layout, monkeypatch):
    """check-setup validates input datasets at their configured `path_in_babs`.

    Regression test for #325: the input dataset is cloned to `sourcedata/BIDS`
    (as in the BIDS-study layout) and there is no `inputs/data` folder at all,
    so a hardcoded probe of `inputs/data` would fail with FileNotFoundError.
    """
    project_root = babs_project_subjectlevel_study_layout
    analysis_path = project_root / 'analysis'
    assert op.exists(analysis_path / 'sourcedata' / 'BIDS' / '.datalad' / 'config')
    assert not op.exists(analysis_path / 'inputs')

    monkeypatch.setattr('babs.check_setup.read_yaml', mock_read_yaml)
    babs_proj = BABSCheckSetup(project_root)
    babs_proj.wtf_key_info()
    assert babs_proj.input_datasets['BIDS'].path_in_babs == 'sourcedata/BIDS'

    # Should pass: the input dataset is found at its configured path.
    babs_proj.babs_check_setup(submit_a_test_job=False)


def test_check_setup_input_dataset_at_configured_path(babs_project_subjectlevel):
    """check-setup reports a bad input dataset using its configured `path_in_babs`."""
    babs_proj = BABSCheckSetup(babs_project_subjectlevel)
    in_ds = babs_proj.input_datasets['BIDS']

    # The configured path does not exist:
    in_ds.path_in_babs = 'sourcedata/does_not_exist'
    with pytest.raises(FileNotFoundError, match="input dataset #1 'BIDS' does not exist"):
        babs_proj.babs_check_setup(submit_a_test_job=False)

    # The configured path exists but is not a DataLad dataset:
    in_ds.path_in_babs = 'code'
    with pytest.raises(ValueError, match="'BIDS' is not a valid DataLad dataset"):
        babs_proj.babs_check_setup(submit_a_test_job=False)


def test_check_setup_no_input_datasets(babs_project_subjectlevel):
    """check-setup raises if no input dataset is configured at all."""
    babs_proj = BABSCheckSetup(babs_project_subjectlevel)
    babs_proj.input_datasets = InputDatasets('subject', {})

    with pytest.raises(ValueError, match='There is no input dataset in this BABS project'):
        babs_proj.babs_check_setup(submit_a_test_job=False)


def test_check_setup_missing_container(babs_project_sessionlevel):
    """Test check_setup behavior with missing container dataset."""
    # Remove the container dataset
    container_path = babs_project_sessionlevel / 'analysis' / 'containers'
    if op.exists(container_path / '.datalad'):
        shutil.rmtree(container_path / '.datalad')

    babs_proj = BABSCheckSetup(babs_project_sessionlevel)

    # Check setup should raise a FileNotFoundError about missing container dataset
    with pytest.raises(
        FileNotFoundError, match='There is no containers DataLad dataset in folder'
    ):
        babs_proj.babs_check_setup(submit_a_test_job=False)
