"""This is to get data for pytests"""
import sys
import os
import os.path as op
import pytest
import tempfile
import shutil
import subprocess
import datalad.api as dlapi
sys.path.append("..")
from babs.utils import (read_yaml)   # noqa

# =============== Define several constant variables: ==================
__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

# make a working dir:
WORKING_DIR = tempfile.mkdtemp()    # will be different each time you call it
# if using `tempfile.mkdtemp()`, have to manually delete the temp folder!
# if using `tempfile.TemporaryDirectory()`, it will be removed, even when pytest is failed.

INPUT_DATA_BIDS_DIR = op.join(WORKING_DIR, "DSCSDSI")
ORIGIN_CONTAINER_DS = op.join(WORKING_DIR, "my-container")
# path of input datasets:
ORIGIN_INPUT_DATA = read_yaml(op.join(__location__, "origin_input_dataset.yaml"))
INFO_2ND_INPUT_DATA = {
    "which_input": "zipped_derivatives_qsiprep",
    # "type_session": this should be consistent with the first dataset
    "if_input_local": False
}
LIST_WHICH_BIDSAPP = ["toybidsapp", "fmriprep", "qsiprep"]
TOYBIDSAPP_VERSION = "0.0.5"   # +++++++++++++++++++++++
TOYBIDSAPP_VERSION_DASH = TOYBIDSAPP_VERSION.replace(".", "-")
# ====================================================================

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

@pytest.fixture(scope="session")
def if_singularity_installed():
    if_singularity_installed = if_command_installed("singularity")
    # also check if Docker is installed:
    if_docker_installed = if_command_installed("docker")
    # check if one of `singularity` and `docker` is installed:
    if (not if_singularity_installed) and (not if_docker_installed):
        raise Exception("Neither singularity or docker is installed!")

    return if_singularity_installed

@pytest.fixture(scope="session")
def prep_container_ds_toybidsapp(if_singularity_installed):
    """
    This is to pull toy BIDS App container image + create a datalad dataset of it.
        Depending on if singularity is installed (True on CircleCI and clusters),
    it will use singularity to build a sif file, or directly pull the Docker image.
        Warning: no matter which BIDS App, we'll use toy BIDS App as the image,
    and name the container as those in `LIST_WHICH_BIDSAPP`. Tested that the same image
    can have different names in one datalad dataset.

    Parameters:
    --------------
    if_singularity_installed: from a fixture; bool
        True or False

    # Returns:
    # -----------
    # fn_sif: str or None
    #     The path to the built sif file.
    #     If singularity is not installed, it will be `None`.
    """
    # docker_addr = "pennlinc/toy_bids_app:" + TOYBIDSAPP_VERSION  # +++++++++++++++++++++++
    docker_addr = "chenyingzhao/toy_bids_app:" + TOYBIDSAPP_VERSION
    docker_url = "docker://" + docker_addr

    # Pull the container image:
    if if_singularity_installed:
        # build a singularity sif image:
        filename_sif = "toybidsapp_" + TOYBIDSAPP_VERSION + ".sif"
        fn_sif = op.join(WORKING_DIR, filename_sif)
        cmd = "singularity build " + filename_sif + " " + docker_url
        proc_build_sif = subprocess.run(
            cmd.split(),
            cwd=WORKING_DIR)
        proc_build_sif.check_returncode()
        # assert the sif file exists:
        assert op.exists(fn_sif)
    else:
        # directly pull from docker:
        cmd = "docker pull " + docker_addr
        proc_docker_pull = subprocess.run(
            cmd.split(),
            cwd=WORKING_DIR)
        proc_docker_pull.check_returncode()
        fn_sif = None

    # Set up container datalad dataset taht holds several names of containers
    #   though all of them are toy BIDS App...
    # create a new datalad dataset for holding the container:
    container_ds_handle = dlapi.create(path=ORIGIN_CONTAINER_DS)
    # add container image into this datalad dataset:
    for which_bidsapp in LIST_WHICH_BIDSAPP:
        if if_singularity_installed:   # add the sif file:
            # datalad containers-add --url ${fn_sif} toybidsapp-${version_tag_dash}
            # API help: in python env: `help(dlapi.containers_add)`
            container_ds_handle.containers_add(
                name=which_bidsapp+"-"+TOYBIDSAPP_VERSION_DASH,  # e.g., "toybidsapp-0-0-6"
                url=fn_sif)
            # can remove the original sif file now:
            os.remove(fn_sif)
        else:   # add docker image:
            # datalad containers-add --url dhub://pennlinc/toy_bids_app:${version_tag} \
            #   toybidsapp-${version_tag_dash}
            container_ds_handle.containers_add(
                name=which_bidsapp+"-"+TOYBIDSAPP_VERSION_DASH,  # e.g., "toybidsapp-0-0-6"
                url="dhub://"+docker_addr   # e.g., "dhub://pennlinc/toy_bids_app:0.0.6"
            )

    return 0

def if_command_installed(cmd):
    """
    This is to check if a command has been installed on the system

    Parameters:
    ------------
    cmd: str
        the command you want to test. e.g., 'singularity'

    Returns:
    ---------
    if_installed: bool
        True or False
    """
    a = shutil.which(cmd)
    if a is None:   # not exist:
        if_installed = False
    else:
        if_installed = True

    return if_installed

def pytest_sessionfinish(session, exitstatus):
    """ whole test run finishes. """
    # if using `tempfile.TemporaryDirectory`, then no need to manually remove this.
    shutil.rmtree(WORKING_DIR)
