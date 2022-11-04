""" Define core functions used in BABS """

import os
import os.path as op
import pandas as pd
# from tqdm import tqdm
import datalad.api as dlapi

from babs.babs import BABS, Input_ds, System
from babs.utils import (get_datalad_version)


def babs_init(where_project, project_name,
              input, list_sub_file,
              container_ds,
              container_name, container_config_yaml_file,
              type_session, type_system):
    """
    This is to core function of babs-init.

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

    # TODO: add sanity check of type_session and type_system!

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

    # Validate system's type name:
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
