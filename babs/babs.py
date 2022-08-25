# This is the main module.

import os
import os.path as op
import datalad.api as dlapi
import pandas as pd

from babs.utils import *

class BABS():
    """The BABS class is for babs projects of BIDS Apps"""

    def __init__(self, project_root, type_session, system):
        '''
        Parameters:
        ------------
        project_root: str
            absolute path to the root of this babs project
        type_session: str
            whether the input dataset is "multi-ses" or "single-ses"
        system: str
            the job scheduling system, "sge" or "slurm"

        Attributes:
        ---------------
        project_root: str
            absolute path to the root of this babs project
        type_session: str
            whether the input dataset is "multi-ses" or "single-ses"
        system: str
            the job scheduling system, "sge" or "slurm"
        analysis_datalad_handle: datalad dataset
            the `analysis` datalad dataset
        input_ria_url: str
            URL of input RIA store, sibling of `analysis`, starting with "ria+file://". The computation of each job will start with a clone from this input RIA store.
        output_ria_url: str
            URL of output RIA store, sibling of `analysis`, starting with "ria+file://". The results of jobs will be pushed to this output RIA store.
        '''

        self.project_root = project_root
        self.type_session = type_session
        self.system = system

        self.analysis_path = op.join(project_root, "analysis")
        self.analysis_datalad_handle = None

        self.input_ria_url = "ria+file://" + op.join(project_root, "input_ria")
        self.output_ria_url = "ria+file://" + op.join(project_root, "output_ria")


    def babs_bootstrap(self, input_pd, container_ds):
        """
        Bootstrap a babs project: initialize datalad-tracked RIAs, generate scripts to be used, etc

        Parameters:
        -------------
        input_pd: pandas DataFrame
            Input dataset(s). 
            Columns are: "is_zipped" (True or False) and "input_ds" (path to the input dataset) 
            Can have more than one row (i.e., more than one input dataset).
        container_ds: str
            path to the container datalad dataset

        """

        print("hey you entered babs_bootstrap method of BABS class!")
        print("input_pd:")
        print(input_pd)

        print(container_ds)

        # ==============================================================
        # Initialize: TODO
        # ==============================================================
        
        # make a directory of project_root:
        os.makedirs(self.project_root)  

        # create `analysis` folder:
        if op.exists(self.analysis_path):
            # check if it's a datalad dataset:
            _ = dlapi.status(dataset = self.analysis_path)  
            print("Folder `analysis` exists in the `project_root`; not to re-create it.")
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
        else:
            self.analysis_datalad_handle = dlapi.create(self.analysis_path,
                                                        cfg_proc='yoda',
                                                        annex=True)

        # create RIA siblings:

        # TODO: add sanity check: if the input_ria and output_ria have been created, check if they are analysis's siblings + they are ria siblings; then, update them with datalad push from anlaysis folder

        self.analysis_datalad_handle.create_sibling_ria(name = "output",
                                                        url = self.output_ria_url,
                                                        new_store_ok = True)
        # ^ ref: in python environment: import datalad; help(datalad.distributed.create_sibling_ria)
            # seems there is no docs online?
        # source code: https://github.com/datalad/datalad/blob/master/datalad/distributed/create_sibling_ria.py


        # ==============================================================
        # Bootstrap scripts: TODO
        # ==============================================================

        # ==============================================================
        # Clean up: TODO
        # ==============================================================
