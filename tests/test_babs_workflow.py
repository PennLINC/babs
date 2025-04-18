# This is to test `babs init`.
import argparse
import os
import os.path as op
import time
from pathlib import Path
from unittest import mock

import yaml

from babs.cli import _enter_check_setup, _enter_init, _enter_merge, _enter_status, _enter_submit
from babs.scheduler import squeue_to_pandas
from babs.utils import read_yaml

# Get the path to the notebooks directory
NOTEBOOKS_DIR = Path(__file__).parent.parent / 'notebooks'


# Get the path to the config_simbids.yaml file
def get_config_simbids_path():
    """Get the path to the config_simbids.yaml file."""
    e2e_slurm_path = Path(__file__).parent / 'e2e-slurm' / 'container'
    return e2e_slurm_path / 'config_simbids.yaml'


def update_yaml_for_run(new_dir, babs_config_yaml, input_datasets_updates=None):
    """Copy a packaged yaml to a new_dir and make any included_files in new_dir.

    Parameters
    ----------
    new_dir : Path
        The directory to copy the yaml to.
    babs_config_yaml : str
        The name of the yaml file to copy.
    input_datasets_updates : dict
        A dictionary of input datasets to update in the yaml file.

    Returns
    -------
    new_yaml_path : Path
        The path to the new yaml file.
    """

    # Check if we're using the config_simbids.yaml file
    if babs_config_yaml == 'config_simbids.yaml':
        packaged_yaml_path = get_config_simbids_path()
    else:
        packaged_yaml_path = op.join(NOTEBOOKS_DIR, babs_config_yaml)

    new_yaml_path = new_dir / babs_config_yaml

    assert op.exists(packaged_yaml_path)
    babs_config = read_yaml(packaged_yaml_path)

    # Create temporary files for each of the imported files:
    for imported_file in babs_config.get('imported_files', []):
        # create a temporary file:
        fn_imported_file = new_dir / imported_file['original_path'].lstrip('/')
        fn_imported_file.parent.mkdir(parents=True, exist_ok=True)
        with open(fn_imported_file, 'w') as f:
            f.write('FAKE DATA')
        imported_file['original_path'] = fn_imported_file

    # Update input datasets if provided
    if input_datasets_updates:
        for ds_name, ds_path in input_datasets_updates.items():
            babs_config['input_datasets'][ds_name]['origin_url'] = ds_path

    yaml_data = babs_config.copy()
    for imported_file in yaml_data.get('imported_files', []):
        imported_file['original_path'] = str(imported_file['original_path'])

    # Only update these if not already present in the YAML
    if 'script_preamble' not in yaml_data:
        yaml_data['script_preamble'] = 'PATH=/opt/conda/envs/babs/bin:$PATH'

    # How much cluster resources it needs:
    if 'cluster_resources' not in yaml_data:
        yaml_data['cluster_resources'] = {'interpreting_shell': '/bin/bash'}

    if 'job_compute_space' not in yaml_data:
        yaml_data['job_compute_space'] = '/tmp'

    with open(new_yaml_path, 'w') as f:
        yaml.dump(yaml_data, f)

    return new_yaml_path


def test_babs_init_raw_bids(
    tmp_path_factory,
    templateflow_home,
    bids_data_singlesession,
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
        project_base, config_simbids_path.name, {'BIDS': bids_data_singlesession}
    )

    babs_init_opts = argparse.Namespace(
        project_root=project_root,
        list_sub_file=None,
        container_ds=simbids_container_ds,
        container_name=container_name,
        container_config=container_config,
        processing_level='subject',
        queue='slurm',
        keep_if_failed=False,
    )

    # babs init:
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
