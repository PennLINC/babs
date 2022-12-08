""" Define core functions used in BABS """

import os
import os.path as op
import pandas as pd
import yaml
# from tqdm import tqdm
import datalad.api as dlapi

from babs.babs import BABS, Input_ds, System
from babs.utils import (get_datalad_version,
                        validate_type_session)


def babs_init(where_project, project_name,
              input, list_sub_file,
              container_ds,
              container_name, container_config_yaml_file,
              type_session, type_system):
    """
    This is the core function of babs-init.

    Parameters:
    --------------
    where_project: str
        absolute path to the directory where the project will be created
    project_name: str
        the babs project name
    input: nested list
        for each sub-list:
            element 1: name of input datalad dataset (str)
            element 2: path to the input datalad dataset (str)
    list_sub_file: str or None
        Path to the CSV file that lists the subject (and sessions) to analyze;
        or `None` if CLI's flag isn't specified
        single-ses data: column of 'sub_id';
        multi-ses data: columns of 'sub_id' and 'ses_id'
    container_ds: str
        path to the container datalad dataset
    container_name: str
        name of the container, best to include version number.
        e.g., 'fmriprep-0-0-0'
    container_config_yaml_file: str
        Path to a YAML file that contains the configurations
        of how to run the BIDS App container
    type_session: str
        multi-ses or single-ses
    type_system: str
        sge or slurm


    """
    # print datalad version:
    # if no datalad is installed, will raise error
    print("DataLad version: " + get_datalad_version())

    # =================================================================
    # Sanity checks:
    # =================================================================
    project_root = op.join(where_project, project_name)

    # # check if it exists:
    # if op.exists(project_root):
    #     raise Exception("the folder `project_name` already exists in the directory `where_project`!")

    # check if `where_project` is writable:
    if not os.access(where_project, os.W_OK):
        raise Exception("the `where_project` is not writable!")

    # validate `type_session`:
    type_session = validate_type_session(type_session)

    input_ds = Input_ds(input, list_sub_file, type_session)

    # sanity check on the input dataset: the dir should exist, and should be datalad dataset:
    for the_input_ds in input_ds.df["path_in"]:
        if the_input_ds[0:6] == "osf://":  # first 6 char
            pass   # not to check, as cannot be checked by `dlapi.status`
        else:
            _ = dlapi.status(dataset=the_input_ds)
        # ^^ if not datalad dataset, there will be an error saying no installed dataset found
        # if fine, will print "nothing to save, working tree clean"

    # Create an instance of babs class:
    babs_proj = BABS(project_root,
                     type_session,
                     type_system)

    # Validate system's type name `type_system`:
    system = System(type_system)

    # print out key information for visual check:
    print("")
    print("project_root of this BABS project: " + babs_proj.project_root)
    print("type of data of this BABS project: " + babs_proj.type_session)
    print("job scheduling system of this BABS project: " + babs_proj.type_system)
    print("")

    # call method `babs_bootstrap()`:
    babs_proj.babs_bootstrap(input_ds,
                             container_ds, container_name, container_config_yaml_file,
                             system)

def babs_submit(project_root, count=None, job=None):
    """
    This is the core function of `babs-submit`.

    Parameters:
    --------------
    project_root: str
        absolute path to the directory of BABS project
    count: int or None
        number of jobs to be submitted
        default: None (did not specify in cli)
            if `--job` is not requested, it will be changed to `1` before going into `babs_submit()`
        any negative int will be treated as submitting all jobs that haven't been submitted.
    job: nested list
        For each sub-list, the length should be 1 (for single-ses) or 2 (for multi-ses)
    """

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj = get_existing_babs_proj(project_root)

    # Actions on `count`:
    if count is None:
        count = 1   # if not to specify `--count`, change to 1
    # sanity check:
    if count == 0:
        raise Exception("`--count 0` is not valid! Please specify a positive integer. "
                        + "To submit all jobs, please do not specify `--count`.")

    # Actions on `job`:
    if job is not None:
        count = -1    # just in case; make sure all specified jobs will be submitted

        # sanity check:
        if babs_proj.type_session == "single-ses":
            expected_len = 1
        elif babs_proj.type_session == "multi-ses":
            expected_len = 2
        for i_job in range(0, len(job)):
            # expected length in each sub-list:
            assert len(job[i_job]) == expected_len, \
                "There should be " + str(expected_len) + " arguments in `--job`," \
                    + " as input dataset(s) is " + babs_proj.type_session + "!"
            # 1st argument:
            assert job[i_job][0][0:4] == "sub-", \
                "The 1st argument of `--job`" + " should be 'sub-*'!"
            if babs_proj.type_session == "multi-ses":
                # 2nd argument:
                assert job[i_job][1][0:4] == "ses-", \
                    "The 2nd argument of `--job`" + " should be 'ses-*'!"

        # turn into a pandas DataFrame:
        df_job_specified = pd.DataFrame(None,
                                        index=list(range(0, len(job))),
                                        columns=['sub_id', 'ses_id'])
        for i_job in range(0, len(job)):
            df_job_specified.at[i_job, "sub_id"] = job[i_job][0]
            df_job_specified.at[i_job, "ses_id"] = job[i_job][1]
    else:  # `job` is None:
        df_job_specified = None

    # Call method `babs_submit()`:
    babs_proj.babs_submit(count, df_job_specified)

def babs_status(project_root, resubmit=None):
    """
    This is the core function of `babs-status`.

    Parameters:
    --------------
    project_root: str
        absolute path to the directory of BABS project
    resubmit: nested list or None
        each sub-list: one of 'failed', 'pending', 'stalled'
    """

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj = get_existing_babs_proj(project_root)

    # Get the list of resubmit conditions:
    if resubmit is not None:   # user specified --resubmit
        # e.g., [['pending'], ['failed']]
        # change nested list to a simple list:
        flags_resubmit = []
        for i in range(0, len(resubmit)):
            flags_resubmit.append(resubmit[i][0])

        # remove dupliated elements:
        flags_resubmit = list(set(flags_resubmit))   # `list(set())`: acts like "unique"

        # print(flags_resubmit)
    else:   # `resubmit` is None:
        print("Did not request any flags of resubmit.")
        flags_resubmit = []   # empty list

    # Call method `babs_status()`:
    babs_proj.babs_status(flags_resubmit)

def get_existing_babs_proj(project_root):
    """
    This is to get `babs_proj` (class `BABS`)
    based on existing yaml file `babs_proj_config.yaml`.
    This should be used by `babs_submit()` and `babs_status`.

    Parameters:
    --------------
    project_root: str
        absolute path to the directory of BABS project
        TODO: accept relative path too, like datalad's `-d`

    Returns:
    --------------
    babs_proj: class `BABS`
        information about a BABS project
    """

    # Read configurations of BABS project from saved yaml file:
    babs_proj_config_yaml = op.join(project_root,
                                    "analysis/code/babs_proj_config.yaml")
    if op.exists(babs_proj_config_yaml) is False:
        raise Exception("`babs-init` was not successful:"
                        + " there is no 'analysis/code/babs_proj_config.yaml' file!")

    with open(babs_proj_config_yaml) as f:
        babs_proj_config = yaml.load(f, Loader=yaml.FullLoader)
        # ^^ config is a dict; elements can be accessed by `config["key"]["sub-key"]`
    f.close()

    type_session = babs_proj_config["type_session"]
    type_system = babs_proj_config["type_system"]

    # Get the class `BABS`:
    babs_proj = BABS(project_root, type_session, type_system)

    # update key informations including `output_ria_data_dir`:
    babs_proj.wtf_key_info(flag_output_ria_only=True)

    return babs_proj
