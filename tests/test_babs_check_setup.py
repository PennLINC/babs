# This is to test `babs check-setup`.

import argparse
import os
import os.path as op
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.append('..')

from get_data import (  # noqa
    SUPPORTED_BIDS_APPS,
    TEMPLATEFLOW_HOME,
    TOYBIDSAPP_VERSION_DASH,
    __location__,
    container_ds_path,
    get_container_config_yaml_filename,
    get_input_data,
    in_circleci,
    exec_environment,
)

from babs.cli import _enter_check_setup, _enter_init  # noqa


@pytest.mark.order(index=2)
@pytest.mark.parametrize(
    'test_scenario', [('not_to_keep_failed'), ('wrong_container_ds'), ('wrong_input_ds')]
)
def test_babs_check_setup(
    test_scenario, tmp_path, tmp_path_factory, container_ds_path, in_circleci
):
    """
    This is to test `babs check-setup` in different failed `babs init` cases.
    Successful `babs init` has been tested in `test_babs_init.py`.
    We won't test `--job-test` either as that requires installation of cluster simulation system.

    Parameters
    ----------
    test_scenario: str
        'not_to_keep_failed': `container_ds` has wrong path;
        not to `--keep-if-failed` in `babs init`
        'wrong_container_ds': `container_ds` has wrong path, `--keep-if-failed` in `babs init`
        'wrong_input_ds': `input ds` has wrong path, `--keep-if-failed` in `babs init`
        All cases have something going wrong, leading to `babs init` failure;
        Only in case `not_to_keep_failed`, flag `--keep-if-failed` in `babs init` won't turn on,
        so expected error will be: BABS project does not exist.
    tmp_path: fixture from pytest
    tmp_path_factory: fixture from pytest
    container_ds_path: fixture; str
        Path to the container datalad dataset
    in_circleci: fixture
        CircleCI environment indicator
    """
    # fixed variables:
    bids_app = 'toybidsapp'
    assert bids_app in SUPPORTED_BIDS_APPS
    input_data_name = 'BIDS'
    processing_level = 'session'
    input_is_local = False

    # Get the path to input dataset:
    path_in = get_input_data(input_data_name, processing_level, input_is_local, tmp_path_factory)
    input_ds_cli = {input_data_name: path_in}
    input_ds_cli_wrong = {input_data_name: '/random/path/to/input_ds'}

    # Container dataset - has been set up by fixture `prep_container_ds_toybidsapp()`
    assert op.exists(container_ds_path)
    assert op.exists(op.join(container_ds_path, '.datalad/config'))
    container_ds_path_wrong = '/random/path/to/container_ds'

    # Preparation of env variable `TEMPLATEFLOW_HOME`:
    os.environ['TEMPLATEFLOW_HOME'] = TEMPLATEFLOW_HOME
    assert os.getenv('TEMPLATEFLOW_HOME') is not None  # assert env var has been set

    # Get the cli of `babs init`:
    project_parent = tmp_path.absolute().as_posix()  # turn into a string
    project_name = 'my_babs_project'
    project_root = Path(op.join(project_parent, project_name))
    container_name = bids_app + '-' + TOYBIDSAPP_VERSION_DASH
    container_config_yaml_filename = 'example_container_' + bids_app + '.yaml'
    container_config_yaml_filename = get_container_config_yaml_filename(
        bids_app, input_data_name, two_inputs=False, queue='slurm'
    )  # TODO: also test slurm!
    container_config = op.join(
        op.dirname(__location__), 'notebooks', container_config_yaml_filename
    )
    assert op.exists(container_config)

    # below are all correct options:
    babs_init_opts = argparse.Namespace(
        project_root=project_root,
        datasets=input_ds_cli,
        list_sub_file=None,
        container_ds=container_ds_path,
        container_name=container_name,
        container_config=container_config,
        processing_level=processing_level,
        queue='slurm',
        keep_if_failed=True,
    )

    # inject something wrong --> `babs init` will fail:
    babs_init_opts.container_ds = container_ds_path_wrong
    # `--keep-if-failed`:
    if test_scenario == 'not_to_keep_failed':
        babs_init_opts.keep_if_failed = False
    # each case, what went wrong:
    if test_scenario == 'not_to_keep_failed':
        babs_init_opts.container_ds = container_ds_path_wrong
    elif test_scenario == 'wrong_container_ds':
        babs_init_opts.container_ds = container_ds_path_wrong
    elif test_scenario == 'wrong_input_ds':
        babs_init_opts.datasets = input_ds_cli_wrong

    # run `babs init`:
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        _enter_init()

    # Get cli of `babs check-setup`:
    babs_check_setup_opts = argparse.Namespace(project_root=project_root, job_test=False)
    # Set up expected error message from `babs check-setup`:
    if test_scenario == 'not_to_keep_failed':
        error_type = Exception  # what's after `raise` in the source code
        error_msg = '`project_root` does not exist!'
        # ^^ see `get_existing_babs_proj()` in CLI
    elif test_scenario == 'wrong_container_ds':
        error_type = AssertionError  # error from `assert`
        error_msg = 'There is no containers DataLad dataset in folder:'
    elif test_scenario == 'wrong_input_ds':
        error_type = FileNotFoundError
        error_msg = 'No such file or directory:'
        # ^^ No such file or directory: '/path/to/my_babs_project/analysis/inputs/data'

    # Run `babs check-setup`:
    with mock.patch.object(
        argparse.ArgumentParser, 'parse_args', return_value=babs_check_setup_opts
    ):
        with pytest.raises(error_type, match=error_msg):  # contains what pattern in error message
            _enter_check_setup()
