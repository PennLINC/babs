# This is to test `babs-check-setup`.

import os
import os.path as op
import sys
import argparse
import pytest
from unittest import mock
sys.path.append("..")
sys.path.append("../babs")
from babs.cli import (    # noqa
    babs_init_main,
    babs_check_setup_main)
from get_data import (   # noqa
    get_input_data,
    container_ds_path,
    where_now,
    if_circleci,
    get_container_config_yaml_filename,
    __location__,
    INFO_2ND_INPUT_DATA,
    LIST_WHICH_BIDSAPP,
    TOYBIDSAPP_VERSION_DASH,
    TEMPLATEFLOW_HOME
)

@pytest.mark.order(index=2)
@pytest.mark.parametrize(
    "which_case, error_type, error_msg",[
        # container_ds` has wrong path; not to `--keep-if-failed`
        ("not_to_keep_failed", Exception, "`--project-root` does not exist!"),
        # container_ds` has wrong path #todo: perhaps it should be changed to RuntimeError?
        ("wrong_container_ds", AssertionError, "There is no containers DataLad dataset in folder:"),
        # `input ds` has wrong path
        ("wrong_input_ds", FileNotFoundError, "No such file or directory:")
    ]
)
def test_babs_check_setup(
        which_case, error_type, error_msg,
        tmp_path, tmp_path_factory,
        container_ds_path, if_circleci,
        type_system="sge"
):
    """
    This is to test `babs-check-setup` in different failed `babs-init` cases.
    Successful `babs-init` has been tested in `test_babs_init.py`.
    We won't test `--job-test` either as that requires installation of cluster simulation system.

    Parameters:
    ---------------
    which_case: str
        'not_to_keep_failed': `container_ds` has wrong path; not to `--keep-if-failed` in `babs-init`
        'wrong_container_ds': `container_ds` has wrong path, `--keep-if-failed` in `babs-init`
        'wrong_input_ds': `input ds` has wrong path, `--keep-if-failed` in `babs-init`
        All cases have something going wrong, leading to `babs-init` failure;
        Only in case `not_to_keep_failed`, flag `--keep-if-failed` in `babs-init` won't turn on,
        so expected error will be: BABS project does not exist.
    error_type: Exception
        The type of expected error raised by `babs-check-setup`
    error_msg: str
        The expected error message raised by `babs-check-setup`
    tmp_path: fixture from pytest
    tmp_path_factory: fixture from pytest
    container_ds_path: fixture; str
        Path to the container datalad dataset
    type_system: str
         the type of job scheduling system, "sge" or "slurm" (shouldn't make a difference here)
    """
    # fixed variables:
    which_bidsapp = "toybidsapp"
    assert which_bidsapp in LIST_WHICH_BIDSAPP
    which_input = "BIDS"
    type_session = "multi-ses"
    if_input_local = False

    # Get the path to input dataset:
    path_in = get_input_data(which_input, type_session, if_input_local, tmp_path_factory)
    input_ds_cli = [[which_input, path_in]]

    # TODO: should we just point to a dir in tmp_path? the assert should not be needed
    # Preparation of env variable `TEMPLATEFLOW_HOME`:
    os.environ["TEMPLATEFLOW_HOME"] = TEMPLATEFLOW_HOME
    assert os.getenv('TEMPLATEFLOW_HOME') is not None    # assert env var has been set

    # Get the cli of `babs-init`:
    project_name = "my_babs_project"
    project_root = str(tmp_path / project_name)
    container_name = which_bidsapp + "-" + TOYBIDSAPP_VERSION_DASH


    container_config_yaml_file = \
        get_container_config_yaml_filename(which_bidsapp, which_input, if_two_input=False,
                                           type_system=type_system)

    # below are all correct options:
    babs_init_opts = argparse.Namespace(
        where_project=str(tmp_path),
        project_name=project_name,
        input=input_ds_cli,
        list_sub_file=None,
        container_ds=container_ds_path,
        container_name=container_name,
        container_config_yaml_file=container_config_yaml_file,
        type_session=type_session,
        type_system=type_system,
        keep_if_failed=True
    )

    # inject something wrong --> `babs-init` will fail:
    container_ds_path_wrong = "/random/path/to/container_ds"
    input_ds_cli_wrong = [[which_input, "/random/path/to/input_ds"]]
    if which_case == "not_to_keep_failed":
        babs_init_opts.container_ds = container_ds_path_wrong
        # `--keep-if-failed`:
        babs_init_opts.keep_if_failed = False
    elif which_case == "wrong_container_ds":
        babs_init_opts.container_ds = container_ds_path_wrong
    elif which_case == "wrong_input_ds":
        babs_init_opts.input = input_ds_cli_wrong
    else:
        pytest.skip("No rules provided for this case!")

    # run `babs-init`:
    with mock.patch.object(
            argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        babs_init_main()

    # Get cli of `babs-check-setup`:
    babs_check_setup_opts = argparse.Namespace(
        project_root=project_root,
        job_test=False
    )

    # Run `babs-check-setup`:
    with mock.patch.object(
            argparse.ArgumentParser, 'parse_args', return_value=babs_check_setup_opts):
        with pytest.raises(error_type,
                           match=error_msg):   # contains what pattern in error message
            babs_check_setup_main()
