# This is to test `babs-init`.

import pytest
from get_data import (
    get_input_data,
    INFO_2ND_INPUT_DATA
)

# Define fixtures of different cases to test

# Use parametrizing to test each case

# ARRANGE

@pytest.mark.parametrize(
    "which_bidsapp,which_input,type_session,if_input_local",
    # test toybidsapp: BIDS/zipped x single/multi-ses:
    #   the input data will also be remote by default:
    [("toybidsapp", "BIDS", "single-ses", False),
    #  ("toybidsapp", "BIDS", "multi-ses", False),
    #  ("toybidsapp", "zipped_derivatives_qsiprep", "single-ses", False),
    #  ("toybidsapp", "zipped_derivatives_qsiprep", "multi-ses", False),
    #  # test if input is local:
    #  ("toybidsapp", "BIDS", "single-ses", True),
    #  # test fmriprep: single/multi-ses
    #  ("fmriprep", "BIDS", "single-ses", False),
    #  ("fmriprep", "BIDS", "multi-ses", False),
    #  # test 2 input datasets:   # HOW TO DO SO????
    #  ("toybidsapp_2inputs", "BIDS", "single-ses", False),
     ])
def test_babs_init(which_bidsapp, which_input, type_session, if_input_local, tmp_path):
    """
    This is to test `babs-init` in different cases.

    Parameters:
    --------------
    which_bidsapp: str
        The name of a BIDS App. However here we only use `toybidsapp` to test, even though you
        specified e.g., fmriprep; we'll make sure the BIDS App to be tested is reflected in
        `container_name` which BABS cares.
    which_input: str
        which input dataset. Options see keys in `origin_input_dataset.yaml`
    type_session: str
        multi-ses or single-ses
    if_input_local: bool
        whether the input dataset is a local copy (True), or it's remote (False)
    tmp_path: str
        Path to a temporary directory, created by pytest
    """

    # Get the path to input dataset:
    path_in = get_input_data(which_input, type_session, if_input_local)
    input_ds_cli = [[path_in, which_input]]
    if which_bidsapp == "toybidsapp_2inputs":
        # get another input dataset: qsiprep derivatives
        assert INFO_2ND_INPUT_DATA["which_input"] != which_input   # avoid repeated input ds name
        path_in_2nd = get_input_data(
            INFO_2ND_INPUT_DATA["which_input"],
            type_session,   # should be consistent with the 1st dataset
            INFO_2ND_INPUT_DATA["if_input_local"])
        input_ds_cli.append([path_in_2nd], INFO_2ND_INPUT_DATA["which_input"])

    # Get the path to the container dataset (depending on `which_case`):
    print("TODO")

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

    # clean up the temporary dir
    print("TODO")
