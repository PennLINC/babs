# This is to test `babs init`.
import argparse
import os
import os.path as op
from pathlib import Path
from unittest import mock

import yaml

from babs.cli import _enter_check_setup, _enter_init  # noqa
from babs.utils import read_yaml, write_yaml  # noqa

# Get the path to the notebooks directory
NOTEBOOKS_DIR = Path(__file__).parent.parent / 'notebooks'


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

    for ds_name, ds_path in input_datasets_updates.items():
        babs_config['input_datasets'][ds_name]['origin_url'] = ds_path

    yaml_data = babs_config.copy()
    for imported_file in yaml_data.get('imported_files', []):
        imported_file['original_path'] = str(imported_file['original_path'])
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

    if not op.exists(NOTEBOOKS_DIR):
        raise FileNotFoundError(f'Notebooks directory not found at {NOTEBOOKS_DIR}')

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

    container_config = update_yaml_for_run(
        project_base, 'eg_fmriprep-24-1-1_anatonly.yaml', {'BIDS': bids_data_singlesession}
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

    # run `babs init`:
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        _enter_init()

    # # ================== ASSERT ============================
    # # Assert by running `babs check-setup`
    # babs_check_setup_opts = argparse.Namespace(project_root=project_root, job_test=False)
    # # Run `babs check-setup`:
    # with mock.patch.object(
    #     argparse.ArgumentParser, 'parse_args', return_value=babs_check_setup_opts
    # ):
    #     _enter_check_setup()
