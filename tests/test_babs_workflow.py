"""Test the babs workflow."""

import argparse
import os
import os.path as op
import time
from pathlib import Path
from unittest import mock

import pytest
from conftest import (
    ensure_container_image,
    gather_slurm_job_diagnostics,
    get_config_simbids_path,
    update_yaml_for_run,
)

from babs import base as babs_base
from babs.cli import _enter_check_setup, _enter_init, _enter_merge, _enter_status, _enter_submit
from babs.scheduler import squeue_to_pandas
from babs.utils import get_results_branches_from_clone


@pytest.mark.parametrize('processing_level', ['subject', 'session'])
def test_babs_init_raw_bids(
    tmp_path_factory,
    templateflow_home,
    bids_data_singlesession,
    bids_data_multisession,
    processing_level,
    simbids_container_ds,
):
    """
    This is to test `babs init` on raw BIDS data.
    """

    # Check the container dataset
    assert op.exists(simbids_container_ds)
    assert op.exists(op.join(simbids_container_ds, '.datalad/config'))

    # Check the bids input dataset:
    assert op.exists(bids_data_singlesession)
    assert op.exists(op.join(bids_data_singlesession, '.datalad/config'))

    # Preparation of env variable `TEMPLATEFLOW_HOME`:
    os.environ['TEMPLATEFLOW_HOME'] = str(templateflow_home)
    assert os.getenv('TEMPLATEFLOW_HOME')

    # Get the cli of `babs init`:
    project_base = tmp_path_factory.mktemp('project')
    project_root = project_base / 'my_babs_project'
    container_name = 'simbids-0-0-3'

    # Use config_simbids.yaml instead of eg_fmriprep
    config_simbids_path = get_config_simbids_path()
    container_config = update_yaml_for_run(
        project_base,
        config_simbids_path.name,
        {
            'BIDS': bids_data_singlesession
            if processing_level == 'subject'
            else bids_data_multisession
        },
    )

    babs_init_opts = argparse.Namespace(
        project_root=project_root,
        list_sub_file=None,
        container_ds=simbids_container_ds,
        container_name=container_name,
        container_config=container_config,
        processing_level=processing_level,
        queue='slurm',
        keep_if_failed=False,
    )

    # Test error when project root already exists
    project_root.mkdir(parents=True, exist_ok=True)
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        with pytest.raises(FileExistsError, match=r'already exists'):
            _enter_init()

    # Test error when parent directory doesn't exist
    non_existent_parent = project_base / 'non_existent' / 'my_babs_project'
    babs_init_opts.project_root = non_existent_parent
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        with pytest.raises(ValueError, match=r'parent folder.*does not exist'):
            _enter_init()

    # Test error when parent directory doesn't exist
    babs_init_opts.project_root = project_root
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        _enter_init()

    # babs check-setup:
    babs_check_setup_opts = argparse.Namespace(project_root=project_root, job_test=True)
    with mock.patch.object(
        argparse.ArgumentParser, 'parse_args', return_value=babs_check_setup_opts
    ):
        _enter_check_setup()

    # test babs status before submitting jobs
    babs_status_opts = argparse.Namespace(project_root=project_root)
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_status_opts):
        _enter_status()

    ensure_container_image(project_root, container_name)

    # babs submit:
    babs_submit_opts = argparse.Namespace(
        project_root=project_root,
        select=None,
        inclusion_file=None,
        count=1,
        skip_running_jobs=False,
    )
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_submit_opts):
        _enter_submit()

    # babs status:
    babs_status_opts = argparse.Namespace(project_root=project_root)
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_status_opts):
        _enter_status()

    finished = False
    for waitnum in [5, 8, 10, 15, 30, 60, 120]:
        time.sleep(waitnum)
        print(f'Waiting {waitnum} seconds...')
        df = squeue_to_pandas()
        print(df)
        if df.empty:
            finished = True
            break

    if not finished:
        raise RuntimeError('Jobs did not finish in time')

    # Refresh status so has_results is set from output RIA branches before submitting
    # remaining jobs (otherwise the same subject would be submitted again).
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_status_opts):
        _enter_status()

    # Submit the remaining job(s):
    babs_submit_opts = argparse.Namespace(
        project_root=project_root,
        select=None,
        inclusion_file=None,
        count=None,
        skip_running_jobs=False,
    )
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_submit_opts):
        _enter_submit()

    # Wait for all submitted jobs to finish before merging
    finished = False
    for waitnum in [5, 8, 10, 15, 30, 60, 120]:
        time.sleep(waitnum)
        print(f'Waiting for remaining jobs {waitnum} seconds...')
        df = squeue_to_pandas()
        print(df)
        if df.empty:
            finished = True
            break

    if not finished:
        raise RuntimeError('Remaining jobs did not finish in time')

    babs_merge_opts = argparse.Namespace(
        project_root=project_root, chunk_size=2000, trial_run=False
    )

    # Avoid running `git branch --list` in the RIA store (can hang in CI). When
    # merge_ds exists (after clone in babs_merge), list remote branches there.
    _orig_get_results_branches_method = babs_base.BABS._get_results_branches

    def _get_results_branches_use_merge_ds_when_exists(self):
        merge_ds = Path(self.project_root) / 'merge_ds'
        if merge_ds.exists():
            return get_results_branches_from_clone(str(merge_ds))
        return _orig_get_results_branches_method(self)

    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_merge_opts):
        with mock.patch.object(
            babs_base.BABS, '_get_results_branches', _get_results_branches_use_merge_ds_when_exists
        ):
            try:
                _enter_merge()
            except ValueError as e:
                if 'no successfully finished job' in str(e).lower():
                    diag = gather_slurm_job_diagnostics(
                        project_root, log_glob='sim.*', max_logs=None, tail_lines=None
                    )
                    raise ValueError(f'{e}\nJob accounting (sacct):\n{diag}') from e
                raise


