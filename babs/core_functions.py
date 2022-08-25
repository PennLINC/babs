""" Define core functions used in BABS """

import os
import os.path as op
import pandas as pd
from babs.babs import BABS

def babs_init(where_project, project_name, 
            input, container_ds,
            type_session, system):
    
    """
    This is to core function of babs-init. 

    Parameters:
    --------------
    where_project: str
        absolute path to the directory where the project will be created
    project_name: str
        the babs project name
    input: list
        type of the input (is_zipped) and path to the input datalad dataset
    container_ds: str
        path to the container datalad dataset
    type_session: str
        multi-ses or single-ses
    system: str
        sge or slurm


    """

    # Sanity checks:
    project_root = op.join(where_project, project_name)

    if op.exists(project_root):
        raise Exception("the folder `project_name` already exists in the directory `where_project`!")

    # TODO: add sanity check of type_session and system!

    # change the `args.input` as a pandas table easy to read:
    print(input)
    input_pd = pd.DataFrame({'is_zipped':[input[0]], 
                            'input_ds': [input[1]]})

                            # TODO: make ^ generalized to more than one --input flags!

    # Create an instance of babs class:
    babs_proj = BABS(project_root,
                    type_session,
                    system)
    # print out key information for visual check:
    print("project_root of this BABS project: " + babs_proj.project_root)
    print("type of data of this BABS project: " + babs_proj.type_session)
    print("job scheduling system of this BABS project: " + babs_proj.system)

    # call method `babs_bootstrap()`:
    babs_proj.babs_bootstrap(input_pd, container_ds)