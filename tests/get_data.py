"""This is to get data for pytests"""

import os
import os.path as op

# import tempfile
import shutil
import subprocess
import sys

import datalad.api as dlapi
import pytest

sys.path.append('..')
from babs.utils import read_yaml  # noqa

# =============== Define several constant variables: ==================
__location__ = op.dirname(
    op.abspath(__file__)
)  # the path to the directory of current python script
#   ^^ `op.abspath()` is to make sure always returns abs path, regardless of python version
#       ref: https://note.nkmk.me/en/python-script-file-path/

# containers:
SUPPORTED_BIDS_APPS = ['toybidsapp', 'fmriprep', 'qsiprep']
TOYBIDSAPP_VERSION = '0.0.7'  # +++++++++++++++++++++++
TOYBIDSAPP_VERSION_DASH = TOYBIDSAPP_VERSION.replace('.', '-')
FN_TOYBIDSAPP_Sin_circleci = op.join(
    '/singularity_images', 'toybidsapp_' + TOYBIDSAPP_VERSION + '.sif'
)

# path of input datasets:
ORIGIN_INPUT_DATA = read_yaml(op.join(__location__, 'origin_input_dataset.yaml'))
INFO_2ND_INPUT_DATA = {
    'input_data_name': 'fmriprep',
    # "processing_level": this should be consistent with the first dataset
    'input_is_local': False,
}

# env variables
# TEMPLATEFLOW_HOME = '/test/templateflow_home'
TEMPLATEFLOW_HOME = '/root/TEMPLATEFLOW_HOME_TEMP'  # $HOME is '/root'
# ====================================================================


def get_input_data(input_data_name, processing_level, input_is_local, tmp_path_factory):
    """
    This is to get the path of input data.

    Parameters
    ----------
    input_data_name: str
        'BIDS' - unzipped
        or 'fmriprep' or 'qsiprep' - zipped derivatives
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    input_is_local: bool
        if the input dataset is local [True] or remote (e.g., on OSF) [False]
    tmp_path_factory: fixture
        see: https://docs.pytest.org/en/7.1.x/how-to/tmp_path.html#the-tmp-path-factory

    Returns
    -------
    path_in: str
        where is the input dataset
    """
    # Check if we're on CircleCI - always use cached data on CircleCI
    env_circleci = os.getenv('CIRCLECI')
    if env_circleci:
        cached_path = op.join('/home/circleci/test_data', f'{input_data_name}_{processing_level}')
        if op.exists(cached_path):
            return cached_path
        else:
            raise Exception(
                f'Expected cached dataset not found at {cached_path}. '
                'Did the download_test_data job complete successfully?'
            )

    # For non-CircleCI environments
    if not input_is_local:
        # directly grab from pre-defined YAML file:
        path_in = ORIGIN_INPUT_DATA[input_data_name][processing_level]
    else:
        origin_in = ORIGIN_INPUT_DATA[input_data_name][processing_level]
        # create a temporary folder:
        path_in_pathlib = tmp_path_factory.mktemp(input_data_name)
        # turn into a string of absolute path (but seems not necessary):
        path_in = path_in_pathlib.absolute().as_posix()

        # clone to this local temporary place:
        dlapi.clone(source=origin_in, path=path_in)

    return path_in


@pytest.fixture(scope='session')
def in_circleci():
    """If it's currently running on CircleCI"""
    env_circleci = os.getenv('CIRCLECI')  # a string 'true' or None
    if env_circleci:
        in_circleci = True
    else:
        in_circleci = False

    return in_circleci


@pytest.fixture(scope='session')
def exec_environment(in_circleci):
    """
    Determine where this pytest is running.
    - if is on CircleCI: 'on_circleci';
    - if not on CircleCI, but `singularity` is installed: 'on_cluster'
    - if not either way, `docker` must be installed: 'on_local'
    """
    exec_environment = ''
    # check if singularity is installed:
    singularity_is_installed = command_available('singularity')
    # check if docker is installed:
    docker_is_installed = command_available('docker')

    if in_circleci:
        exec_environment = 'on_circleci'
    elif singularity_is_installed:
        exec_environment = 'on_cluster'
    elif docker_is_installed:
        exec_environment = 'on_local'
    else:
        exec_environment = ''
        raise Exception(
            'Not on CircleCI, and neither singularity nor docker is installed!'
            ' Pytest cannot proceed.'
        )
    return exec_environment


