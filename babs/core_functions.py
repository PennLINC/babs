""" Define core functions used in BABS """

import os
import os.path as op
import pandas as pd
# from tqdm import tqdm
import datalad.api as dlapi

from babs.babs import BABS
from babs.utils import *

def babs_init(where_project, project_name, 
            input, container_ds,
            container_name, container_config_yaml_file,
            type_session, system):
    
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
            element 1: type of the input (is_zipped), True or False
            element 2: path to the input datalad dataset
    container_ds: str
        path to the container datalad dataset
    type_session: str
        multi-ses or single-ses
    system: str
        sge or slurm


    """
    # print datalad version:
    print("DataLad version: " + get_datalad_version())   # if no datalad is installed, will raise error

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

    # TODO: add sanity check of type_session and system!


    # change the `args.input` as a pandas table easy to read:
    #print(input)
    input_pd = pd.DataFrame({'is_zipped':[input[0][0]], 
                            'input_ds': [input[0][1]]})
                            #  # TODO: make ^ generalized to more than one --input flags!
    # sanity check on the input dataset: the dir should exist, and should be datalad dataset:
    for the_input_ds in input_pd["input_ds"]:
        _ = dlapi.status(dataset = the_input_ds)  
        # ^^ if not datalad dataset, there will be an error saying no installed dataset found
        # if fine, will print "nothing to save, working tree clean"


    # Create an instance of babs class:
    babs_proj = BABS(project_root,
                    type_session,
                    system)
    # print out key information for visual check:
    print("")
    print("project_root of this BABS project: " + babs_proj.project_root)
    print("type of data of this BABS project: " + babs_proj.type_session)
    print("job scheduling system of this BABS project: " + babs_proj.system)
    print("")
    # call method `babs_bootstrap()`:
    babs_proj.babs_bootstrap(input_pd, container_ds, container_name, container_config_yaml_file)