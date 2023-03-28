# This is to test `babs-init`.
import os
import os.path as op
import sys
import argparse
import pytest
import shutil
from unittest import mock
import datalad.api as dlapi

sys.path.append("..")
from babs.cli import (    # noqa
    babs_init_main,
    babs_check_setup_main)
from get_data import (   # noqa
    get_input_data,
    container_ds_path,
    if_circleci,
    __location__,
    INFO_2ND_INPUT_DATA,
    LIST_WHICH_BIDSAPP,
    TOYBIDSAPP_VERSION_DASH
)

# Define fixtures of different cases to test

# Use parametrizing to test each case

# ARRANGE

@pytest.mark.parametrize(
    "which_bidsapp,which_input,type_session,if_input_local,if_two_input",
    # test toybidsapp: BIDS/zipped x single/multi-ses:
    #   the input data will also be remote by default:
    [("toybidsapp", "BIDS", "single-ses", False, False),
    #  ("toybidsapp", "BIDS", "multi-ses", False, False),
    #  ("toybidsapp", "zipped_derivatives_qsiprep", "single-ses", False, False),
    #  ("toybidsapp", "zipped_derivatives_qsiprep", "multi-ses", False, False),
    #  # test if input is local:
    ("toybidsapp", "BIDS", "single-ses", True, False),
    #  # test fmriprep: single/multi-ses
    #  ("fmriprep", "BIDS", "single-ses", False, False),
    #  ("fmriprep", "BIDS", "multi-ses", False, False),
    #  # test 2 input datasets:
    # ("toybidsapp", "BIDS", "single-ses", False, True),
     ])
def test_babs_init(which_bidsapp, which_input, type_session, if_input_local, if_two_input,
                   tmp_path, tmp_path_factory,
                   container_ds_path, if_circleci
                   ):
    """
    This is to test `babs-init` in different cases.

    Parameters:
    --------------
    which_bidsapp: str
        The name of a BIDS App. However here we only use `toybidsapp` to test, even though you
        specified e.g., fmriprep; we'll make sure the BIDS App to be tested is reflected in
        `container_name` which BABS cares.
        It must be one of the string in `LIST_WHICH_BIDSAPP`.
    which_input: str
        which input dataset. Options see keys in `origin_input_dataset.yaml`
    type_session: str
        multi-ses or single-ses
    if_input_local: bool
        whether the input dataset is a local copy (True), or it's remote (False)
    if_two_input: bool
        whether to use two input datasets
    tmp_path: fixture from pytest
    tmp_path_factory: fixture from pytest
    container_ds_path: fixture; str
        Path to the container datalad dataset
    if_circleci: fixture; bool
        Whether currently in CircleCI
    """
    # Sanity checks:
    assert which_bidsapp in LIST_WHICH_BIDSAPP

    # Get the path to input dataset:
    path_in = get_input_data(which_input, type_session, if_input_local, tmp_path_factory)
    input_ds_cli = [[which_input, path_in]]
    if if_two_input:
        # get another input dataset: qsiprep derivatives
        assert INFO_2ND_INPUT_DATA["which_input"] != which_input   # avoid repeated input ds name
        path_in_2nd = get_input_data(
            INFO_2ND_INPUT_DATA["which_input"],
            type_session,   # should be consistent with the 1st dataset
            INFO_2ND_INPUT_DATA["if_input_local"],
            tmp_path_factory)
        input_ds_cli.append([INFO_2ND_INPUT_DATA["which_input"], path_in_2nd])

    # Container dataset - has been set up by fixture `prep_container_ds_toybidsapp()`
    assert op.exists(container_ds_path)
    assert op.exists(op.join(container_ds_path, ".datalad/config"))

    # Get the cli of `babs-init`:
    where_project = tmp_path.absolute().as_posix()   # turn into a string
    project_name = "my_babs_project"
    project_root = op.join(where_project, project_name)
    container_name = which_bidsapp + "-" + TOYBIDSAPP_VERSION_DASH
    container_config_yaml_file = op.join(op.dirname(__location__), "notebooks",
                                         "example_container_toybidsapp.yaml")
    # +++++++++++++++ change to container-specific yaml file???? ++++++++++++

    babs_init_opts = argparse.Namespace(
        where_project=where_project,
        project_name=project_name,
        input=input_ds_cli,
        list_sub_file=None,
        container_ds=container_ds_path,
        container_name=container_name,
        container_config_yaml_file=container_config_yaml_file,
        type_session=type_session,
        type_system="sge",
        keep_if_failed=None
    )

    # run `babs-init`:
    with mock.patch.object(
            argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        babs_init_main()

    # ================== ASSERT ============================
    # Assert by running `babs-check-setup`
    babs_check_setup_opts = argparse.Namespace(
        project_root=project_root,
        job_test=False
    )
    # run `babs-check-setup`:
    with mock.patch.object(
            argparse.ArgumentParser, 'parse_args', return_value=babs_check_setup_opts):
        babs_check_setup_main()


    # check if container dataset is there:

    # check if input and output RIA have been created:

    # check `sub_ses_final_inclu.csv`:
    #   if qsiprep + multi-ses:  one session should not be included

    # anything else from `babs-check-setup`?

    # No need to manually remove temporary dirs; those are created by pytest's fixtures
    #   and will be automatically removed after 3 runs of pytests. ref below:
    #   https://docs.pytest.org/en/7.1.x/how-to/tmp_path.html#the-default-base-temporary-directory