@pytest.fixture(scope='session')
def container_ds_path(exec_environment, tmp_path_factory):
    """
    This is to get toy BIDS App container image + create a datalad dataset of it.
        Depending on if pytest is running on CircleCI,
    it will use pre-built sif file (for CircleCI), or pull the Docker image (for other cases).
        Warning: no matter which BIDS App, we'll use toy BIDS App as the image,
    and name the container as those in `SUPPORTED_BIDS_APPS`. Tested that the same image
    can have different names in one datalad dataset.

    Parameters
    ----------
    exec_environment: from a fixture; str or empty str ("")
        Depending on if on circleci, and singularity or docker is installed:
        - "on_circleci": will use pre-built sif file;
        - "on_cluster": will use `singularity` command to build the sif file
        - "on_local": will use `docker` to pull the container
    tmp_path_factory: fixture in pytest

    Returns
    -------
    origin_container_ds: str
        path to the created container datalad dataset
    """
    docker_addr = 'pennlinc/toy_bids_app:' + TOYBIDSAPP_VERSION
    docker_url = 'docker://' + docker_addr

    # Pull the container image:
    if exec_environment == 'on_circleci':
        # assert the sif file exists:
        assert op.exists(FN_TOYBIDSAPP_Sin_circleci)
        fn_toybidsapp_sif = FN_TOYBIDSAPP_Sin_circleci
    elif exec_environment == 'on_cluster':
        # build the sif file:
        folder_toybidsapp_sif = tmp_path_factory.mktemp('temp_singularity_images')
        fn_toybidsapp_sif = op.join(
            folder_toybidsapp_sif, 'toybidsapp_' + TOYBIDSAPP_VERSION + '.sif'
        )
        proc_singularity_build = subprocess.run(
            # singularity build toybidsapp_${toybidsapp_version}.sif \
            #       docker://pennlinc/toy_bids_app:${toybidsapp_version}
            ['singularity', 'build', fn_toybidsapp_sif, docker_url],
            stdout=subprocess.PIPE,
        )
        proc_singularity_build.check_returncode()
    elif exec_environment == 'on_local':
        # directly pull from docker:
        cmd = 'docker pull ' + docker_addr
        proc_docker_pull = subprocess.run(cmd.split())
        proc_docker_pull.check_returncode()
        fn_toybidsapp_sif = None
    else:
        raise Exception("Invalid `exec_environment` = '" + exec_environment + "'!")

    # Set up container datalad dataset that holds several names of containers
    #   though all of them are toy BIDS App...
    # create a temporary dir:
    origin_container_ds_pathlib = tmp_path_factory.mktemp('my-container')
    origin_container_ds = origin_container_ds_pathlib.absolute().as_posix()
    # create a new datalad dataset for holding the container:
    container_ds_handle = dlapi.create(path=origin_container_ds)
    # add container image into this datalad dataset:
    for bids_app in SUPPORTED_BIDS_APPS:
        if exec_environment in ['on_circleci', 'on_cluster']:  # add the built sif file:
            # datalad containers-add --url ${fn_sif} toybidsapp-${version_tag_dash}
            # API help: in python env: `help(dlapi.containers_add)`
            container_ds_handle.containers_add(
                name=bids_app + '-' + TOYBIDSAPP_VERSION_DASH,  # e.g., "toybidsapp-0-0-7"
                url=fn_toybidsapp_sif,
            )
            # # can remove the original sif file now:
            # os.remove(fn_toybidsapp_sif)
        elif exec_environment == 'on_local':  # add docker image:
            # datalad containers-add --url dhub://pennlinc/toy_bids_app:${version_tag} \
            #   toybidsapp-${version_tag_dash}
            container_ds_handle.containers_add(
                name=bids_app + '-' + TOYBIDSAPP_VERSION_DASH,  # e.g., "toybidsapp-0-0-7"
                url='dhub://' + docker_addr,  # e.g., "dhub://pennlinc/toy_bids_app:0.0.7"
            )

    return origin_container_ds


def get_container_config_yaml_filename(bids_app, input_data_name, two_inputs, queue):
    """
    This is to get the container's config YAML file name,
    depending on the BIDS App and if there are two inputs (for fMRIPrep)

    Parameters
    ----------
    bids_app: str
        name of the bidsapp
    input_data_name: str
        "BIDS" for raw BIDS
        "fmriprep" for zipped BIDS derivates
    two_inputs: bool
        whether there are two input BIDS datasets
    queue: str
        "slurm"

    Returns
    -------
    container_config_yaml_filename: str
        the filename, without the path.
    """
    # dict_cluster_name = {'sge': 'cubic',
    #                      'slurm': 'msi'}
    dict_bidsapp_version = {'qsiprep': '1-0-0', 'fmriprep': '24-1-1', 'toybidsapp': '0-0-7'}
    dict_task_name = {
        'qsiprep': 'regular',
        'fmriprep': 'regular',
        'toybidsapp': 'rawBIDS-walkthrough',
    }

    # bidsapp and its version:
    container_config_yaml_filename = 'eg_' + bids_app + '-' + dict_bidsapp_version[bids_app]

    # task:
    container_config_yaml_filename += '_'
    if (bids_app == 'fmriprep') & two_inputs:
        container_config_yaml_filename += 'ingressed-fs'
    elif (bids_app == 'toybidsapp') & (input_data_name == 'fmriprep'):
        # the input is zipped BIDS derivatives:
        container_config_yaml_filename += 'zipped'
    else:
        container_config_yaml_filename += dict_task_name[bids_app]

    # just add ".yaml", no need to add system names:
    container_config_yaml_filename += '.yaml'

    return container_config_yaml_filename


def command_available(cmd):
    """
    This is to check if a command has been installed on the system

    Parameters
    ----------
    cmd: str
        the command you want to test. e.g., 'singularity'

    Returns
    -------
    is_installed: bool
        True or False
    """
    a = shutil.which(cmd)
    if a is None:  # not exist:
        is_installed = False
    else:
        is_installed = True

    return is_installed
