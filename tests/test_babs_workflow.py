"""Test the babs workflow."""

import argparse
import os
import os.path as op
import time
from unittest import mock

import pytest
from conftest import get_config_simbids_path, update_yaml_for_run

from babs.cli import _enter_check_setup, _enter_init, _enter_merge, _enter_status, _enter_submit
from babs.scheduler import squeue_to_pandas


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

    # babs submit:
    babs_submit_opts = argparse.Namespace(
        project_root=project_root, select=None, inclusion_file=None, count=1
    )
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_submit_opts):
        _enter_submit()

    # babs status:
    babs_status_opts = argparse.Namespace(project_root=project_root)
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_status_opts):
        _enter_status()

    finished = False
    for waitnum in [5, 8, 10, 15, 30, 60]:
        time.sleep(waitnum)
        print(f'Waiting {waitnum} seconds...')
        df = squeue_to_pandas()
        print(df)
        if df.empty:
            finished = True
            break

    if not finished:
        raise RuntimeError('Jobs did not finish in time')

    # Submit the last job:
    babs_submit_opts = argparse.Namespace(
        project_root=project_root, select=None, inclusion_file=None, count=None
    )
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_submit_opts):
        _enter_submit()

    babs_merge_opts = argparse.Namespace(
        project_root=project_root, chunk_size=2000, trial_run=False
    )
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_merge_opts):
        _enter_merge()