def test_bootstrap_cleanup(babs_project_sessionlevel_babsobject):
    """Test that the cleanup method properly removes a partially created project."""

    # Run cleanup
    babs_project_sessionlevel_babsobject.clean_up()

    # Verify project was removed
    assert not op.exists(babs_project_sessionlevel_babsobject.project_root)


def test_init_import_files(tmp_path_factory, babs_project_sessionlevel_babsobject):
    """Test importing external files into the BABS project."""
    # Create a test file
    test_file = tmp_path_factory.mktemp('files') / 'test_file.txt'
    with open(test_file, 'w') as f:
        f.write('Test content')

    # Import the file
    file_list = [{'original_path': str(test_file), 'analysis_path': 'code/imported_file.txt'}]
    babs_project_sessionlevel_babsobject._init_import_files(file_list)

    # Check if file was imported
    imported_path = (
        Path(babs_project_sessionlevel_babsobject.project_root)
        / 'analysis'
        / 'code'
        / 'imported_file.txt'
    )
    assert imported_path.exists()
    assert imported_path.read_text() == 'Test content'


def test_init_import_files_nonexistent(babs_project_sessionlevel_babsobject):
    """Test error handling when trying to import non-existent files."""

    # Try to import a non-existent file
    file_list = [
        {'original_path': '/nonexistent/file.txt', 'analysis_path': 'code/imported_file.txt'}
    ]
    with pytest.raises(FileNotFoundError, match='does not exist'):
        babs_project_sessionlevel_babsobject._init_import_files(file_list)


def test_datalad_save_with_filtering(babs_project_sessionlevel_babsobject):
    """Test datalad_save with file filtering."""
    # Create test files
    test_file1 = Path(babs_project_sessionlevel_babsobject.analysis_path) / 'test_file1.txt'
    test_file2 = Path(babs_project_sessionlevel_babsobject.analysis_path) / 'test_file2.txt'

    with open(test_file1, 'w') as f:
        f.write('Test content 1')

    with open(test_file2, 'w') as f:
        f.write('Test content 2')

    # Save with filtering
    babs_project_sessionlevel_babsobject.datalad_save(
        path=[
            str(test_file1.relative_to(babs_project_sessionlevel_babsobject.analysis_path)),
            str(test_file2.relative_to(babs_project_sessionlevel_babsobject.analysis_path)),
        ],
        message='Test save',
        filter_files=[str(test_file2.name)],
    )

    # Check that test_file1 was saved but test_file2 was filtered out
    import subprocess

    result = subprocess.run(
        ['git', 'ls-files'],
        cwd=babs_project_sessionlevel_babsobject.analysis_path,
        capture_output=True,
        text=True,
    )

    assert test_file1.name in result.stdout
    assert test_file2.name not in result.stdout
