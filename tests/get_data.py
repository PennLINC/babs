"""This is to get data for pytests"""
import sys
import os
import os.path as op
import tempfile
import shutil
import datalad.api as dlapi
sys.path.append("..")
from babs.utils import (read_yaml)   # noqa

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

WORKING_DIR = tempfile.mkdtemp()   # will be different each time you call it
INPUT_DATA_BIDS_DIR = op.join(WORKING_DIR, "DSCSDSI")
# path of input datasets:
ORIGIN_INPUT_DATA = read_yaml(op.join(__location__, "origin_input_dataset.yaml"))
INFO_2ND_INPUT_DATA = {
    "which_input": "zipped_derivatives_qsiprep",
    # "type_session": this should be consistent with the first dataset
    "if_input_local": False
}

def pytest_sessionfinish(session, exitstatus):
    """ whole test run finishes. """
    shutil.rmtree(WORKING_DIR)

def get_input_data(which_input, type_session, if_input_local):
    """
    This is to get the path of input data.

    Parameters:
    ---------------
    which_input: str
        'BIDS' or 'zipped_derivatives_qsiprep'
    type_session: str
        'single-ses' or 'multi-ses'
    if_input_local: bool
        if the input dataset is local [True] or remote (e.g., on OSF) [False]

    Returns:
    -----------
    path_in: str
        where is the input dataset
    """
    if not if_input_local:
        # directly grab from pre-defined YAML file:
        path_in = ORIGIN_INPUT_DATA[which_input][type_session]
    else:
        origin_in = ORIGIN_INPUT_DATA[which_input][type_session]
        # clone to a local temporary place:
        path_in = tempfile.mkdtemp()
        dlapi.clone(source=origin_in,
                    path=path_in)

    return path_in


def get_container_data(which_bidsapp, if_local=True):
    """
    This is to get path to container datalad dataset.

    Parameters:
    -----------
    which_bidsapp: str
        which BIDS App it is.
    if_local: bool
        if the container dataset is local [True] or remote (e.g., on OSF) [False]
    """
    print("TODO")
