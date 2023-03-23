# This is to test `babs-init`.
import os
import os.path as op
import pytest
import shutil
import datalad.api as dlapi
from get_data import (
    get_input_data,
    if_singularity_installed,
    prep_container_ds_toybidsapp,
    WORKING_DIR,
    INFO_2ND_INPUT_DATA,
    ORIGIN_CONTAINER_DS,
    LIST_WHICH_BIDSAPP
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
    #  ("toybidsapp", "BIDS", "single-ses", True, False),
    #  # test fmriprep: single/multi-ses
    #  ("fmriprep", "BIDS", "single-ses", False, False),
    #  ("fmriprep", "BIDS", "multi-ses", False, False),
    #  # test 2 input datasets:
    #  ("toybidsapp", "BIDS", "single-ses", False, True),
     ])
def test_babs_init(which_bidsapp, which_input, type_session, if_input_local, if_two_input,
                   tmp_path, prep_container_ds_toybidsapp,
                   if_singularity_installed):
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
    tmp_path: str
        Path to a temporary directory, created by pytest
    """
    # Sanity checks:
    assert which_bidsapp in LIST_WHICH_BIDSAPP

    # Get the path to input dataset:
    path_in = get_input_data(which_input, type_session, if_input_local)
    input_ds_cli = [[path_in, which_input]]
    if if_two_input:
        # get another input dataset: qsiprep derivatives
        assert INFO_2ND_INPUT_DATA["which_input"] != which_input   # avoid repeated input ds name
        path_in_2nd = get_input_data(
            INFO_2ND_INPUT_DATA["which_input"],
            type_session,   # should be consistent with the 1st dataset
            INFO_2ND_INPUT_DATA["if_input_local"])
        input_ds_cli.append([path_in_2nd], INFO_2ND_INPUT_DATA["which_input"])

    # Container dataset - has been set up by fixture `prep_container_ds_toybidsapp()`
    assert op.exists(ORIGIN_CONTAINER_DS)

    # get the cli
    print("TODO")

    # run `babs-init`:
    print("TODO")

    # Assert several things:
    print("TODO")
    # check if those scripts are generated:

    # check if input dataset(s) are there:

    # check if container dataset is there:

    # check if input and output RIA have been created:

    # check `sub_ses_final_inclu.csv`:
    #   if qsiprep + multi-ses:  one session should not be included

    # anything else from `babs-check-setup`?

    # Clean up the temporary dir:
    # remove input dataset(s):
    dlapi.remove(path=path_in)
    if if_two_input:
        dlapi.remove(dataset=path_in_2nd)
    # remove container dataset:
    dlapi.remove(dataset=ORIGIN_CONTAINER_DS, reckless="availability")
    # ^^ --reckless is probably needed as there is no other container ds copy

    # now, we can remove working directory:
    shutil.rmtree(WORKING_DIR)
    assert not op.exists(WORKING_DIR)
