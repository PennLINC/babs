# This is the main module.

import os
import os.path as op
from re import L
import subprocess
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
        input_ria_path: str
            Path to the input RIA store, the sibling of `analysis`. The computation of each job will start with a clone from this input RIA store.
        output_ria_path: str
            Path to the output RIA store, the sibling of `analysis`. The results of jobs will be pushed to this output RIA store.
        input_ria_url: str
            URL of input RIA store, starting with "ria+file://". 
        output_ria_url: str
            URL of output RIA store, starting with "ria+file://". 
        output_ria_data_dir: str
            Path to the output RIA's data directory. Example: /full/path/to/project_root/output_ria/e48/03bc1-9eec-4543-9387-90415ca3477e
        '''

        self.project_root = project_root
        self.type_session = type_session
        self.system = system

        self.analysis_path = op.join(project_root, "analysis")
        self.analysis_datalad_handle = None

        self.input_ria_path = op.join(project_root, "input_ria")
        self.output_ria_path = op.join(project_root, "output_ria")

        self.input_ria_url = "ria+file://" + self.input_ria_path
        self.output_ria_url = "ria+file://" + self.output_ria_path

        self.output_ria_data_dir = None     # not known yet before output_ria is created


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

        entry_pwd = os.getcwd()

        print("hey you entered babs_bootstrap method of BABS class!")
        print("input_pd:")
        print(input_pd)

        print(container_ds)

        # ==============================================================
        # Initialize:
        # ==============================================================
        
        # make a directory of project_root:
        if not op.exists(self.project_root):
            os.makedirs(self.project_root)  

        # create `analysis` folder:
        if op.exists(self.analysis_path):
            # check if it's a datalad dataset:
            try:
                _ = dlapi.status(dataset = self.analysis_path)  
                print("Folder 'analysis' exists in the `project_root` and is a datalad dataset; not to re-create it.")
                self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
            except:
                raise Exception("Folder 'analysis' exists but is not a datalad dataset. Please remove this folder and rerun.")
        else:
            self.analysis_datalad_handle = dlapi.create(self.analysis_path,
                                                        cfg_proc='yoda',
                                                        annex=True)

        # Create output RIA sibling:
        print("Creating output and input RIA...")
        if op.exists(self.output_ria_path):
            pass
            # TODO: add sanity check: if the input_ria and output_ria have been created, check if they are analysis's siblings + they are ria siblings; then, update them with datalad push from anlaysis folder
        else:
            self.analysis_datalad_handle.create_sibling_ria(name = "output",
                                                            url = self.output_ria_url,
                                                            new_store_ok = True)
        # ^ ref: in python environment: import datalad; help(datalad.distributed.create_sibling_ria)
            # sometimes, have to first `temp = dlapi.Dataset("/path/to/analysis/folder")`, then `help(temp.create_sibling_ria)`, you can stop here, or now you can help(datalad.distributed.create_sibling_ria)
            # seems there is no docs online?
        # source code: https://github.com/datalad/datalad/blob/master/datalad/distributed/create_sibling_ria.py

        # get the `self.output_ria_data_dir`, e.g., /full/path/output_ria/e48/03bc1-9eec-4543-9387-90415ca3477e
        analysis_git_path = op.join(self.analysis_path, ".git")
        proc_output_ria_data_dir = subprocess.run(
            ["git", "--git-dir", analysis_git_path, "remote", "get-url", "--push", "output"],
            stdout=subprocess.PIPE)   # another way to change the wd temporarily: add `cwd=self.xxx` in `subprocess.run()`
        proc_output_ria_data_dir.check_returncode()   # if success: no output; if failed: will raise CalledProcessError
        self.output_ria_data_dir = proc_output_ria_data_dir.stdout.decode('utf-8')
        if self.output_ria_data_dir[-1:] == "\n":
            self.output_ria_data_dir = self.output_ria_data_dir[:-1]  # remove the last 2 characters
        
        # Create input RIA sibling:
        if op.exists(self.input_ria_path):
            pass
            # TODO: add sanity check: if the input_ria and output_ria have been created, check if they are analysis's siblings + they are ria siblings; then, update them with datalad push from anlaysis folder
        else:
            self.analysis_datalad_handle.create_sibling_ria(name = "input",
                                                            url = self.input_ria_url,
                                                            storage_sibling = False,   # False is `off` in CLI of datalad
                                                            new_store_ok = True)
            
        # Register the input dataset:
        if op.exists(op.join(self.analysis_path, "inputs/data")):
            print("The input dataset has been copied into `analysis` folder; not to copy again.")
            pass
            # TODO: add sanity check: if its datalad sibling is input dataset
        else:
            print("Cloning input dataset(s)...")
            dlapi.clone(dataset = self.analysis_path,  # clone input dataset(s) as sub-dataset into `analysis` dataset
                        source = input_pd.at[0, "input_ds"],    # input dataset(s)
                        path = op.join(self.analysis_path, "inputs/data"))   # path to clone into

            # amend the previous commit with a nicer commit message:
            proc_git_commit_amend = subprocess.run(
                ["git", "commit", "--amend", "-m", "Register input data dataset as a subdataset"],
                cwd = self.analysis_path,
                stdout=subprocess.PIPE
            )
            proc_git_commit_amend.check_returncode()

            # confirm the cloned dataset is valid: if multi-ses, has `ses-*` in each `sub-*`; if single-ses, has a `sub-*`
            check_validity_input_dataset(op.join(self.analysis_path, "inputs/data"),
                                        self.type_session)
        # ^^ TODO: to be generalized to multiple input datasets!

        # Add container as sub-dataset of `analysis`:
        # # TO ASK: WHY WE NEED TO CLONE IT FIRST INTO `project_root`???
        # dlapi.clone(source = container_ds,    # container datalad dataset
        #             path = op.join(self.project_root, "containers"))   # path to clone into

        # directly add container as sub-dataset of `analysis`:
        dlapi.install(dataset = self.analysis_path,  # clone input dataset(s) as sub-dataset into `analysis` dataset
                    source = container_ds,    # container datalad dataset
                    path = op.join(self.analysis_path, "containers"))    # into `analysis\containers` folder

        # original bash command, if directly going into as sub-dataset:
        # datalad install -d . --source ../../toybidsapp-container-docker/ containers

        # from our the way:
        # cd ${PROJECTROOT}/analysis
        # datalad install -d . --source ${PROJECTROOT}/pennlinc-containers

        print("")


        # ==============================================================
        # Bootstrap scripts: TODO
        # ==============================================================

        # ==============================================================
        # Clean up: TODO
        # ==============================================================
