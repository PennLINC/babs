# This is the main module.

import os
import os.path as op
from re import L
import subprocess
import pandas as pd

import datalad.api as dlapi
from datalad_container.find_container import find_container_

from babs.utils import *
#from utils import *

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


    def babs_bootstrap(self, input_pd, container_ds, container_name, container_config_yaml_file):
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

        # print("hey you entered babs_bootstrap method of BABS class!")
        # print("input_pd:")
        # print(input_pd)

        # print(container_ds)

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
        print("Register the input dataset...")
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
        print("Add the container as a sub-dataset of `analysis` dataset...")
        if op.exists(op.join(self.analysis_path, "containers")):
            print("The container has been added as a sub-dataset; not to do it again.")
            pass
            # TODO: check if the container has been successfully added as a sub-dataset!
        else:
            dlapi.install(dataset = self.analysis_path,  # clone input dataset(s) as sub-dataset into `analysis` dataset
                        source = container_ds,    # container datalad dataset
                        path = op.join(self.analysis_path, "containers"))    # into `analysis\containers` folder

        # original bash command, if directly going into as sub-dataset:
        # datalad install -d . --source ../../toybidsapp-container-docker/ containers

        # from our the way:
        # cd ${PROJECTROOT}/analysis
        # datalad install -d . --source ${PROJECTROOT}/pennlinc-containers



        # ==============================================================
        # Bootstrap scripts: TODO
        # ==============================================================

        container = Container(container_ds, container_name, container_config_yaml_file)

        # Generate bash script of singularity run + zip:
        bash_path = op.join(self.analysis_path, "code", container_name, "_zip.sh")  # e.g., analysis/code/fmriprep-0-0-0_zip.sh
        container.generate_bash_run_bidsapp(bash_path, self.type_session)
        print()


        # ==============================================================
        # Clean up: TODO
        # ==============================================================

class Container():
    """This class is for the BIDS App Container"""
    def __init__(self, container_ds, container_name, config_yaml_file=None):
        """
        This is to initalize Container class.

        Parameters:
        --------------
        container_ds: str
            The path to the container datalad dataset as the input of `babs-init`
        container_name: str
            The name of the container when adding to datalad dataset (e.g., `NAME` in `datalad containers-add NAME`), e.g., fmriprep-0-0-0
        config_yaml_file: str or None
            The YAML file that contains the configurations of how to run the container
            This is optional argument (of the CLI `babs-init`)
        """

        self.container_ds = container_ds
        self.container_name = container_name
        self.config_yaml_file = config_yaml_file

    def generate_bash_run_bidsapp(self, bash_path, type_session):
        """
        This is to generate a bash script that runs the BIDS App singularity image.

        Parameters:
        -------------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        type_session: str
            multi-ses or single-ses.
        """

        type_session = validate_type_session(type_session)

        # Check if the folder exist; if not, create it:
        bash_dir = op.dirname(bash_path)
        if not op.exists(bash_dir):
            os.makedirs(bash_dir)

        
        # TODO: continue adding commands......

        # Read container config YAML file:
        if self.config_yaml_file is None:
            config = None
            print("Did not provide `container_config_yaml_file`; command of singularity run will be read from information saved by `call-fmt` when `datalad containers-add.`")
        else:
            config = read_container_config_yaml(self.config_yaml_file)
            # check if it contains information we need:
            if "babs_singularity_run" not in config:
                print("The key 'babs_singularity_run' was not included in the `container_config_yaml_file`. Therefore will not to refer to yaml for command of singularity run.")
            else:   
                print("temp: generate command for xxxx")   # contain \ for each key-value
        print()


        # TODO: read yaml file and parse the arguments in singularity run
        # TODO: also corporate the `call-fmt` in `datalad containers-add`

        # Write into the bash file:
        bash_file = open(bash_path, "a")   # open in append mode 

        bash_file.write('''\
            #!/bin/bash
            set -e -u -x

            subid="$1"
            ''')

        if type_session == "multi-ses":
            bash_file.write('sesid="$2"')   # also have the input of `sesid`
            bash_file.write("\n")
        
        
        bash_file.close()