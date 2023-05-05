# This is the main module.

import os
import os.path as op
# from re import L
import subprocess
import warnings
import pandas as pd
import numpy as np
import glob
import shutil
import tempfile
import yaml
from filelock import Timeout, FileLock
from datetime import datetime
import time
import re   # regular expression operations

import datalad.api as dlapi
import datalad.support as dlsupport   # for exception name etc
from datalad_container.find_container import find_container_
# from datalad.interface.base import build_doc

from babs.utils import (get_immediate_subdirectories,
                        check_validity_unzipped_input_dataset,
                        if_input_ds_from_osf,
                        generate_cmd_set_envvar,
                        generate_cmd_filterfile,
                        generate_cmd_singularityRun_from_config, generate_cmd_unzip_inputds,
                        generate_cmd_zipping_from_config,
                        validate_type_session,
                        validate_type_system,
                        read_yaml,
                        write_yaml,
                        generate_bashhead_resources,
                        generate_cmd_script_preamble,
                        generate_cmd_job_compute_space,
                        generate_cmd_datalad_run,
                        generate_cmd_determine_zipfilename,
                        get_list_sub_ses,
                        submit_one_job,
                        submit_one_test_job,
                        create_job_status_csv,
                        read_job_status_csv,
                        report_job_status,
                        request_job_status,
                        request_all_job_status,
                        calcu_runtime,
                        get_last_line,
                        get_config_msg_alert,
                        get_alert_message_in_log_files,
                        get_username,
                        check_job_account,
                        print_versions_from_yaml,
                        get_git_show_ref_shasum,
                        ceildiv)

# import pandas as pd

# @build_doc
class BABS():
    """The BABS class is for babs projects of BIDS Apps"""

    def __init__(self, project_root, type_session, type_system):
        '''
        Parameters:
        ------------
        project_root: str
            absolute path to the root of this babs project
        type_session: str
            whether the input dataset is "multi-ses" or "single-ses"
        type_system: str
            the type of job scheduling system, "sge" or "slurm"

        Attributes:
        ---------------
        project_root: str
            absolute path to the root of this babs project
        type_session: str
            whether the input dataset is "multi-ses" or "single-ses"
        type_system: str
            the type of job scheduling system, "sge" or "slurm"
        config_path: str
            path to the config yaml file
        analysis_path: str
            path to the `analysis` folder.
        analysis_datalad_handle: datalad dataset
            the `analysis` datalad dataset
        input_ria_path: str
            Path to the input RIA store, the sibling of `analysis`.
            The computation of each job will start with a clone from this input RIA store.
        output_ria_path: str
            Path to the output RIA store, the sibling of `analysis`.
            The results of jobs will be pushed to this output RIA store.
        input_ria_url: str
            URL of input RIA store, starting with "ria+file://".
        output_ria_url: str
            URL of output RIA store, starting with "ria+file://".
        output_ria_data_dir: str
            Path to the output RIA's data directory.
            Example: /full/path/to/project_root/output_ria/238/da2f2-2fc4-4b88-a2c5-aa6e754b5d0b
        analysis_dataset_id: str
            The ID of DataLad dataset `analysis`.
            This will be used to get the full path to the dataset in input RIA.
            Example: '238da2f2-2fc4-4b88-a2c5-aa6e754b5d0b'
        list_sub_path_rel: str
            Path to the list of final included subjects (and sessions) CSV file.
            This is relative to `analysis` folder.
        list_sub_path_abs: str
            Absolute path of `list_sub_path_rel`.
            Example: '/path/to/analysis/code/sub_final_inclu.csv' for singl-ses dataset;
                '/path/to/analysis/code/sub_ses_final_inclu.csv' for multi-ses dataset.
        job_status_path_rel: str
            Path to the `job_status.csv` file.
            This is relative to `analysis` folder.
        job_status_path_abs: str
            Absolute path of `job_status_path_abs`.
            Example: '/path/to/analysis/code/job_status.csv'
        '''

        # validation:
        type_session = validate_type_session(type_session)
        type_system = validate_type_system(type_system)

        # attributes:
        self.project_root = project_root
        self.type_session = type_session
        self.type_system = type_system

        self.analysis_path = op.join(project_root, "analysis")
        self.analysis_datalad_handle = None

        self.config_path = op.join(self.analysis_path,
                                   "code/babs_proj_config.yaml")

        self.input_ria_path = op.join(project_root, "input_ria")
        self.output_ria_path = op.join(project_root, "output_ria")

        self.input_ria_url = "ria+file://" + self.input_ria_path
        self.output_ria_url = "ria+file://" + self.output_ria_path

        self.output_ria_data_dir = None     # not known yet before output_ria is created
        self.analysis_dataset_id = None    # to update later

        # attribute `list_sub_path_*`:
        if self.type_session == "single-ses":
            self.list_sub_path_rel = 'code/sub_final_inclu.csv'
        elif self.type_session == "multi-ses":
            self.list_sub_path_rel = 'code/sub_ses_final_inclu.csv'
        self.list_sub_path_abs = op.join(self.analysis_path,
                                         self.list_sub_path_rel)

        self.job_status_path_rel = 'code/job_status.csv'
        self.job_status_path_abs = op.join(self.analysis_path,
                                           self.job_status_path_rel)

    def datalad_save(self, path, message=None):
        """
        Save the current status of datalad dataset `analysis`
        Also checks that all the statuses returned are "ok" (or "notneeded")

        Parameters:
        ------------
        path: str or list of str
            the path to the file(s) or folder(s) to save
        message: str or None
            commit message in `datalad save`

        Notes:
        ------------
        If the path does not exist, the status will be "notneeded", and won't be error message
            And there won't be a commit with that message
        """

        statuses = self.analysis_datalad_handle.save(path=path, message=message)
        # ^^ number of dicts in list `statuses` = len(path)
        # check that all statuses returned are "okay":
        # below is from cubids
        saved_status = set([status['status'] for status in statuses])
        if saved_status.issubset(set(["ok", "notneeded"])) is False:
            # exists element in `saved_status` that is not "ok" or "notneeded"
            # ^^ "notneeded": nothing to save
            raise Exception("`datalad save` failed!")

    def wtf_key_info(self, flag_output_ria_only=False):
        """
        This is to get some key information on DataLad dataset `analysis`,
        and assign to `output_ria_data_dir` and `analysis_dataset_id`.
        This function relies on `git` and `datalad wtf`
        This needs to be done after the output RIA is created.

        Parameters:
        ------------
        flag_output_ria_only: bool
            if only to get information on output RIA.
            This may expedite the process as other information requires
            calling `datalad` in terminal, which would takes several seconds.
        """

        # Get the `self.output_ria_data_dir`:
        # e.g., /full/path/output_ria/238/da2f2-2fc4-4b88-a2c5-aa6e754b5d0b
        analysis_git_path = op.join(self.analysis_path, ".git")
        proc_output_ria_data_dir = subprocess.run(
            ["git", "--git-dir", analysis_git_path, "remote", "get-url", "--push", "output"],
            stdout=subprocess.PIPE)
        # ^^: for `analysis`: git remote get-url --push output
        # ^^ another way to change the wd temporarily: add `cwd=self.xxx` in `subprocess.run()`
        # if success: no output; if failed: will raise CalledProcessError
        proc_output_ria_data_dir.check_returncode()
        self.output_ria_data_dir = proc_output_ria_data_dir.stdout.decode('utf-8')
        if self.output_ria_data_dir[-1:] == "\n":
            # remove the last 2 characters
            self.output_ria_data_dir = self.output_ria_data_dir[:-1]

        if not flag_output_ria_only:   # also want other information:
            # Get the dataset ID of `analysis`, i.e., `analysis_dataset_id`:

            # way #1: using datalad api; however, it always prints out the full, lengthy wtf report....
            # # full dict from `datalad wtf`:
            # blockPrint()
            # full_wtf_list = dlapi.wtf(dataset=self.analysis_path)
            # enablePrint()
            # # ^^ this is a list
            # if len(full_wtf_list) > 1:
            #     warnings.warn("There are more than one dictionary for input RIA's `datalad wtf`."
            #                   + " We'll only use the first one.")
            # full_wtf = full_wtf_list[0]
            # # ^^ only take the first dict (element) from the full list
            # self.analysis_dataset_id = full_wtf["infos"]["dataset"]["id"]
            # # ^^: $ datalad -f '{infos[dataset][id]}' wtf -S dataset

            # way #2: command line of datalad:
            proc_analysis_dataset_id = subprocess.run(
                ["datalad", "-f", "'{infos[dataset][id]}'", "wtf", "-S", "dataset"],
                cwd=self.analysis_path,
                stdout=subprocess.PIPE)
            # datalad -f '{infos[dataset][id]}' wtf -S dataset
            proc_analysis_dataset_id.check_returncode()
            self.analysis_dataset_id = proc_analysis_dataset_id.stdout.decode('utf-8')
            # remove the `\n`:
            if self.analysis_dataset_id[-1:] == "\n":
                # remove the last 2 characters
                self.analysis_dataset_id = self.analysis_dataset_id[:-1]
            # remove the double quotes:
            if (self.analysis_dataset_id[0] == "'") & (self.analysis_dataset_id[-1] == "'"):
                # if first and the last characters are quotes: remove them
                self.analysis_dataset_id = self.analysis_dataset_id[1:-1]

    def babs_bootstrap(self, input_ds,
                       container_ds, container_name, container_config_yaml_file,
                       system):
        """
        Bootstrap a babs project: initialize datalad-tracked RIAs, generate scripts to be used, etc

        Parameters:
        -------------
        input_ds: class `Input_ds`
            Input dataset(s).
        container_name: str
            name of the container, best to include version number.
            e.g., 'fmriprep-0-0-0'
        container_ds: str
            path to the container datalad dataset which the user provides
        container_config_yaml_file: str
            Path to a YAML file that contains the configurations
            of how to run the BIDS App container
        system: class `System`
            information about the cluster management system
        """

        # ==============================================================
        # Initialize:
        # ==============================================================

        # Make a directory of project_root:
        os.makedirs(self.project_root)   # we don't allow creation if folder exists

        # Create `analysis` folder: -----------------------------
        print("\nCreating `analysis` folder (also a datalad dataset)...")
        self.analysis_datalad_handle = dlapi.create(self.analysis_path,
                                                    cfg_proc='yoda',
                                                    annex=True)

        # Prepare `.gitignore` ------------------------------
        # write into .gitignore so won't be tracked by git:
        gitignore_path = op.join(self.analysis_path, ".gitignore")
        # if exists already, remove it:
        if op.exists(gitignore_path):
            os.remove(gitignore_path)
        gitignore_file = open(gitignore_path, "a")   # open in append mode

        # not to track `logs` folder:
        gitignore_file.write("\nlogs")
        # not to track `.*_datalad_lock`:
        if system.type == "sge":
            gitignore_file.write("\n.SGE_datalad_lock")
        elif system.type == "slurm":
            # TODO: add command for `slurm`!!!
            print("Not supported yet... To work on...")
        # not to track lock file:
        gitignore_file.write("\n" + "code/babs_proj_config.yaml.lock")
        # not to track `job_status.csv`:
        gitignore_file.write("\n" + "code/job_status.csv")
        gitignore_file.write("\n" + "code/job_status.csv.lock")
        # not to track files generated by `babs-check-setup`:
        gitignore_file.write("\n" + "code/check_setup/test_job_info.yaml")
        gitignore_file.write("\n" + "code/check_setup/check_env.yaml")
        gitignore_file.write("\n")

        gitignore_file.close()
        self.datalad_save(path=".gitignore",
                          message="Save .gitignore file")

        # Create `babs_proj_config.yaml` file: ----------------------
        print("Save configurations of BABS project in a yaml file ...")
        print("Path to this yaml file will be: 'analysis/code/babs_proj_config.yaml'")
        babs_proj_config_file = open(self.config_path, "w")
        babs_proj_config_file.write("type_session: '"
                                    + self.type_session + "'\n")
        babs_proj_config_file.write("type_system: '"
                                    + self.type_system + "'\n")
        # input_ds:
        babs_proj_config_file.write("input_ds:\n")   # input dataset's name(s)
        for i_ds in range(0, input_ds.num_ds):
            babs_proj_config_file.write("  $INPUT_DATASET_#" + str(i_ds+1) + ":\n")
            babs_proj_config_file.write("    name: '" + input_ds.df["name"][i_ds] + "'\n")
            babs_proj_config_file.write("    path_in: '" + input_ds.df["path_in"][i_ds] + "'\n")
            babs_proj_config_file.write("    path_data_rel: 'TO_BE_FILLED'\n")
            babs_proj_config_file.write("    is_zipped: 'TO_BE_FILLED'\n")
        # container ds:
        babs_proj_config_file.write("container:\n")
        babs_proj_config_file.write("  name: '" + container_name + "'\n")
        babs_proj_config_file.write("  path_in: '" + container_ds + "'\n")

        babs_proj_config_file.close()
        self.datalad_save(path="code/babs_proj_config.yaml",
                          message="Save configurations of this BABS project")

        # Create output RIA sibling: -----------------------------
        print("\nCreating output and input RIA...")
        self.analysis_datalad_handle.create_sibling_ria(name="output",
                                                        url=self.output_ria_url,
                                                        new_store_ok=True)
        # ^ ref: in python environment:
        #   import datalad; help(datalad.distributed.create_sibling_ria)
        #   sometimes, have to first `temp = dlapi.Dataset("/path/to/analysis/folder")`,
        #   then `help(temp.create_sibling_ria)`, you can stop here,
        #   or now you can help(datalad.distributed.create_sibling_ria)
        #   seems there is no docs online?
        # source code:
        # https://github.com/datalad/datalad/blob/master/datalad/distributed/create_sibling_ria.py

        # Get some key information re: DataLad dataset `analysis`,
        # after creating output RIA:
        self.wtf_key_info()

        # Create input RIA sibling:
        self.analysis_datalad_handle.create_sibling_ria(
            name="input",
            url=self.input_ria_url,
            storage_sibling=False,   # False is `off` in CLI of datalad
            new_store_ok=True)

        # Register the input dataset(s): -----------------------------
        print("\nRegistering the input dataset(s)...")
        for i_ds in range(0, input_ds.num_ds):
            # path to cloned dataset:
            i_ds_path = op.join(self.analysis_path,
                                input_ds.df["path_now_rel"][i_ds])
            print("Cloning input dataset #" + str(i_ds+1) + ": '"
                  + input_ds.df["name"][i_ds] + "'")
            # clone input dataset(s) as sub-dataset into `analysis` dataset:
            dlapi.clone(dataset=self.analysis_path,
                        source=input_ds.df["path_in"][i_ds],    # input dataset(s)
                        path=i_ds_path)  # path to clone into

            # amend the previous commit with a nicer commit message:
            proc_git_commit_amend = subprocess.run(
                ["git", "commit", "--amend", "-m",
                    "Register input data dataset '" + input_ds.df["name"][i_ds]
                    + "' as a subdataset"],
                cwd=self.analysis_path,
                stdout=subprocess.PIPE
            )
            proc_git_commit_amend.check_returncode()

        # get the current absolute path to the input dataset:
        input_ds.assign_path_now_abs(self.analysis_path)

        # Check the type of each input dataset: (zipped? unzipped?)
        #   this also gets `is_zipped`
        print("\nChecking whether each input dataset is a zipped or unzipped dataset...")
        input_ds.check_if_zipped()
        # sanity checks:
        input_ds.check_validity_zipped_input_dataset(self.type_session)

        # Check validity of unzipped ds:
        #   if multi-ses, has `ses-*` in each `sub-*`; if single-ses, has a `sub-*`
        check_validity_unzipped_input_dataset(input_ds, self.type_session)

        # Update input ds information in `babs_proj_config.yaml`:
        babs_proj_config = read_yaml(self.config_path, if_filelock=True)
        for i_ds in range(0, input_ds.num_ds):
            ds_index_str = "$INPUT_DATASET_#" + str(i_ds+1)
            # update `path_data_rel`:
            babs_proj_config["input_ds"][ds_index_str]["path_data_rel"] = \
                input_ds.df["path_data_rel"][i_ds]
            # update `is_zipped`:
            babs_proj_config["input_ds"][ds_index_str]["is_zipped"] = \
                input_ds.df["is_zipped"][i_ds]
        # dump:
        write_yaml(babs_proj_config, self.config_path, if_filelock=True)
        # datalad save: update:
        self.datalad_save(path="code/babs_proj_config.yaml",
                          message="Update configurations of input dataset of this BABS project")

        # Add container as sub-dataset of `analysis`: -----------------------------
        # # TO ASK: WHY WE NEED TO CLONE IT FIRST INTO `project_root`???
        # dlapi.clone(source = container_ds,    # container datalad dataset
        #             path = op.join(self.project_root, "containers"))   # path to clone into

        # directly add container as sub-dataset of `analysis`:
        print("\nAdding the container as a sub-dataset of `analysis` dataset...")
        dlapi.install(dataset=self.analysis_path,
                      source=container_ds,    # container datalad dataset
                      path=op.join(self.analysis_path, "containers"))
        # into `analysis/containers` folder

        # original bash command, if directly going into as sub-dataset:
        # datalad install -d . --source ../../toybidsapp-container-docker/ containers

        # from our the way:
        # cd ${PROJECTROOT}/analysis
        # datalad install -d . --source ${PROJECTROOT}/pennlinc-containers

        container = Container(container_ds, container_name, container_config_yaml_file)

        # sanity check of container ds:
        container.sanity_check(self.analysis_path)

        # ==============================================================
        # Bootstrap scripts:
        # ==============================================================

        # Generate `<containerName>_zip.sh`: ----------------------------------
        # which is a bash script of singularity run + zip
        # in folder: `analysis/code`
        print("\nGenerating a bash script for running container and zipping the outputs...")
        print("This bash script will be named as `" + container_name + "_zip.sh`")
        bash_path = op.join(self.analysis_path, "code", container_name + "_zip.sh")
        container.generate_bash_run_bidsapp(bash_path, input_ds, self.type_session)
        self.datalad_save(path="code/" + container_name + "_zip.sh",
                          message="Generate script of running container")

        # make another folder within `code` for test jobs:
        os.makedirs(op.join(self.analysis_path, "code/check_setup"), exist_ok=True)

        # Generate `participant_job.sh`: --------------------------------------
        print("\nGenerating a bash script for running jobs at participant (or session) level...")
        print("This bash script will be named as `participant_job.sh`")
        bash_path = op.join(self.analysis_path, "code", "participant_job.sh")
        container.generate_bash_participant_job(bash_path, input_ds, self.type_session,
                                                system)

        # also, generate a bash script of a test job used by `babs-check-setup`:
        path_check_setup = op.join(self.analysis_path, "code/check_setup")
        container.generate_bash_test_job(path_check_setup, system)

        self.datalad_save(path=["code/participant_job.sh",
                                "code/check_setup/call_test_job.sh",
                                "code/check_setup/test_job.py"],
                          message="Participant compute job implementation")
        # NOTE: `dlapi.save()` does not work...
        # e.g., datalad save -m "Participant compute job implementation"

        # Determine the list of subjects to analyze: -----------------------------
        print("\nDetermining the list of subjects (and sessions) to analyze...")
        _ = get_list_sub_ses(input_ds, container.config, self)
        self.datalad_save(path="code/*.csv",
                          message="Record of inclusion/exclusion of participants")

        # Generate the template of job submission: --------------------------------
        print("\nGenerating a template for job submission calls...")
        print("The template text file will be named as `submit_job_template.yaml`.")
        yaml_path = op.join(self.analysis_path, "code", "submit_job_template.yaml")
        container.generate_job_submit_template(yaml_path, input_ds, self, system)

        # also, generate template for testing job used by `babs-check-setup`:
        yaml_test_path = op.join(self.analysis_path, "code/check_setup", "submit_test_job_template.yaml")
        container.generate_test_job_submit_template(yaml_test_path, self, system)

        # datalad save:
        self.datalad_save(path=["code/submit_job_template.yaml",
                                "code/check_setup/submit_test_job_template.yaml"],
                          message="Template for job submission")

        # Finish up and get ready for clusters running: -----------------------
        # create folder `logs` in `analysis`; future log files go here
        #   this won't be tracked by git (as already added to `.gitignore`)
        log_path = op.join(self.analysis_path, "logs")
        if not op.exists(log_path):
            os.makedirs(log_path)

        # in case anything in `code/` was not saved:
        #   If there is anything not saved yet, probably should be added to `.gitignore`
        #   at the beginning of `babs-init`.
        self.datalad_save(path="code/",
                          message="Save anything in folder code/ that hasn't been saved")

        # ==============================================================
        # Final steps in bootstrapping:
        # ==============================================================

        print("\nFinal steps...")
        # No need to keep the input dataset(s):
        #   old version: datalad uninstall -r --nocheck inputs/data
        print("DataLad dropping input dataset's contents...")
        for i_ds in range(0, input_ds.num_ds):
            _ = self.analysis_datalad_handle.drop(
                path=input_ds.df["path_now_rel"][i_ds],
                recursive=True,   # and potential subdataset
                reckless='availability')
            # not to check availability
            # seems have to specify the dataset (by above `handle`);
            # otherwise, dl thinks the dataset is where current python is running

        # Update input and output RIA:
        print("Updating input and output RIA...")
        #   datalad push --to input
        #   datalad push --to output
        self.analysis_datalad_handle.push(to="input")
        self.analysis_datalad_handle.push(to="output")

        # Add an alias to the data in output RIA store:
        print("Adding an alias 'data' to output RIA store...")
        """
        RIA_DIR=$(find $PROJECTROOT/output_ria/???/ -maxdepth 1 -type d | sort | tail -n 1)
        mkdir -p ${PROJECTROOT}/output_ria/alias
        ln -s ${RIA_DIR} ${PROJECTROOT}/output_ria/alias/data
        """
        if not op.exists(op.join(self.output_ria_path,
                                 "alias")):
            os.makedirs(op.join(self.output_ria_path,
                                "alias"))
        # create a symbolic link:
        the_symlink = op.join(self.output_ria_path,
                              "alias", "data")
        if op.exists(the_symlink) & op.islink(the_symlink):
            # exists and is a symlink: remove first
            os.remove(the_symlink)
        os.symlink(self.output_ria_data_dir,
                   the_symlink)
        # to check this symbolic link, just: $ ls -l <output_ria/alias/data>
        #   it should point to /full/path/output_ria/xxx/xxx-xxx-xxx-xxx

        # SUCCESS!
        print("\n`babs-init` was successful!")

    def clean_up(self, input_ds):
        """
        If `babs-init` failed, this function cleans up the BABS project `babs-init` creates.

        Parameters:
        --------------
        input_ds: class `Input_ds`
            information of input dataset(s)

        Notes:
        --------
        Steps in `babs-init`:
        * create `analysis` datalad dataset
        * create input and output RIA
        * clone input dataset(s)
        * generate bootstrapped scripts
        * finish up
        """
        if op.exists(self.project_root):   # if BABS project root folder has been created:
            if op.exists(self.analysis_path):   # analysis folder is created by datalad 
                self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
                # Remove each input dataset:
                print("Removing input dataset(s) if cloned...")
                for i_ds in range(0, input_ds.num_ds):
                    # check if it exists yet:
                    path_now_abs = op.join(self.analysis_path, input_ds.df["path_now_rel"][i_ds])
                    if op.exists(path_now_abs):   # this input dataset has been cloned:
                        # use `datalad remove` to remove:
                        _ = self.analysis_datalad_handle.remove(
                            path=path_now_abs,
                            reckless="modification")

                # `git annex dead here`:
                print("\nRunning `git annex dead here`...")
                proc_git_annex_dead = subprocess.run(
                    ["git", "annex", "dead", "here"],
                    cwd=self.analysis_path,
                    stdout=subprocess.PIPE)
                proc_git_annex_dead.check_returncode()

                # Update input and output RIA:
                print("\nUpdating input and output RIA if created...")
                #   datalad push --to input
                #   datalad push --to output
                if op.exists(self.input_ria_path):
                    self.analysis_datalad_handle.push(to="input")
                if op.exists(self.output_ria_path):
                    self.analysis_datalad_handle.push(to="output")

            # Now we can delete this project folder:
            print("\nDeleting created BABS project folder...")
            proc_rm_project_folder = subprocess.run(
                ["rm", "-rf", self.project_root],
                stdout=subprocess.PIPE)
            proc_rm_project_folder.check_returncode()

        # confirm the BABS project has been removed:
        assert (not op.exists(self.project_root)), \
            "Created BABS project was not completely deleted!" \
            + " Path to created BABS project: '" + self.project_root + "'"

        print("\nCreated BABS project has been cleaned up.")

    def babs_check_setup(self, input_ds, flag_job_test):
        """
        This function validates the setups by babs-init.

        Parameters:
        --------------
        input_ds: class `Input_ds`
            information of input dataset(s)
        flag_job_test: bool
            Whether to submit and run a test job.
        """
        from .constants import CHECK_MARK

        babs_proj_config = read_yaml(self.config_path, if_filelock=True)

        print("Will check setups of BABS project located at: " + self.project_root)
        if flag_job_test:
            print("Will submit a test job for testing; will take longer time.")
        else:
            print("Did not request `--job-test`; will not submit a test job.")

        # Print out the saved configuration info: ----------------
        print("Below is the configuration information saved during `babs-init`"
              + " in file 'analysis/code/babs_proj_config.yaml':\n")
        f = open(op.join(self.analysis_path, "code/babs_proj_config.yaml"), 'r')
        file_contents = f.read()
        print(file_contents)
        f.close()

        # Check the project itself: ---------------------------
        print("Checking the BABS project itself...")
        # check if `analysis_path` exists
        #   (^^ though should be checked in `get_existing_babs_proj()` in cli.py)
        assert op.exists(self.analysis_path), \
            "Folder 'analysis' does not exist in this BABS project!" \
            + " Current path to analysis folder: " + self.analysis_path
        # if there is `analysis`:
        # update `analysis_datalad_handle`:
        if self.analysis_datalad_handle is None:
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
        print(CHECK_MARK + " All good!")

        # Check `analysis` datalad dataset: ----------------------
        print("\nCheck status of 'analysis' DataLad dataset...")
        # Are there anything unsaved? ref: CuBIDS function
        analysis_statuses = set([status['state'] for status in
                                self.analysis_datalad_handle.status(
                                    eval_subdataset_state='commit'
                                    # not to fully eval subdataset (e.g. input ds) status
                                    # otherwise, would take too long..
            )])
        # statuses should be all "clean", without anything else e.g., "modified":
        assert analysis_statuses == set(["clean"]), \
            "Analysis DataLad dataset's status is not clean." \
            + " There might be untracked or modified files in folder 'analysis'." \
            + " Please go to this directory: '" + self.analysis_path + "'\n" \
            + " and run `datalad status` to check what were changed," \
            + " then run `datalad save -m 'your message'`," \
            + " then run `datalad push --to input`;" \
            + " Finally, if you're sure there is no successful jobs finished, you can" \
            + " run `datalad push --to output`."
        print(CHECK_MARK + " All good!")

        # Check input dataset(s): ---------------------------
        print("\nChecking input dataset(s)...")
        # check if there is at least one folder in the `inputs/data` dir:
        temp_list = get_immediate_subdirectories(op.join(self.analysis_path, "inputs/data"))
        assert len(temp_list) > 0, \
            "There is no sub-directory (i.e., no input dataset) in 'inputs/data'!" \
            + " Full path to folder 'inputs/data': " + op.join(self.analysis_path, "inputs/data")

        # check each input ds:
        for i_ds in range(0, input_ds.num_ds):
            path_now_abs = input_ds.df["path_now_abs"][i_ds]

            # check if the dir of this input ds exists:
            assert op.exists(path_now_abs), \
                "The path to the cloned input dataset #" + str(i_ds + 1) \
                + " '" + input_ds.df["name"][i_ds] + "' does not exist: " \
                + path_now_abs

            # check if dir of input ds is a datalad dataset:
            assert op.exists(op.join(path_now_abs, ".datalad/config")), \
                "The input dataset #" + str(i_ds + 1) \
                + " '" + input_ds.df["name"][i_ds] + "' is not a valid DataLad dataset:" \
                + " There is no file '.datalad/config' in its directory: " + path_now_abs

            # ROADMAP: check if input dataset ID saved in YAML file
            #           (not saved yet, also need to add to Input_ds class too)
            #           = that in `.gitmodules` in cloned ds
            #   However, It's pretty unlikely that someone changes inputs/data on their own
            #       if they're using BABS

        print(CHECK_MARK + " All good!")

        # Check container datalad dataset: ---------------------------
        print("\nChecking container datalad dataset...")
        folder_container = op.join(self.analysis_path, "containers")
        container_name = babs_proj_config["container"]["name"]
        # assert it's a datalad ds in `containers` folder:
        assert op.exists(op.join(folder_container, ".datalad/config")), \
            "There is no containers DataLad dataset in folder: " + folder_container

        # ROADMAP: check if container dataset ID saved in YAML file (not saved yet)
        #           (not saved yet, probably better to add to Container class?)
        #           = that in `.gitmodules` in cloned ds
        #   However, It's pretty unlikely that someone changes it on their own
        #       if they're using BABS

        # no action now; when `babs-init`, has done `Container.sanity_check()`
        #               to make sure the container named `container_name` exists.
        print(CHECK_MARK + " All good!")

        # Check `analysis/code`: ---------------------------------
        print("\nChecking `analysis/code/` folder...")
        # folder `analysis/code` should exist:
        assert op.exists(op.join(self.analysis_path, "code")), \
            "Folder 'code' does not exist in 'analysis' folder!"

        # assert the list of files in the `code` folder,
        #   and bash files should be executable:
        list_files_code = [
            "babs_proj_config.yaml",
            container_name + "_zip.sh",
            "participant_job.sh",
            "submit_job_template.yaml"
            ]
        if self.type_session == "single-ses":
            list_files_code.append("sub_final_inclu.csv")
        else:
            list_files_code.append("sub_ses_final_inclu.csv")

        for temp_filename in list_files_code:
            temp_fn = op.join(self.analysis_path, "code", temp_filename)
            # the file should exist:
            assert op.isfile(temp_fn), \
                "Required file '" + temp_filename + "' does not exist" \
                + " in 'analysis/code' folder in this BABS project!"
            # check if bash files are executable:
            if op.splitext(temp_fn)[1] == ".sh":   # extension is '.sh':
                assert os.access(temp_fn, os.X_OK), \
                    "This code file should be executable: " + temp_fn
        print(CHECK_MARK + " All good!")

        # Check input and output RIA: ----------------------
        print("\nChecking input and output RIA...")

        # check if they are siblings of `analysis`:
        print("\tDatalad dataset `analysis`'s siblings:")
        analysis_siblings = self.analysis_datalad_handle.siblings(action='query')
        # get the actual `output_ria_data_dir`;
        #   the one in `self` attr is directly got from `analysis` remote,
        #   so should not use that here.
        # output_ria:
        actual_output_ria_data_dir = os.readlink(
            op.join(self.output_ria_path, "alias/data"))   # get the symlink of `alias/data`
        assert op.exists(actual_output_ria_data_dir)    # make sure this exists
        # get '000/0000-0000-0000-0000':
        data_foldername = op.join(
            op.basename(op.dirname(actual_output_ria_data_dir)),
            op.basename(actual_output_ria_data_dir))
        # input_ria:
        actual_input_ria_data_dir = op.join(self.input_ria_path, data_foldername)
        assert op.exists(actual_input_ria_data_dir)    # make sure this exists

        if_found_sibling_input = False
        if_found_sibling_output = False
        for i_sibling in range(0, len(analysis_siblings)):
            the_sibling = analysis_siblings[i_sibling]
            if the_sibling["name"] == "output":   # output ria:
                if_found_sibling_output = True
                assert the_sibling["url"] == actual_output_ria_data_dir, \
                    "The `analysis` datalad dataset's sibling 'output' url does not match" \
                    + " the path to the output RIA." \
                    + " Former = " + the_sibling["url"] + ";" \
                    + " Latter = " + actual_output_ria_data_dir
            if the_sibling["name"] == "input":   # input ria:
                if_found_sibling_input = True
                assert the_sibling["url"] == actual_input_ria_data_dir, \
                    "The `analysis` datalad dataset's sibling 'input' url does not match" \
                    + " the path to the input RIA." \
                    + " Former = " + the_sibling["url"] + ";" \
                    + " Latter = " + actual_input_ria_data_dir
        if not if_found_sibling_input:
            raise Exception("Did not find a sibling of 'analysis' DataLad dataset"
                            + " that's called 'input'. There may be something wrong when"
                            + " setting up input RIA!")
        if not if_found_sibling_output:
            raise Exception("Did not find a sibling of 'analysis' DataLad dataset"
                            + " that's called 'output'. There may be something wrong when"
                            + " setting up output RIA!")

        # output_ria_datalad_handle = dlapi.Dataset(self.output_ria_data_dir)

        # check if the current commit in `analysis` has been pushed to RIA:
        #   i.e., if commit hash are matched:
        # analysis' commit hash:
        proc_hash_analysis = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.analysis_path,
            stdout=subprocess.PIPE)
        proc_hash_analysis.check_returncode()
        hash_analysis = proc_hash_analysis.stdout.decode('utf-8').replace("\n", "")

        # input ria's commit hash:
        proc_hash_input_ria = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=actual_input_ria_data_dir,   # using the actual one we just got
            stdout=subprocess.PIPE)
        proc_hash_input_ria.check_returncode()
        hash_input_ria = proc_hash_input_ria.stdout.decode('utf-8').replace("\n", "")
        assert hash_analysis == hash_input_ria, \
            "The hash of current commit of `analysis` datalad dataset does not match" \
            + " with that of input RIA." \
            + " Former = " + hash_analysis + ";" \
            + " Latter = " + hash_input_ria + "." + "\n" \
            + "It might be because that latest commits in" \
            + " `analysis` were not pushed to input RIA." \
            + " Try running this command at directory '" + self.analysis_path + "': \n" \
            + "$ datalad push --to input"

        # output ria's commit hash:
        proc_hash_output_ria = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=actual_output_ria_data_dir,   # using the actual one we just got
            stdout=subprocess.PIPE)
        proc_hash_output_ria.check_returncode()
        hash_output_ria = proc_hash_output_ria.stdout.decode('utf-8').replace("\n", "")
        # only throw out a warning if not matched, as after there is branch in output RIA,
        #   not recommend to push updates from analysis to output RIA:
        if hash_analysis != hash_output_ria:
            flag_warning_output_ria = True
            warnings.warn(
                "The hash of current commit of `analysis` datalad dataset does not match"
                + " with that of output RIA."
                + " Former = " + hash_analysis + ";"
                + " Latter = " + hash_output_ria + ".\n"
                + "It might be because that latest commits in"
                + " `analysis` were not pushed to output RIA.\n"
                + "If there are already successful job(s) finished, please do NOT push updates"
                + " from `analysis` to output RIA.\n"
                + "If you're sure there is no successful job finished, you may try running"
                + " this command at directory '" + self.analysis_path + "': \n"
                + "$ datalad push --to output"
                )
        else:
            flag_warning_output_ria = False

        if flag_warning_output_ria:
            print("There is warning for output RIA - Please check it out!"
                  " Else in input and output RIA is good.")
        else:
            print(CHECK_MARK + " All good!")

        # Submit a test job (if requested) --------------------------------
        if not flag_job_test:
            print("\nNot to submit a test job as it's not requested."
                  + " We recommend running a test job with `--job-test` if you haven't done so;"
                  + " It will gather setup information in the designated environment"
                  + " and will make sure jobs can finish successfully on current cluster.")
            print("\n`babs-check-setup` was successful! ")
        else:
            print("\nSubmitting a test job, will take a while to finish...")
            print("Although the script will be submitted to the cluster to run,"
                  " this job will not run the BIDS App;"
                  " instead, this test job will gather setup information"
                  " in the designated environment"
                  " and will make sure jobs can finish successfully on current cluster.")

            _, job_id_str, log_filename = submit_one_test_job(self.analysis_path)
            log_fn = op.join(self.analysis_path, "logs", log_filename)  # abs path
            o_fn = log_fn.replace(".*", ".o")
            # write this information in a YAML file:
            fn_test_job_info = op.join(self.analysis_path, "code/check_setup",
                                       "test_job_info.yaml")
            if op.exists(fn_test_job_info):
                os.remove(fn_test_job_info)  # remove it

            test_job_info_file = open(fn_test_job_info, "w")
            test_job_info_file.write("# Information of submitted test job:\n")
            test_job_info_file.write("job_id: '" + job_id_str + "'\n")
            test_job_info_file.write("log_filename: '" + log_filename + "'\n")

            test_job_info_file.close()

            # check job status every 1 min:
            flag_done = False   # whether job is out of queue (True)
            flag_success_test_job = False  # whether job was successfully finished (True)
            print("Will check the test job's status every 1 min...")
            while not flag_done:
                # wait for 1 min:
                time.sleep(60)   # Sleep for 60 seconds

                # check the job status
                df_all_job_status = request_all_job_status()
                d_now_str = str(datetime.now())
                to_print = d_now_str + ": "
                if job_id_str in df_all_job_status.index.to_list():
                    # ^^ if `df` is empty, `.index.to_list()` will return []
                    # if the job is still in the queue:
                    # state_category = df_all_job_status.at[job_id_str, '@state']
                    state_code = df_all_job_status.at[job_id_str, 'state']
                    # ^^ column `@state`: 'running' or 'pending'

                    # print some information:
                    if state_code == "r":
                        to_print += "Test job is running (`r`)..."
                    elif state_code == "qw":
                        to_print += "Test job is pending (`qw`)..."
                    elif state_code == "eqw":
                        to_print += "Test job is stalled (`eqw`)..."

                else:   # the job is not in queue:
                    flag_done = True
                    # get the last line of the log file:
                    last_line = get_last_line(o_fn).replace("\n", "")
                    # check if it's "SUCCESS":
                    if last_line == "SUCCESS":
                        flag_success_test_job = True
                        to_print += "Test job is successfully finished!"
                    else:   # failed:
                        flag_success_test_job = False
                        to_print += "Test job was not successfully finished"
                        to_print += " and is currently out of queue."
                        to_print += " Last line of stdout log file: '" + last_line + "'."
                        to_print += " Path to the log file: " + log_fn
                print(to_print)

            if not flag_success_test_job:   # failed
                raise Exception(
                    "\nThere is something wrong probably in the setups."
                    + " Please check the log files"
                    + " and the `--container_config_yaml_file`"
                    + " provided in `babs-init`!"
                )
            else:   # flag_success_test_job == True:
                # go thru `code/check_setup/check_env.yaml`: check if anything wrong:
                fn_check_env_yaml = op.join(self.analysis_path, "code/check_setup",
                                            "check_env.yaml")
                flag_writable, flag_all_installed = print_versions_from_yaml(fn_check_env_yaml)
                if not flag_writable:
                    raise Exception(
                        "The designated workspace is not writable!"
                        + " Please change it in the YAML file"
                        + " used in `babs-init --container-config-yaml-file`,"
                        + " then rerun `babs-init` with updated YAML file.")
                    # NOTE: ^^ currently this is not aligned with YAML file sections;
                    # this will make more sense after adding section of workspace path in YAML file
                if not flag_all_installed:
                    raise Exception(
                        "Some required package(s) were not installed"
                        + " in the designated environment!"
                        + " Please install them in the designated environment,"
                        + " or change the designated environment you hope to use"
                        + " in `--container-config-yaml-file` and rerun `babs-init`!")

                print("Please check if above versions are the ones you hope to use!"
                      + " If not, please change the version in the designated environment,"
                      + " or change the designated environment you hope to use"
                      + " in `--container-config-yaml-file` and rerun `babs-init`.")
                print(CHECK_MARK + " All good in test job!")
                print("\n`babs-check-setup` was successful! ")

        if flag_warning_output_ria:
            print("\nPlease check out the warning for output RIA!")

    def babs_submit(self, count=1, df_job_specified=None):
        """
        This function submits jobs and prints out job status.

        Parameters:
        -------------------
        count: int
            number of jobs to be submitted
            default: 1
            negative value: to submit all jobs
        df_job_specified: pd.DataFrame or None
            list of specified job(s) to submit.
            columns: 'sub_id' (and 'ses_id', if multi-ses)
            If `--job` was not specified in `babs-submit`, it will be None.
        """

        count_report_progress = 10
        # ^^ if `j_count` is several times of `count_report_progress`, report progress

        # update `analysis_datalad_handle`:
        if self.analysis_datalad_handle is None:
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)

        # `create_job_status_csv(self)` has been called in `babs_status()`
        #   in `cli.py`

        # Load the csv file
        lock_path = self.job_status_path_abs + ".lock"
        lock = FileLock(lock_path)

        j_count = 0

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                df_job = read_job_status_csv(self.job_status_path_abs)
                df_job_updated = df_job.copy()

                # See if user has specified list of jobs to submit:
                if df_job_specified is not None:
                    print("Will only submit specified jobs...")
                    for j_job in range(0, df_job_specified.shape[0]):
                        # find the index in the full `df_job`:
                        if self.type_session == "single-ses":
                            sub = df_job_specified.at[j_job, 'sub_id']
                            ses = None
                            temp = df_job['sub_id'] == sub
                        elif self.type_session == "multi-ses":
                            sub = df_job_specified.at[j_job, 'sub_id']
                            ses = df_job_specified.at[j_job, 'ses_id']
                            temp = (df_job['sub_id'] == sub) & \
                                (df_job['ses_id'] == ses)

                        i_job = df_job.index[temp].to_list()
                        # # sanity check: there should only be one `i_job`:
                        # #   ^^ can be removed as done in `core_functions.py`
                        # assert_msg = "There are duplications in `job_status.csv`" \
                        #     + " for " + sub
                        # if self.type_session == "multi-ses":
                        #     assert_msg += ", " + ses
                        # assert len(i_job) == 1, assert_msg + "!"
                        i_job = i_job[0]   # take the element out of the list

                        # check if the job has already been submitted:
                        if not df_job["has_submitted"][i_job]:  # to run
                            job_id, _, log_filename = submit_one_job(self.analysis_path,
                                                                     self.type_session,
                                                                     sub, ses)

                            # assign into `df_job_updated`:
                            df_job_updated.at[i_job, "job_id"] = job_id
                            df_job_updated.at[i_job, "log_filename"] = log_filename

                            # update the status:
                            df_job_updated.at[i_job, "has_submitted"] = True
                            # reset fields:
                            df_job_updated.at[i_job, "is_failed"] = np.nan
                            # probably not necessary to reset:
                            df_job_updated.at[i_job, "job_state_category"] = np.nan
                            df_job_updated.at[i_job, "job_state_code"] = np.nan
                            df_job_updated.at[i_job, "duration"] = np.nan
                        else:
                            to_print = "The job for " + sub
                            if self.type_session == "multi-ses":
                                to_print += ", " + ses
                            to_print += " has already been submitted," \
                                + " so it won't be submitted again." \
                                + " If you want to resubmit it," \
                                + " please use `babs-status --resubmit`"
                            print(to_print)

                else:    # did not specify jobs to submit,
                    #   so submit by order in full list `df_job`, max = `count`:
                    # Check if there is still jobs to submit:
                    total_has_submitted = int(df_job["has_submitted"].sum())
                    if total_has_submitted == df_job.shape[0]:   # all submitted
                        print("All jobs have already been submitted. "
                              + "Use `babs-status` to check job status.")
                    else:
                        # Check which row has not been submitted:
                        for i_job in range(0, df_job.shape[0]):
                            if not df_job["has_submitted"][i_job]:  # to run
                                # ^^ type is bool (`numpy.bool_`), so use `if a:` or `if not a:`
                                # print(df_job["sub_id"][i_job] + "_" + df_job["ses_id"][i_job])

                                # Submit a job:
                                if self.type_session == "single-ses":
                                    sub = df_job.at[i_job, "sub_id"]
                                    ses = None
                                else:   # multi-ses
                                    sub = df_job.at[i_job, "sub_id"]
                                    ses = df_job.at[i_job, "ses_id"]

                                job_id, _, log_filename = \
                                    submit_one_job(self.analysis_path,
                                                   self.type_session,
                                                   sub, ses)

                                # assign into `df_job_updated`:
                                df_job_updated.at[i_job, "job_id"] = job_id
                                df_job_updated.at[i_job, "log_filename"] = log_filename

                                # update the status:
                                df_job_updated.at[i_job, "has_submitted"] = True
                                # reset fields:
                                df_job_updated.at[i_job, "is_failed"] = np.nan
                                # probably not necessary to reset:
                                df_job_updated.at[i_job, "job_state_category"] = np.nan
                                df_job_updated.at[i_job, "job_state_code"] = np.nan
                                df_job_updated.at[i_job, "duration"] = np.nan

                                # print(df_job_updated)

                                j_count += 1
                                # if it's several times of `count_report_progress`:
                                if j_count % count_report_progress == 0:
                                    print('So far ' + str(j_count) + ' jobs have been submitted.')

                                if j_count == count:
                                    break

                        # babs-submit is only responsible for submitting jobs that haven't run yet

                with pd.option_context('display.max_rows', None,
                                       'display.max_columns', None,
                                       'display.width', 120):   # default is 80 characters...
                    # ^^ print all the columns and rows (with returns)
                    print(df_job_updated.head(6))   # only first several rows

                # save updated df:
                df_job_updated.to_csv(self.job_status_path_abs, index=False)

                # here, the job status was not checked, so message from `report_job_status()`
                #   based on current df is not trustable:
                # # Report the job status:
                # report_job_status(df_job_updated)

        except Timeout:   # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print("Another instance of this application currently holds the lock.")

    def babs_status(self, flags_resubmit,
                    df_resubmit_job_specific=None, reckless=False,
                    container_config_yaml_file=None,
                    job_account=False):
        """
        This function checks job status and resubmit jobs if requested.

        Parameters:
        -------------
        flags_resubmit: list
            Under what condition to perform job resubmit.
            Element choices are: 'failed', 'pending', 'stalled'.
        df_resubmit_job_specific: pd.DataFrame or None
            list of specified job(s) to resubmit, requested by `--resubmit-job`
            columns: 'sub_id' (and 'ses_id', if multi-ses)
            if `--resubmit-job` was not specified in `babs-status`, it will be None.
        reckless: bool
            Whether to resubmit jobs listed in `df_resubmit_job_specific`,
            even they're done or running.
            This is used when `--resubmit-job`
        container_config_yaml_file: str or None
            Path to a YAML file that contains the configurations
            of how to run the BIDS App container.
            It may include 'alert_log_messages' section
            to be used by babs-status.
        job_account: bool
            Whether to account failed jobs (e.g., using `qacct` for SGE),
            which may take some time.
            This step will be skipped if `--resubmit failed` was requested.
        """

        # `create_job_status_csv(self)` has been called in `babs_status()`
        #   in `cli.py`

        # Load the csv file
        lock_path = self.job_status_path_abs + ".lock"
        lock = FileLock(lock_path)

        # Prepare for checking alert messages in log files:
        #   get the pre-defined alert messages:
        config_msg_alert = get_config_msg_alert(container_config_yaml_file)

        # Get username, if `--job-account` is requested:
        username_lowercase = get_username()

        # Get the list of branches in output RIA:
        proc_git_branch_all = subprocess.run(
            ["git", "branch", "-a"],
            cwd=self.output_ria_data_dir,
            stdout=subprocess.PIPE
        )
        proc_git_branch_all.check_returncode()
        msg = proc_git_branch_all.stdout.decode('utf-8')
        list_branches = msg.split()

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                df_job = read_job_status_csv(self.job_status_path_abs)
                df_job_updated = df_job.copy()

                # Get all jobs' status:
                df_all_job_status = request_all_job_status()

                # For jobs that have been submitted but not successful yet:
                # Update job status, and resubmit if requested:
                # get the list of jobs submitted, but `is_done` is not True:
                temp = (df_job['has_submitted']) & (~df_job['is_done'])
                list_index_job_tocheck = df_job.index[temp].tolist()
                for i_job in list_index_job_tocheck:
                    # Get basic information for this job:
                    job_id = df_job.at[i_job, "job_id"]
                    job_id_str = str(job_id)
                    log_filename = df_job.at[i_job, "log_filename"]  # with "*"
                    log_fn = op.join(self.analysis_path, "logs", log_filename)  # abs path
                    o_fn = log_fn.replace(".*", ".o")

                    # did_resubmit = False   # reset: did not resubmit this job

                    if self.type_session == "single-ses":
                        sub = df_job.at[i_job, "sub_id"]
                        ses = None
                        branchname = "job-" + job_id_str + "-" + sub
                        # e.g., job-00000-sub-01
                    elif self.type_session == "multi-ses":
                        sub = df_job.at[i_job, "sub_id"]
                        ses = df_job.at[i_job, "ses_id"]
                        branchname = "job-" + job_id_str + "-" + sub + "-" + ses
                        # e.g., job-00000-sub-01-ses-B

                    # Check if resubmission of this job is requested:
                    if_request_resubmit_this_job = False
                    if df_resubmit_job_specific is not None:
                        if self.type_session == "single-ses":
                            temp = df_resubmit_job_specific['sub_id'] == sub
                        elif self.type_session == "multi-ses":
                            temp = (df_resubmit_job_specific['sub_id'] == sub) & \
                                (df_resubmit_job_specific['ses_id'] == ses)

                        if any(temp):   # any matched; `temp` is pd.Series of True or False
                            if_request_resubmit_this_job = True
                            # print("debugging purpose: request to resubmit job: " + sub + ", " + ses)
                            # ^^ only for multi-ses!

                    # Update the "last_line_stdout_file":
                    df_job_updated.at[i_job, "last_line_stdout_file"] = \
                        get_last_line(o_fn)

                    # Check if any alert message in log files for this job:
                    # NOTE: in theory can skip failed jobs in previous round,
                    #       but making assigning variables hard; so not to skip
                    #       if df_job.at[i_job, "is_failed"] is not True:    # np.nan or False
                    alert_message_in_log_files, if_no_alert_in_log = \
                        get_alert_message_in_log_files(config_msg_alert, log_fn)
                    # ^^ the function will handle even if `config_msg_alert=None`
                    df_job_updated.at[i_job, "alert_message"] = \
                        alert_message_in_log_files

                    # Check if there is a branch in output RIA:
                    #   check if branch name of current job is in the list of all branches:
                    if branchname in list_branches:
                        # found the branch:
                        df_job_updated.at[i_job, "is_done"] = True
                        # reset/update:
                        df_job_updated.at[i_job, "job_state_category"] = np.nan
                        df_job_updated.at[i_job, "job_state_code"] = np.nan
                        df_job_updated.at[i_job, "duration"] = np.nan
                        #   ROADMAP: ^^ get duration via `qacct`
                        #       (though qacct may not be accurate)
                        df_job_updated.at[i_job, "is_failed"] = False

                        # check if echoed "SUCCESS":
                        # TODO ^^

                    else:   # did not find the branch
                        # Check the job status:
                        if job_id_str in df_all_job_status.index.to_list():
                            # ^^ if `df` is empty, `.index.to_list()` will return []
                            state_category = df_all_job_status.at[job_id_str, '@state']
                            state_code = df_all_job_status.at[job_id_str, 'state']
                            # ^^ column `@state`: 'running' or 'pending'

                            if state_code == "r":
                                # Check if resubmit is requested:
                                if if_request_resubmit_this_job & (not reckless):
                                    # requested resubmit, but without `reckless`: print msg
                                    to_print = "Although resubmit for job: " + sub
                                    if self.type_session == "multi-ses":
                                        to_print += ", " + ses
                                    to_print += " was requested, as this job is running," \
                                        + " and `--reckless` was not specified, BABS won't" \
                                        + " resubmit this job."
                                    warnings.warn(to_print)

                                if if_request_resubmit_this_job & reckless:  # force to resubmit:
                                    # Resubmit:
                                    # did_resubmit = True
                                    # print a message:
                                    to_print = "Resubmit job for " + sub
                                    if self.type_session == "multi-ses":
                                        to_print += ", " + ses
                                    to_print += ", although it was running," \
                                        + " resubmit for this job was requested" \
                                        + " and `--reckless` was specified."
                                    print(to_print)

                                    # kill original one
                                    proc_kill = subprocess.run(
                                        ["qdel", job_id_str],
                                        stdout=subprocess.PIPE
                                    )
                                    proc_kill.check_returncode()
                                    # submit new one:
                                    job_id_updated, _, log_filename = \
                                        submit_one_job(self.analysis_path,
                                                       self.type_session,
                                                       sub, ses)
                                    # update fields:
                                    df_job_updated.at[i_job, "job_id"] = job_id_updated
                                    df_job_updated.at[i_job, "log_filename"] = log_filename
                                    df_job_updated.at[i_job, "job_state_category"] = np.nan
                                    df_job_updated.at[i_job, "job_state_code"] = np.nan
                                    df_job_updated.at[i_job, "duration"] = np.nan
                                    df_job_updated.at[i_job, "is_failed"] = np.nan
                                    df_job_updated.at[i_job, "last_line_stdout_file"] = np.nan
                                    df_job_updated.at[i_job, "alert_message"] = np.nan
                                    df_job_updated.at[i_job, "job_account"] = np.nan

                                else:   # just let it run:
                                    df_job_updated.at[i_job, "job_state_category"] = state_category
                                    df_job_updated.at[i_job, "job_state_code"] = state_code
                                    # get the duration:
                                    duration = calcu_runtime(
                                        df_all_job_status.at[job_id_str, "JAT_start_time"])
                                    df_job_updated.at[i_job, "duration"] = duration

                                    # do nothing else, just wait

                            elif state_code == "qw":
                                if ('pending' in flags_resubmit) or (if_request_resubmit_this_job):
                                    # Resubmit:
                                    # did_resubmit = True
                                    # print a message:
                                    to_print = "Resubmit job for " + sub
                                    if self.type_session == "multi-ses":
                                        to_print += ", " + ses
                                    to_print += ", as it was pending and resubmit was requested."
                                    print(to_print)

                                    # kill original one
                                    proc_kill = subprocess.run(
                                        ["qdel", job_id_str],
                                        stdout=subprocess.PIPE
                                    )
                                    proc_kill.check_returncode()
                                    # submit new one:
                                    job_id_updated, _, log_filename = \
                                        submit_one_job(self.analysis_path,
                                                       self.type_session,
                                                       sub, ses)
                                    # update fields:
                                    df_job_updated.at[i_job, "job_id"] = job_id_updated
                                    df_job_updated.at[i_job, "log_filename"] = log_filename
                                    df_job_updated.at[i_job, "job_state_category"] = np.nan
                                    df_job_updated.at[i_job, "job_state_code"] = np.nan
                                    df_job_updated.at[i_job, "duration"] = np.nan
                                    df_job_updated.at[i_job, "is_failed"] = np.nan
                                    df_job_updated.at[i_job, "last_line_stdout_file"] = np.nan
                                    df_job_updated.at[i_job, "alert_message"] = np.nan
                                    df_job_updated.at[i_job, "job_account"] = np.nan

                                else:   # not to resubmit:
                                    # update fields:
                                    df_job_updated.at[i_job, "job_state_category"] = state_category
                                    df_job_updated.at[i_job, "job_state_code"] = state_code

                            elif state_code == "eqw":
                                if ('stalled' in flags_resubmit) or (if_request_resubmit_this_job):
                                    # Resubmit:
                                    # did_resubmit = True
                                    # print a message:
                                    to_print = "Resubmit job for " + sub
                                    if self.type_session == "multi-ses":
                                        to_print += ", " + ses
                                    to_print += ", as it was stalled and resubmit was requested."
                                    print(to_print)

                                    # kill original one
                                    proc_kill = subprocess.run(
                                        ["qdel", job_id_str],
                                        stdout=subprocess.PIPE
                                    )
                                    proc_kill.check_returncode()
                                    # submit new one:
                                    job_id_updated, _, log_filename = \
                                        submit_one_job(self.analysis_path,
                                                       self.type_session,
                                                       sub, ses)
                                    # update fields:
                                    df_job_updated.at[i_job, "job_id"] = job_id_updated
                                    df_job_updated.at[i_job, "log_filename"] = log_filename
                                    df_job_updated.at[i_job, "job_state_category"] = np.nan
                                    df_job_updated.at[i_job, "job_state_code"] = np.nan
                                    df_job_updated.at[i_job, "duration"] = np.nan
                                    df_job_updated.at[i_job, "is_failed"] = np.nan
                                    df_job_updated.at[i_job, "last_line_stdout_file"] = np.nan
                                    df_job_updated.at[i_job, "alert_message"] = np.nan
                                    df_job_updated.at[i_job, "job_account"] = np.nan
                                else:   # not to resubmit:
                                    # update fields:
                                    df_job_updated.at[i_job, "job_state_category"] = state_category
                                    df_job_updated.at[i_job, "job_state_code"] = state_code

                        else:   # did not find in `df_all_job_status`, i.e., job queue
                            # probably error
                            df_job_updated.at[i_job, "is_failed"] = True
                            # reset:
                            df_job_updated.at[i_job, "job_state_category"] = np.nan
                            df_job_updated.at[i_job, "job_state_code"] = np.nan
                            df_job_updated.at[i_job, "duration"] = np.nan
                            # ROADMAP: ^^ get duration via `qacct`

                            # check the log file:
                            # TODO ^^
                            # TODO: assign error category in df; also print it out

                            # resubmit if requested:
                            if ("failed" in flags_resubmit) or (if_request_resubmit_this_job):
                                # Resubmit:
                                # did_resubmit = True
                                # print a message:
                                to_print = "Resubmit job for " + sub
                                if self.type_session == "multi-ses":
                                    to_print += ", " + ses
                                to_print += ", as it is failed and resubmit was requested."
                                print(to_print)

                                # no need to kill original one!
                                #   As it already failed and out of job queue...

                                # submit new one:
                                job_id_updated, _, log_filename = \
                                    submit_one_job(self.analysis_path,
                                                   self.type_session,
                                                   sub, ses)

                                # update fields:
                                df_job_updated.at[i_job, "job_id"] = job_id_updated
                                df_job_updated.at[i_job, "log_filename"] = log_filename
                                df_job_updated.at[i_job, "is_failed"] = np.nan
                                df_job_updated.at[i_job, "last_line_stdout_file"] = np.nan
                                df_job_updated.at[i_job, "alert_message"] = np.nan
                                df_job_updated.at[i_job, "job_account"] = np.nan
                                # reset of `job_state_*` have been done - see above

                            else:  # resubmit 'error' was not requested:
                                # If `--job-account` is requested:
                                if job_account & if_no_alert_in_log:
                                    # if `--job-account` is requested, and there is no alert
                                    #   message found in log files:
                                    job_name = log_filename.split(".*")[0]
                                    msg_job_account = \
                                        check_job_account(job_id_str, job_name, username_lowercase)
                                    df_job_updated.at[i_job, "job_account"] = msg_job_account
                # Done: submitted jobs that not 'is_done'

                # For 'is_done' jobs in previous round:
                temp = (df_job['has_submitted']) & (df_job['is_done'])
                list_index_job_is_done = df_job.index[temp].tolist()
                for i_job in list_index_job_is_done:
                    # Get basic information for this job:
                    job_id = df_job.at[i_job, "job_id"]
                    job_id_str = str(job_id)
                    log_filename = df_job.at[i_job, "log_filename"]  # with "*"
                    log_fn = op.join(self.analysis_path, "logs", log_filename)  # abs path
                    o_fn = log_fn.replace(".*", ".o")

                    if self.type_session == "single-ses":
                        sub = df_job.at[i_job, "sub_id"]
                        ses = None
                        branchname = "job-" + job_id_str + "-" + sub
                        # e.g., job-00000-sub-01
                    elif self.type_session == "multi-ses":
                        sub = df_job.at[i_job, "sub_id"]
                        ses = df_job.at[i_job, "ses_id"]
                        branchname = "job-" + job_id_str + "-" + sub + "-" + ses
                        # e.g., job-00000-sub-01-ses-B

                    # Check if resubmission of this job is requested:
                    if_request_resubmit_this_job = False
                    if df_resubmit_job_specific is not None:
                        if self.type_session == "single-ses":
                            temp = df_resubmit_job_specific['sub_id'] == sub
                        elif self.type_session == "multi-ses":
                            temp = (df_resubmit_job_specific['sub_id'] == sub) & \
                                (df_resubmit_job_specific['ses_id'] == ses)

                        if any(temp):   # any matched; `temp` is pd.Series of True or False
                            if_request_resubmit_this_job = True
                            # print("debugging purpose: request to resubmit job:" + sub + ", " + ses)
                            # ^^ only for multi-ses

                    # if want to resubmit, but `--reckless` is NOT specified: print msg:
                    if if_request_resubmit_this_job & (not reckless):
                        to_print = "Although resubmit for job: " + sub
                        if self.type_session == "multi-ses":
                            to_print += ", " + ses
                        to_print += " was requested, as this job is done," \
                            + " and `--reckless` was not specified, BABS won't" \
                            + " resubmit this job."
                        warnings.warn(to_print)

                    # if resubmit is requested, and `--reckless` is specified:
                    if if_request_resubmit_this_job & reckless:
                        # Resubmit:
                        # did_resubmit = True
                        # print a message:
                        to_print = "Resubmit job for " + sub
                        if self.type_session == "multi-ses":
                            to_print += ", " + ses
                        to_print += ", although it is done," \
                            + " resubmit for this job was requested" \
                            + " and `--reckless` was specified."
                        print(to_print)

                        # TODO: delete the original branch?

                        # kill original one
                        proc_kill = subprocess.run(
                            ["qdel", job_id_str],
                            stdout=subprocess.PIPE
                        )
                        proc_kill.check_returncode()
                        # submit new one:
                        job_id_updated, _, log_filename = \
                            submit_one_job(self.analysis_path,
                                           self.type_session,
                                           sub, ses)
                        # update fields:
                        df_job_updated.at[i_job, "job_id"] = job_id_updated
                        df_job_updated.at[i_job, "log_filename"] = log_filename
                        df_job_updated.at[i_job, "job_state_category"] = np.nan
                        df_job_updated.at[i_job, "job_state_code"] = np.nan
                        df_job_updated.at[i_job, "duration"] = np.nan
                        df_job_updated.at[i_job, "is_done"] = False
                        df_job_updated.at[i_job, "is_failed"] = np.nan
                        df_job_updated.at[i_job, "last_line_stdout_file"] = np.nan
                        df_job_updated.at[i_job, "alert_message"] = np.nan
                        df_job_updated.at[i_job, "job_account"] = np.nan

                    else:    # did not request resubmit, or `--reckless` is None:
                        # just perform normal stuff for a successful job:
                        # Update the "last_line_stdout_file":
                        df_job_updated.at[i_job, "last_line_stdout_file"] = \
                            get_last_line(o_fn)
                        # Check if any alert message in log files for this job:
                        #   this is to update `alert_message` in case user changes configs in yaml
                        alert_message_in_log_files, if_no_alert_in_log = \
                            get_alert_message_in_log_files(config_msg_alert, log_fn)
                        # ^^ the function will handle even if `config_msg_alert=None`
                        df_job_updated.at[i_job, "alert_message"] = \
                            alert_message_in_log_files
                # Done: 'is_done' jobs.

                # For jobs that haven't been submitted yet:
                #   just to throw out warnings if `--resubmit-job` was requested...
                if df_resubmit_job_specific is not None:
                    # only keep those not submitted:
                    df_job_not_submitted = df_job[~df_job["has_submitted"]]
                    # only keep columns of `sub_id` and `ses_id`:
                    if self.type_session == "single-ses":
                        df_job_not_submitted_slim = df_job_not_submitted[["sub_id"]]
                    elif self.type_session == "multi-ses":
                        df_job_not_submitted_slim = df_job_not_submitted[["sub_id", "ses_id"]]

                    # check if `--resubmit-job` was requested for any these jobs:
                    df_intersection = df_resubmit_job_specific.merge(df_job_not_submitted_slim)
                    if len(df_intersection) > 0:
                        warnings.warn("Jobs for some of the subjects (and sessions) requested in"
                                      + " `--resubmit-job` haven't been submitted yet."
                                      + " Please use `babs-submit` first.")
                # Done: jobs that haven't submitted yet

                # Finish up `babs-status`:
                # # print updated df:
                # print("")
                # with pd.option_context('display.max_rows', None,
                #                        'display.max_columns', None,
                #                        'display.width', 120):   # default is 80 characters...
                #     # ^^ print all columns and rows (with returns)
                #     print(df_job_updated.head(6))

                # save updated df:
                df_job_updated.to_csv(self.job_status_path_abs, index=False)

                # Report the job status:
                report_job_status(df_job_updated, self.analysis_path, config_msg_alert)

        except Timeout:   # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print("Another instance of this application currently holds the lock.")

    def babs_merge(self, chunk_size, trial_run):
        """
        This function merges results and provenance from all successfully finished jobs.

        Parameters:
        ---------------
        chunk_size: int
            Number of branches in a chunk when merging at a time.
        trial_run: bool
            Whether to run as a trial run which won't push the merging actions back to output RIA.
            This option should only be used by developers for testing purpose.
        """
        if_any_warning = False
        self.wtf_key_info()   # get `self.analysis_dataset_id`
        # path to `merge_ds`:
        merge_ds_path = op.join(self.project_root, "merge_ds")

        if op.exists(merge_ds_path):
            raise Exception("Folder 'merge_ds' already exists. `babs-merge` won't proceed."
                            " If you're sure you want to rerun `babs-merge`,"
                            " please remove this folder before you rerun `babs-merge`."
                            " Path to 'merge_ds': '" + merge_ds_path + "'. ")

        # Define (potential) text files:
        #   in 'merge_ds/code' folder
        #   as `merge_ds` should not exist at the moment,
        #   no need to check existence/remove these files.
        # define path to text file of invalid job list exists:
        fn_list_invalid_jobs = op.join(merge_ds_path, "code",
                                       "list_invalid_job_when_merging.txt")
        # define path to text file of files with missing content:
        fn_list_content_missing = op.join(merge_ds_path, "code",
                                          "list_content_missing.txt")
        # define path to printed messages from `git annex fsck`:
        # ^^ this will be absolutely used if `babs-merge` does not fail:
        fn_msg_fsck = op.join(merge_ds_path, "code",
                              "log_git_annex_fsck.txt")

        # Clone output RIA to `merge_ds`:
        print("Cloning output RIA to 'merge_ds'...")
        # get the path to output RIA:
        #   'ria+file:///path/to/BABS_project/output_ria#0000000-000-xxx-xxxxxxxx'
        output_ria_source = self.output_ria_url \
            + "#" + self.analysis_dataset_id
        # clone: `datalad clone ${outputsource} merge_ds`
        dlapi.clone(source=output_ria_source,
                    path=merge_ds_path)

        # List all branches in output RIA:
        print("\nListing all branches in output RIA...")
        # get all branches:
        proc_git_branch_all = subprocess.run(
            ["git", "branch", "-a"],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE
        )
        proc_git_branch_all.check_returncode()
        msg = proc_git_branch_all.stdout.decode('utf-8')
        list_branches_all = msg.split()

        # only keep those having pattern `job-`:
        list_branches_jobs = [ele for ele in list_branches_all if "job-" in ele]
        # ^^ ["remotes/origin/job-xxx", "remotes/origin/job-xxx", ...]
        #   it's normal and necessary to have `remotes/origin`. See notes below.
        # NOTE: our original bash script for merging: `merge_outputs_postscript.sh`:
        #   run `git branch -a | grep job- | sort` in `merge_ds`
        #   --> should get all branches whose names contain `*job-*`
        #   e.g., `remotes/origin/job-xxx`   # as run in `merge_ds`
        # Should not run in output RIA data dir, as you'll get branches without `remotes/origin`
        #   --> raise error of "merge: job-xxxx - not something we can merge"
        #   i.e., cannot find the branch to merge.

        if len(list_branches_jobs) == 0:
            raise Exception("There is no successfully finished job yet."
                            " Please run `babs-submit` first.")

        # Find all valid branches (i.e., those with results --> have different SHASUM):
        print("\nFinding all valid job branches to merge...")
        # get default branch's name: master or main:
        #   `git remote show origin | sed -n '/HEAD branch/s/.*: //p'`
        proc_git_remote_show_origin = subprocess.run(
            ["git", "remote", "show", 'origin'],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE)
        proc_git_remote_show_origin.check_returncode()
        msg = proc_git_remote_show_origin.stdout.decode('utf-8')
        # e.g., '... HEAD branch: master\n....': search between 'HEAD branch: ' and '\n':
        temp = re.search('HEAD branch: '+'(.+?)'+'\n', msg)
        if temp:   # not empty:
            default_branch_name = temp.group(1)   # what's between those two keywords
            # another way: `default_branch_name = msg.split("HEAD branch: ")[1].split("\n")[0]`
        else:
            raise Exception("There is no HEAD branch in output RIA!")
        print("Git default branch's name of output RIA is: '" + default_branch_name + "'")

        # get current git commit SHASUM before merging as a reference:
        git_ref, _ = get_git_show_ref_shasum(default_branch_name, merge_ds_path)

        # check if each job branch has a new commit
        #   that's different from current git commit SHASUM (`git_ref`):
        list_branches_no_results = []
        list_branches_with_results = []
        for branch_job in list_branches_jobs:
            # get the job's `git show-ref`:
            git_ref_branch_job, _ = \
                get_git_show_ref_shasum(branch_job, merge_ds_path)
            if git_ref_branch_job == git_ref:   # no new commit --> no results in this branch
                list_branches_no_results.append(branch_job)
            else:   # has results:
                list_branches_with_results.append(branch_job)

        # check if there is any valid job (with results):
        if len(list_branches_with_results) == 0:   # empty:
            raise Exception("There is no job branch in output RIA that has results yet,"
                            + " i.e., there is no successfully finished job yet."
                            + " Please run `babs-submit` first.")

        # check if there is invalid job (without results):
        if len(list_branches_no_results) > 0:   # not empty
            # save to a text file:
            #   note: this file has been removed at the beginning of babs_merge() if it existed)
            if_any_warning = True
            warnings.warn("There are invalid job branch(es) in output RIA,"
                          + " and these job(s) do not have results."
                          + " The list of such invalid jobs will be saved to"
                          + " the following text file: '" + fn_list_invalid_jobs + "'."
                          + " Please review it.")
            with open(fn_list_invalid_jobs, "w") as f:
                f.write('\n'.join(list_branches_no_results))
                f.write("\n")   # add a new line at the end
        # NOTE to developers: when testing ^^:
        #   You can `git branch job-test` in `output_ria/000/000-000` to make a fake branch
        #       that has the same SHASUM as master branch's
        #       then you should see above warning.
        #   However, if you finish running `babs-merge`, this branch `job-test` will have
        #       a *different* SHASUM from master's, making it a "valid" job now.
        #   To continue testing above warning, you need to delete this branch:
        #       `git branch --delete job-test` in `output_ria/000/000-000`
        #       then re-create a new one: `git branch job-test`

        # Merge valid branches chunk by chunk:
        print("\nMerging valid job branches chunk by chunk...")
        print("Total number of job branches to merge = " + str(len(list_branches_with_results)))
        print("Chunk size (number of job branches per chunk) = " + str(chunk_size))
        # turn the list into numpy array:
        arr = np.asarray(list_branches_with_results)
        # ^^ e.g., array([1, 7, 0, 6, 2, 5, 6])   # but with `dtype='<U24'`
        # split into several chunks:
        num_chunks = ceildiv(len(arr), chunk_size)
        print("--> Number of chunks = " + str(num_chunks))
        all_chunks = np.array_split(arr, num_chunks)
        # ^^ e.g., [array([1, 7, 0]), array([6, 2]), array([5, 6])]

        # iterate across chunks:
        for i_chunk in range(0, num_chunks):
            print("Merging chunk #" + str(i_chunk+1)
                  + " (total of " + str(num_chunks) + " chunk[s] to merge)...")
            the_chunk = all_chunks[i_chunk]  # e.g., array(['a', 'b', 'c'])
            # join all branches in this chunk:
            joined_by_space = " ".join(the_chunk)   # e.g., 'a b c'
            # command to run:
            commit_msg = "merge results chunk " \
                + str(i_chunk+1) + "/" + str(num_chunks)
            # ^^ okay to not to be quoted,
            #   as in `subprocess.run` this is a separate element in the `cmd` list
            cmd = ["git", "merge", "-m", commit_msg] \
                + joined_by_space.split(" ")   # split by space
            proc_git_merge = subprocess.run(
                cmd,
                cwd=merge_ds_path,
                stdout=subprocess.PIPE)
            proc_git_merge.check_returncode()
            print(proc_git_merge.stdout.decode('utf-8'))

        # Push merging actions back to output RIA:
        if not trial_run:
            print("\nPushing merging actions to output RIA...")
            # `git push`:
            proc_git_push = subprocess.run(
                ["git", "push"],
                cwd=merge_ds_path, stdout=subprocess.PIPE)
            proc_git_push.check_returncode()
            print(proc_git_push.stdout.decode('utf-8'))

            # Get file availability information: which is very important!
            # `git annex fsck --fast -f output-storage`:
            #   `git annex fsck` = file system check
            #   We've done the git merge of the symlinks of the files,
            #   now we need to match the symlinks with the data content in `output-storage`.
            #   `--fast`: just use the existing MD5, not to re-create a new one
            proc_git_annex_fsck = subprocess.run(
                ["git", "annex", "fsck", "--fast", "-f", "output-storage"],
                cwd=merge_ds_path, stdout=subprocess.PIPE)
            proc_git_annex_fsck.check_returncode()
            # if printing the returned msg,
            #   will be a long list of "fsck xxx.zip (fixing location log) ok"
            #   or "fsck xxx.zip ok"
            # instead, save it into a text file:
            with open(fn_msg_fsck, "w") as f:
                f.write("# Below are printed messages from"
                        " `git annex fsck --fast -f output-storage`:\n\n")
                f.write(proc_git_annex_fsck.stdout.decode('utf-8'))
                f.write("\n")
            # now we can delete `proc_git_annex_fsck` to save memory:
            del proc_git_annex_fsck

            # Double check: there should not be file content that's not in `output-storage`:
            #   This should not print anything - we never has this error before
            # `git annex find --not --in output-storage`
            proc_git_annex_find_missing = subprocess.run(
                ["git", "annex", "find", "--not", "--in", "output-storage"],
                cwd=merge_ds_path, stdout=subprocess.PIPE)
            proc_git_annex_find_missing.check_returncode()
            msg = proc_git_annex_find_missing.stdout.decode('utf-8')
            # `msg` should be empty:
            if msg != '':   # if not empty:
                # save into a file:
                with open(fn_list_content_missing, "w") as f:
                    f.write(msg)
                    f.write("\n")
                raise Exception("Unable to find file content for some file(s)."
                                + " The information has been saved to this text file: '"
                                + fn_list_content_missing + "'.")

            # `git annex dead here`:
            #   stop tracking clone `merge_ds`,
            #   i.e., not to get data from this `merge_ds` sibling:
            proc_git_annex_dead_here = subprocess.run(
                ["git", "annex", "dead", "here"],
                cwd=merge_ds_path, stdout=subprocess.PIPE)
            proc_git_annex_dead_here.check_returncode()
            print(proc_git_annex_dead_here.stdout.decode('utf-8'))

            # Final `datalad push` to output RIA:
            # `datalad push --data nothing`:
            #   pushing to `git` branch in output RIA: has done with `git push`;
            #   pushing to `git-annex` branch in output RIA: hasn't done after `git annex fsck`
            #   `--data nothing`: don't transfer data from this local annex `merge_ds`
            proc_datalad_push = subprocess.run(
                ["datalad", "push", "--data", "nothing"],
                cwd=merge_ds_path, stdout=subprocess.PIPE)
            proc_datalad_push.check_returncode()
            print(proc_datalad_push.stdout.decode('utf-8'))

            # Done:
            if if_any_warning:
                print("\n`babs-merge` has finished but had warning(s)!"
                      " Please check out the warning message(s) above!")
            else:
                print("\n`babs-merge` was successful!")

        else:    # `--trial-run` is on:
            print("")    # new empty line
            warnings.warn("`--trial-run` was requested,"
                          + " not to push merging actions to output RIA.")
            print("\n`babs-merge` did not fully finish yet!")

    def babs_unzip(container_config_yaml_file):
        """
        This function unzips results and extract desired files.
        This is done in 3 steps:
        1. Generate scripts used by `babs-unzip`
        2. Run scripts to unzip data
        3. Merge all branches of unzipping

        Parameters:
        --------------
        config: dict
            loaded container config yaml file
        """

        # ====================================================
        # Generate scripts used by `babs-unzip`
        # ====================================================

        # Prepare input_ds_unzip:
        # Call `babs_bootstrap()`:
        #   !!!! using babs_proj_unzip, instead current `self`!!!

        print("TODO")

        # ====================================================
        # Run scripts to unzip data
        # ====================================================

        # ====================================================
        # Merge all branches of unzipping
        # ====================================================


class Input_ds():
    """This class is for input dataset(s)"""

    def __init__(self, input_cli):
        """
        This is to initialize `Input_ds` class.

        Parameters:
        --------------
        input_cli: nested list of strings
            see CLI `babs-init --input` for more

        Attributes:
        --------------
        df: pandas DataFrame
            includes necessary information:
            - name: str: a name the user gives
            - path_in: str: the path to the input ds
            - path_now_rel: the path to where the input ds is cloned, relative to `analysis` folder
            - path_now_abs: the absolute path to the input ds
            - path_data_rel: the path to where the input data (for a sub or a ses) is,
                relative to `analysis` folder.
                If it's zipped ds, `path_data_rel` = `path_now_rel`/`name`,
                i.e., extra layer of folder got from unzipping
                If it's an unzipped ds, `path_data_rel` = `path_now_rel`
            - is_zipped: True or False, is the input data zipped or not
        num_ds: int
            number of input dataset(s)
        initial_inclu_df: pandas DataFrame or None
            got by method `get_initial_inclu_df()`, based on `list_sub_file`
            Assign `None` for now, before calling that method
            See that method for more.
        """

        # About input dataset(s): ------------------------
        # create an empty pandas DataFrame:
        self.df = pd.DataFrame(None,
                               index=list(range(0, len(input_cli))),
                               columns=['name', 'path_in', 'path_now_rel',
                                        'path_now_abs', 'path_data_rel',
                                        'is_zipped'])

        # number of dataset(s):
        self.num_ds = self.df.shape[0]   # number of rows in `df`

        # change the `input_cli` from nested list to a pandas dataframe:
        for i in range(0, self.num_ds):
            self.df["name"][i] = input_cli[i][0]
            self.df["path_in"][i] = input_cli[i][1]
            self.df["path_now_rel"][i] = op.join("inputs/data", self.df["name"][i])

        # sanity check: input ds names should not be identical:
        if len(set(self.df["name"].tolist())) != self.num_ds:  # length of the set = number of ds
            raise Exception("There are identical names in input datasets' names!")

        # Initialize other attributes: ------------------------------
        self.initial_inclu_df = None

    def get_initial_inclu_df(self, list_sub_file, type_session):
        """
        Define attribute `initial_inclu_df`, a pandas DataFrame or None
            based on `list_sub_file`
            single-session data: column of 'sub_id';
            multi-session data: columns of 'sub_id' and 'ses_id'

        Parameters:
        ----------------
        list_sub_file: str or None
            Path to the CSV file that lists the subject (and sessions) to analyze;
            or `None` if that CLI flag was not specified.
            single-ses data: column of 'sub_id';
            multi-ses data: columns of 'sub_id' and 'ses_id'
        type_session: str
            "multi-ses" or "single-ses"
        """
        # Get the initial included sub/ses list from `list_sub_file` CSV:
        if list_sub_file is None:  # if not to specify that flag in CLI, it'll be `None`
            self.initial_inclu_df = None
        else:
            if op.exists(list_sub_file) is False:    # does not exist:
                raise Exception("`list_sub_file` does not exists! Please check: "
                                + list_sub_file)
            else:   # exists:
                self.initial_inclu_df = pd.read_csv(list_sub_file)
                self.validate_initial_inclu_df(type_session)

    def validate_initial_inclu_df(self, type_session):
        # Sanity check: there are expected column(s):
        if "sub_id" not in list(self.initial_inclu_df.columns):
            raise Exception("There is no 'sub_id' column in `list_sub_file`!")
        if type_session == "multi-ses":
            if "ses_id" not in list(self.initial_inclu_df.columns):
                raise Exception("There is no 'ses_id' column in `list_sub_file`!"
                                + " It is expected as this is a multi-session dataset.")

        # Sanity check: no repeated sub (or sessions):
        if type_session == "single-ses":
            # there should only be one occurrence per sub:
            if len(set(self.initial_inclu_df["sub_id"])) != \
                    len(self.initial_inclu_df["sub_id"]):
                raise Exception("There are repeated 'sub_id' in"
                                + "`list_sub_file`!")
        elif type_session == "multi-ses":
            # there should not be repeated combinations of `sub_id` and `ses_id`:
            after_dropping = \
                self.initial_inclu_df.drop_duplicates(
                    subset=['sub_id', 'ses_id'], keep='first')
            # ^^ remove duplications in specific cols, and keep the first occurrence
            if after_dropping.shape[0] < self.initial_inclu_df.shape[0]:
                print("Combinations of 'sub_id' and 'ses_id' in some rows are duplicated."
                      + " Will only keep the first occurrence...")
                self.initial_inclu_df = after_dropping

        # Sort:
        if type_session == "single-ses":
            # sort:
            self.initial_inclu_df = \
                self.initial_inclu_df.sort_values(by=['sub_id'])
            # reset the index, and remove the additional colume:
            self.initial_inclu_df = \
                self.initial_inclu_df.reset_index().drop(columns=['index'])
        elif type_session == "multi-ses":
            self.initial_inclu_df = \
                self.initial_inclu_df.sort_values(by=['sub_id', 'ses_id'])
            self.initial_inclu_df = \
                self.initial_inclu_df.reset_index().drop(columns=['index'])

    def assign_path_now_abs(self, analysis_path):
        """
        This is the assign the absolute path to input dataset

        Parameters:
        --------------
        analysis_path: str
            absolute path to the `analysis` folder.
        """

        for i in range(0, self.num_ds):
            self.df["path_now_abs"][i] = op.join(analysis_path,
                                                 self.df["path_now_rel"][i])

    def check_if_zipped(self):
        """
        This is to check if each input dataset is zipped, and assign `path_data_rel`.
        If it's a zipped ds: `path_data_rel` = `path_now_rel`/`name`,
                i.e., extra layer of folder got from unzipping
        If it's an unzipped ds, `path_data_rel` = `path_now_rel`
        """

        # Determine if it's a zipped dataset, for each input ds:
        for i_ds in range(0, self.num_ds):
            temp_list = glob.glob(self.df["path_now_abs"][i_ds] + "/sub-*")
            count_zip = 0
            count_dir = 0
            for i_temp in range(0, len(temp_list)):
                if op.isdir(temp_list[i_temp]):
                    count_dir += 1
                elif temp_list[i_temp][-4:] == ".zip":
                    count_zip += 1

            if (count_zip > 0) & (count_dir == 0):   # all are zip files:
                self.df["is_zipped"][i_ds] = True
                print("input dataset '" + self.df["name"][i_ds] + "'"
                      + " is considered as a zipped dataset.")
            elif (count_dir > 0) & (count_zip == 0):   # all are directories:
                self.df["is_zipped"][i_ds] = False
                print("input dataset '" + self.df["name"][i_ds] + "'"
                      + " is considered as an unzipped dataset.")
            elif (count_zip > 0) & (count_dir > 0):  # detect both:
                self.df["is_zipped"][i_ds] = True   # consider as zipped
                print("input dataset '" + self.df["name"][i_ds] + "'"
                      + " has both zipped files and unzipped folders;"
                      + " thus it's considered as a zipped dataset.")
            else:   # did not detect any of them...
                raise Exception("BABS did not detect any folder or zip file of `sub-*`"
                                + " in input dataset '" + self.df["name"][i_ds] + "'.")

        # Assign `path_data_rel`:
        for i_ds in range(0, self.num_ds):
            if self.df["is_zipped"][i_ds] is True:   # zipped ds
                self.df["path_data_rel"][i_ds] = op.join(self.df["path_now_rel"][i_ds],
                                                         self.df["name"][i_ds])
            else:   # unzipped ds:
                self.df["path_data_rel"][i_ds] = self.df["path_now_rel"][i_ds]

    def check_validity_zipped_input_dataset(self, type_session):
        """
        This is to perform two sanity checks on each zipped input dataset:
        1) sanity check on the zip filename:
            if multi-ses: sub-*_ses-*_<input_ds_name>*.zip
            if single-ses: sub-*_<input_ds_name>*.zip
        2) sanity check to make sure the 1st level folder in zipfile
            is consistent to this input dataset's name;
            Only checks the first zipfile.

        Parameters:
        ------------
        type_session: str
            "multi-ses" or "single-ses"
        container_name: str
            Name of the container
        """

        if True in list(self.df["is_zipped"]):  # there is at least one dataset is zipped
            print("Performing sanity check for any zipped input dataset..."
                  " Getting example zip file(s) to check...")
        for i_ds in range(0, self.num_ds):
            if self.df["is_zipped"][i_ds] is True:   # zipped ds
                # Sanity check #1: zip filename: ----------------------------------
                if type_session == "multi-ses":
                    # check if matches the pattern of `sub-*_ses-*_<input_ds_name>*.zip`:
                    temp_list = glob.glob(self.df["path_now_abs"][i_ds]
                                          + "/sub-*_ses-*_" + self.df["name"][i_ds] + "*.zip")
                    temp_list = sorted(temp_list)   # sort by name
                    if len(temp_list) == 0:    # did not find any matched
                        raise Exception("In zipped input dataset #" + str(i_ds + 1)
                                        + " (named '" + self.df["name"][i_ds] + "'),"
                                        + " no zip filename matches the pattern of"
                                        + " 'sub-*_ses-*_"
                                        + self.df["name"][i_ds] + "*.zip'")
                elif type_session == "single-ses":
                    temp_list = glob.glob(self.df["path_now_abs"][i_ds]
                                          + "/sub-*_" + self.df["name"][i_ds] + "*.zip")
                    temp_list = sorted(temp_list)   # sort by name
                    if len(temp_list) == 0:    # did not find any matched
                        raise Exception("In zipped input dataset #" + str(i_ds + 1)
                                        + " (named '" + self.df["name"][i_ds] + "'),"
                                        + " no zip filename matches the pattern of"
                                        + " 'sub-*_"
                                        + self.df["name"][i_ds] + "*.zip'")
                    # not to check below stuff anymore:
                    # # also check there should not be `_ses-*_`
                    # temp_list_2 = glob.glob(self.df["path_now_abs"][i_ds]
                    #                         + "/*_ses-*_*.zip")
                    # if len(temp_list_2) > 0:   # exists:
                    #     raise Exception("In zipped input dataset #" + str(i_ds + 1)
                    #                     + " (named '" + self.df["name"][i_ds] + "'),"
                    #                     + " as it's a single-ses dataset,"
                    #                     + " zip filename should not contain"
                    #                     + " '_ses-*_'")

                # Sanity check #2: foldername within zipped file: -------------------
                temp_zipfile = temp_list[0]   # try out the first zipfile
                temp_zipfilename = op.basename(temp_zipfile)
                dlapi.get(path=temp_zipfile, dataset=self.df["path_now_abs"][i_ds])
                # unzip to a temporary folder and get the foldername
                temp_unzip_to = tempfile.mkdtemp()
                shutil.unpack_archive(temp_zipfile, temp_unzip_to)
                list_unzip_foldernames = get_immediate_subdirectories(temp_unzip_to)
                # remove the temporary folder:
                shutil.rmtree(temp_unzip_to)
                # `datalad drop` the zipfile:
                dlapi.drop(path=temp_zipfile, dataset=self.df["path_now_abs"][i_ds])

                # check if there is folder named as ds's name:
                if self.df["name"][i_ds] not in list_unzip_foldernames:
                    warnings.warn("In input dataset #" + str(i_ds + 1)
                                  + " (named '" + self.df["name"][i_ds]
                                  + "'), there is no folder called '"
                                  + self.df["name"][i_ds] + "' in zipped input file '"
                                  + temp_zipfilename + "'. This may cause error"
                                  + " when running BIDS App for this subject/session")


class System():
    """This class is for cluster management system"""

    def __init__(self, system_type):
        """
        This is to initialize System class.

        Parameters:
        -------------
        system_type: str
            Type of the cluster management system.
            Options are: "sge" and "slurm"

        Attributes:
        -------------
        type: str
            Type of the cluster management system.
            Options are: "sge" and "slurm"
        dict: dict
            Guidance dict (loaded from `dict_cluster_systems.yaml`)
            for how to run this type of cluster.
        """
        # validate and assign to attribute `type`:
        self.type = validate_type_system(system_type)

        # get attribute `dict` - the guidance dict for how to run this type of cluster:
        self.get_dict()

    def get_dict(self):
        # location of current python script:
        #   `op.abspath()` is to make sure always returns abs path, regardless of python version
        #   ref: https://note.nkmk.me/en/python-script-file-path/
        __location__ = op.realpath(op.dirname(op.abspath(__file__)))

        fn_dict_cluster_systems_yaml = op.join(__location__, "dict_cluster_systems.yaml")
        with open(fn_dict_cluster_systems_yaml) as f:
            dict = yaml.load(f, Loader=yaml.FullLoader)
            # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`

        # sanity check:
        if self.type not in dict:
            raise Exception("There is no key called '" + self.type + "' in"
                            + " file `dict_cluster_systems.yaml`!")

        self.dict = dict[self.type]
        f.close()


class Container():
    """This class is for the BIDS App Container"""

    def __init__(self, container_ds, container_name, config_yaml_file):
        """
        This is to initialize Container class.

        Parameters:
        --------------
        container_ds: str
            The path to the container datalad dataset as the input of `babs-init`.
            This container datalad ds is prepared by the user.
        container_name: str
            The name of the container when adding to datalad dataset(e.g., `NAME` in
            `datalad containers-add NAME`),
             e.g., fmriprep-0-0-0
        config_yaml_file: str
            The YAML file that contains the configurations of how to run the container

        Attributes:
        --------------
        container_ds: str
            The path to the container datalad dataset as the input of `babs-init`.
            This container datalad ds is prepared by the user, not the cloned one.
        container_name: str
            The name of the container when adding to datalad dataset(e.g., `NAME` in
            `datalad containers-add NAME`),
             e.g., fmriprep-0-0-0
        config_yaml_file: str
            The YAML file that contains the configurations of how to run the container
            This is optional argument (of the CLI `babs-init`)
        config: dict
            The configurations regarding running the BIDS App on a cluster
            read from `config_yaml_file`.
        container_path_relToAnalysis: str
            The path to the container image saved in BABS project;
            this path is relative to `analysis` folder.
            e.g., `containers/.datalad/environments/fmriprep-0-0-0/image`
            This `image` could be a symlink (`op.islink()`, more likely for singularity container)
            or a folder (`op.isdir()`, more likely for docker container)
        """

        self.container_ds = container_ds
        self.container_name = container_name
        self.config_yaml_file = config_yaml_file

        # sanity check if `config_yaml_file` exists:
        if op.exists(self.config_yaml_file) is False:
            raise Exception("The yaml file of the container's configurations '"
                            + self.config_yaml_file + "' does not exist!")

        # read the container's config yaml file and get the `config`:
        self.read_container_config_yaml()

        self.container_path_relToAnalysis = op.join("containers", ".datalad", "environments",
                                                    self.container_name, "image")

    def sanity_check(self, analysis_path):
        """
        This is a sanity check to validate the cloned container ds.

        Parameters:
        ------------
        analysis_path: str
            Absolute path to the `analysis` folder in a BABS project.
        """
        # path to the symlink/folder `image`:
        container_path_abs = op.join(analysis_path, self.container_path_relToAnalysis)
        # e.g.:
        #   '/path/to/BABS_project/analysis/containers/.datalad/environments/container_name/image'

        # Sanity check: the path to `container_name` should exist in the cloned `container_ds`:
        # e.g., '/path/to/BABS_project/analysis/containers/.datalad/environments/container_name'
        assert op.exists(op.dirname(container_path_abs)), \
            "There is no valid image named '" + self.container_name \
            + "' in the provided container DataLad dataset!"

        # the 'image' symlink or folder should exist:
        assert op.exists(container_path_abs) or op.islink(container_path_abs), \
            "the folder 'image' of container DataLad dataset does not exist," \
            + " and there is no symlink called 'image' either;" \
            + " Path to 'image' in cloned container DataLad dataset should be: '" \
            + container_path_abs + "'."

    def read_container_config_yaml(self):
        """
        This is to get the config dict from `config_yaml_file`
        """
        with open(self.config_yaml_file) as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)
            # ^^ config is a dict; elements can be accessed by `config["key"]["sub-key"]`
        f.close()

    def generate_bash_run_bidsapp(self, bash_path, input_ds, type_session):
        """
        This is to generate a bash script that runs the BIDS App singularity image.

        Parameters:
        -------------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `Input_ds`
            input dataset(s) information
        type_session: str
            multi-ses or single-ses.

        Notes:
        --------------
        When writing `singularity run` part, each chunk to write should start with " \\" + "\n\t",
        meaning, starting with space, a backward slash, a return, and a tab.
        """
        from .constants import PATH_FS_LICENSE_IN_CONTAINER

        type_session = validate_type_session(type_session)
        output_foldername = "outputs"    # folername of BIDS App outputs

        # Check if the folder exist; if not, create it:
        bash_dir = op.dirname(bash_path)
        if not op.exists(bash_dir):
            os.makedirs(bash_dir)

        # check if `self.config` from the YAML file contains information we need:
        if "singularity_run" not in self.config:
            # sanity check: there should be only one input ds
            #   otherwise need to specify in this section:
            assert input_ds.num_ds == 1, \
                "Section 'singularity_run' is missing in the provided" \
                + " `container_config_yaml_file`. As there are more than one" \
                + " input dataset, you must include this section to specify" \
                + " to which argument that each input dataset will go."
            # if there is only one input ds, fine:
            print("Section 'singularity_run' was not included "
                  "in the `container_config_yaml_file`. ")
            cmd_singularity_flags = ""   # should be empty
            # Make sure other returned variables from `generate_cmd_singularityRun_from_config`
            #   also have values:
            # as "--fs-license-file" was not one of the value in `singularity_run` section:
            flag_fs_license = False
            path_fs_license = None
            # copied from `generate_cmd_singularityRun_from_config`:
            singuRun_input_dir = input_ds.df["path_data_rel"][0]
        else:
            # print("Generate singularity run command from `container_config_yaml_file`")
            # # contain \ for each key-value

            # read config from the yaml file:
            cmd_singularity_flags, flag_fs_license, path_fs_license, singuRun_input_dir = \
                generate_cmd_singularityRun_from_config(self.config, input_ds)

        print()

        # TODO: also corporate the `call-fmt` in `datalad containers-add`

        # Check if the bash file already exist:
        if op.exists(bash_path):
            os.remove(bash_path)  # remove it

        # Write into the bash file:
        bash_file = open(bash_path, "a")   # open in append mode

        bash_file.write("#!/bin/bash\n")
        bash_file.write("set -e -u -x\n")

        count_inputs_bash = 0
        bash_file.write('\nsubid="$1"\n')
        count_inputs_bash += 1

        if type_session == "multi-ses":
            # also have the input of `sesid`:
            bash_file.write('sesid="$2"\n')
            count_inputs_bash += 1

        # zip filename as input of bash file:
        for i_ds in range(0, input_ds.num_ds):
            if input_ds.df["is_zipped"][i_ds] is True:  # is zipped:
                count_inputs_bash += 1
                bash_file.write(input_ds.df["name"][i_ds].upper()
                                + '_ZIP="$' + str(count_inputs_bash) + '"\n')

        bash_file.write("\n")

        # Check if `--bids-filter-file "${filterfile}"` is needed:
        flag_filterfile = False
        if type_session == "multi-ses":
            if any(ele in self.container_name.lower() for ele in ["fmriprep", "qsiprep"]):
                # ^^ if the container_name contains `fmriprep` or `qsiprep`:
                # ^^ case insensitive (as have changed to lower case), accept "fMRIPrep-0-0-0"
                flag_filterfile = True

                # generate the command of generating the `$filterfile`,
                # i.e., `${sesid}_filter.json`:
                cmd_filterfile = generate_cmd_filterfile(self.container_name)
                bash_file.write(cmd_filterfile)

        # Check if any dataset is zipped; if so, add commands of unzipping:
        cmd_unzip_inputds = generate_cmd_unzip_inputds(input_ds, type_session)
        if len(cmd_unzip_inputds) > 0:   # not "":
            bash_file.write(cmd_unzip_inputds)

        # Other necessary commands for preparation:
        bash_file.write("\n")

        # Environment variables in container:
        # get environment variables to be injected into container and whose value to be bound:
        cmd_env_templateflow, templateflow_home, templateflow_in_container = \
            generate_cmd_set_envvar("TEMPLATEFLOW_HOME")

        # Write the head of the command `singularity run`:
        bash_file.write("mkdir -p ${PWD}/.git/tmp/wkdir\n")
        cmd_head_singularityRun = "singularity run --cleanenv"
        # binding:
        cmd_head_singularityRun += " \\" + "\n\t" + "-B ${PWD}"

        # check if `templateflow_home` needs to be bound:
        if templateflow_home is not None:
            # add `-B /path/to/templateflow_home:/TEMPLATEFLOW_HOME`:
            # for multiple bindings: multiple `-B` or separate path with comma (too long)
            cmd_head_singularityRun += " \\" + "\n\t" + "-B "
            cmd_head_singularityRun += templateflow_home + ":"
            cmd_head_singularityRun += templateflow_in_container
            # ^^ bind to dir in container

        # check if `freesurfer_home` needs to be bound:
        if flag_fs_license is True:
            # add `-B /path/to/license.txt:/SGLR/FREESURFER_HOME/license.txt`:
            cmd_head_singularityRun += " \\" + "\n\t" + "-B "
            cmd_head_singularityRun += path_fs_license + ":"
            cmd_head_singularityRun += PATH_FS_LICENSE_IN_CONTAINER

        # inject env variable into container:
        if templateflow_home is not None:
            # add `--env TEMPLATEFLOW_HOME=/TEMPLATEFLOW_HOME`:
            cmd_head_singularityRun += " \\" + "\n\t"
            cmd_head_singularityRun += cmd_env_templateflow

        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += self.container_path_relToAnalysis
        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += singuRun_input_dir  # inputs/data/<name>
        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += output_foldername   # output folder

        # currently all BIDS App support `participant` positional argu:
        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += "participant"  # at participant-level

        bash_file.write(cmd_head_singularityRun)

        # Write the named arguments + values:
        # add more arguments that are covered by BABS (instead of users):
        if flag_filterfile is True:
            # also needs a $filterfile flag:
            cmd_singularity_flags += " \\" + "\n\t"
            cmd_singularity_flags += '--bids-filter-file "${filterfile}"'  # <- TODO: test out!!

        cmd_singularity_flags += " \\" + "\n\t"
        cmd_singularity_flags += '--participant-label "${subid}"'   # standard argument in BIDS App

        bash_file.write(cmd_singularity_flags)
        bash_file.write("\n\n")

        print("Below is the generated `singularity run` command:")
        print(cmd_head_singularityRun + cmd_singularity_flags)

        # Zip:
        cmd_zip = generate_cmd_zipping_from_config(self.config, type_session, output_foldername)
        bash_file.write(cmd_zip)

        # Delete folders and files:
        """
        rm -rf prep .git/tmp/wkdir
        rm ${filterfile}
        """
        cmd_clean = "rm -rf " + output_foldername + " " + ".git/tmp/wkdir" + "\n"
        if flag_filterfile is True:
            cmd_clean += "rm ${filterfile}" + " \n"

        bash_file.write(cmd_clean)

        # Done generating `<containerName>_zip.sh`:
        bash_file.write("\n")
        bash_file.close()

        # Execute necessary commands:
        # change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ["chmod", "+x", bash_path],  # e.g., chmod +x code/fmriprep_zip.sh
            stdout=subprocess.PIPE
            )
        proc_chmod_bashfile.check_returncode()

    def generate_bash_participant_job(self, bash_path, input_ds, type_session,
                                      system):
        """
        This is to generate a bash script that runs jobs for each participant (or session).

        Parameters:
        -------------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `Input_ds`
            input dataset(s) information
        type_session: str
            "multi-ses" or "single-ses".
        system: class `System`
            information on cluster management system
        """

        # Sanity check:
        if type_session not in ["multi-ses", "single-ses"]:
            raise Exception("Invalid `type_session`: " + type_session)

        # Check if the bash file already exist:
        if op.exists(bash_path):
            os.remove(bash_path)  # remove it

        # Write into the bash file:
        bash_file = open(bash_path, "a")   # open in append mode

        bash_file.write("#!/bin/bash\n")

        # Cluster resources requesting:
        cmd_bashhead_resources = generate_bashhead_resources(system, self.config)
        bash_file.write(cmd_bashhead_resources)

        # Script preambles:
        cmd_script_preamble = generate_cmd_script_preamble(self.config)
        bash_file.write(cmd_script_preamble)

        # Change how this bash file is run:
        bash_file.write("\n# Fail whenever something is fishy,"
                        + " use -x to get verbose logfiles:\n")
        bash_file.write("set -e -u -x\n")

        # Inputs of the bash script:
        bash_file.write("\n")
        bash_file.write('dssource="$1"\t# i.e., `input_ria`\n')
        bash_file.write('pushgitremote="$2"\t# i.e., `output_ria`\n')
        bash_file.write('subid="$3"\n')

        if type_session == "multi-ses":
            # also have the input of `sesid`:
            bash_file.write('sesid="$4"\n')

        # Change path to a temporary job compute workspace:
        #   the path is based on what users provide in section 'job_compute_space' in YAML file:
        cmd_job_compute_space = generate_cmd_job_compute_space(self.config)
        bash_file.write(cmd_job_compute_space)

        # Setups: ---------------------------------------------------------------
        # set up the branch:
        bash_file.write("\n# Branch name (also used as temporary directory):\n")
        if system.type == "sge":
            varname_jobid = "JOB_ID"
        elif system.type == "slurm":
            varname_jobid = "SLURM_JOBID"

        if type_session == "multi-ses":
            bash_file.write('BRANCH="job-${' + varname_jobid + '}-${subid}-${sesid}"' + '\n')
        elif type_session == "single-ses":
            bash_file.write('BRANCH="job-${' + varname_jobid + '}-${subid}"' + '\n')

        bash_file.write('mkdir ${BRANCH}' + '\n')
        bash_file.write('cd ${BRANCH}' + '\n')

        # datalad clone the input ria:
        bash_file.write("\n# Clone the data from input RIA:\n")
        bash_file.write('datalad clone "${dssource}" ds' + "\n")
        bash_file.write("cd ds")

        # set up the result deposition:
        bash_file.write("\n# Register output RIA as remote for result deposition:\n")
        bash_file.write('git remote add outputstore "${pushgitremote}"' + "\n")
        # ^^ `git remote add <give a name> <folder where the remote is>`
        #   is to add a new remote to your git repo

        # set up a new branch:
        bash_file.write("\n# Create a new branch for this job's results:" + "\n")
        bash_file.write('git checkout -b "${BRANCH}"' + "\n")

        # Start of the application-specific code: ------------------------------

        # pull down input data (but don't retrieve the data content) and remove other sub's data:
        #   purpose of removing other sub's data: otherwise pybids would take
        #   extremely long time in large dataset due to lots of subjects
        bash_file.write(
            "\n# Pull down the input subject (or dataset) but don't retrieve data contents:\n")
        for i_ds in range(0, input_ds.num_ds):
            if input_ds.df["is_zipped"][i_ds] is False:   # unzipped ds:
                # seems regardless of multi-ses or not
                #   as for multi-ses, it might uses other ses's data e.g., anat?
                bash_file.write('datalad get -n "' + input_ds.df["path_now_rel"][i_ds]
                                + "/${subid}" + '"' + "\n")
                # ^^ `-n` means "Get (clone) a registered subdataset, but don’t retrieve data"
                #   here input ds is a sub-dataset of dataset `analysis`.
                # NOTE: not sure why `bootstrap-fmriprep-ingressed-fs.sh` uses:
                # `datalad get -n -r "inputs/data/BIDS/${subid}"`
                # that has `-r`? `-r` means "recursively" - is it for cases that each sub
                #   is a sub-dataset of `inputs/data/<name>`?
                # TODO: try out if adding `-r` still works?

                # remove other sub's data:
                bash_file.write("(cd " + input_ds.df["path_now_rel"][i_ds]
                                + " && rm -rf `find . -type d -name 'sub*'"
                                + " | grep -v $subid`" + ")" + "\n")
                """
                e.g.,:
                datalad get -n "inputs/data/<name>/${subid}"
                (cd inputs/data/<name> && rm -rf `find . -type d -name 'sub*' | grep -v $subid`)
                """
            else:    # zipped ds:
                bash_file.write('datalad get -n "'
                                + input_ds.df["path_now_rel"][i_ds]
                                + '"' + "\n")
                # e.g., `datalad get -n "inputs/data/freesurfer"`
                # ^^ should NOT only get specific zip file, as right now we need to
                #   get the list of all files, so that we can determine zipfilename later.

                # below is another version: using `*` instead of a specific file:
                # bash_file.write('datalad get -n "' + input_ds.df["path_now_rel"][i_ds]
                #                 + "/${subid}_*" + input_ds.df["name"][i_ds] + "*.zip"
                #                 + '"' + "\n")
                bash_file.write("(cd " + input_ds.df["path_now_rel"][i_ds]
                                + " && rm -f `ls sub-*.zip | grep -v ${subid}`"
                                + ")" + "\n")
                """
                e.g.,:
                datalad get -n "inputs/data/freesurfer/${subid}_*<name>*.zip"
                (cd inputs/data/<name> && rm -f `ls sub-*.zip | grep -v ${subid}`)
                """

        # determine the zip filename:
        cmd_determine_zipfilename = generate_cmd_determine_zipfilename(input_ds, type_session)
        bash_file.write(cmd_determine_zipfilename)

        # `datalad run`:
        bash_file.write("\n# datalad run:\n")
        cmd_datalad_run = generate_cmd_datalad_run(self, input_ds, type_session)
        bash_file.write(cmd_datalad_run)

        # Finish up:
        # push result file content to output RIA storage:
        bash_file.write("\n" + "# Push result file content to output RIA storage:\n")
        bash_file.write("datalad push --to output-storage" + "\n")
        # ^^: # `output-storage`: defined when start of bootstrap: `datalad create-sibling-ria`

        # push the output branch:
        bash_file.write("# Push the branch with provenance records:\n")
        bash_file.write("flock $DSLOCKFILE git push outputstore" + "\n")
        # ^^: `outputstore` was defined at the beginning of `participant_job.sh`
        # this push needs a global lock to prevent write conflicts - FAIRly big paper

        # Delete:
        bash_file.write("\necho 'Delete temporary directory:'" + "\n")
        bash_file.write("echo ${BRANCH}" + "\n")
        # each input dataset:
        for i_ds in range(0, input_ds.num_ds):
            bash_file.write("datalad drop -d " + input_ds.df["path_now_rel"][i_ds] + " -r"
                            + " --reckless availability"   # previous `--nocheck` (deprecated)
                            + " --reckless modification"
                            # ^^ previous `--if-dirty ignore` (deprecated)
                            + "\n")
            # e.g., datalad drop -d inputs/data/<name> -r
            # NOTE: our scripts sometimes also adds `--nocheck --if-dirty ignore`
            #   without it, `toybidsapp` with zipped ds as input was not okay (drop impossible)
            #   without it, `toybidsapp` with BIDS as input was fine

        # also `datalad drop` the current `ds` (clone of input RIA)?
        #   this includes dropping of images in `containers` dataset, and zipped output
        bash_file.write("datalad drop -r ."
                        + " --reckless availability"
                        + " --reckless modification"    # this is needed for zipped input ds
                        + "\n")
        # ^^ old scripts: datalad drop -r . --nocheck   # `--nocheck` is deprecated...

        bash_file.write("git annex dead here" + "\n")
        # ^^: as the data has been dropped, we don't want to be reminded of this

        # cd out of $BRANCH:
        bash_file.write("cd ../.." + "\n")
        bash_file.write("rm -rf $BRANCH" + "\n")

        # Done generating `participant_job.sh`:
        bash_file.write("\necho SUCCESS" + "\n")
        bash_file.close()

        # change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ["chmod", "+x", bash_path],  # e.g., chmod +x code/participant_job.sh
            stdout=subprocess.PIPE
            )
        proc_chmod_bashfile.check_returncode()

    def generate_bash_test_job(self, folder_check_setup,
                               system):
        """
        This is to generate two scripts that run a *test* job,
        which will be used by `babs-check-setup`.
        Scripts to generate:
        * `call_test_job.sh`    # just like `participant_job.sh`
        * `test_job.py`    # just like `container_zip.sh`

        Parameters:
        -------------
        folder_check_setup: str
            The path to folder `check_setup`; generated scripts will locate in this folder
        system: class `System`
            information on cluster management system
        """

        fn_call_test_job = op.join(folder_check_setup, "call_test_job.sh")
        fn_test_job = op.join(folder_check_setup, "test_job.py")
        # ==============================================================
        # Generate `call_test_job.sh`, similar to `participant_job.sh`
        # ==============================================================
        # Check if the bash file already exist:
        if op.exists(fn_call_test_job):
            os.remove(fn_call_test_job)  # remove it

        # Write into the bash file:
        bash_file = open(fn_call_test_job, "a")   # open in append mode

        bash_file.write("#!/bin/bash\n")

        # Cluster resources requesting:
        cmd_bashhead_resources = generate_bashhead_resources(system, self.config)
        bash_file.write(cmd_bashhead_resources)

        # Script preambles:
        cmd_script_preamble = generate_cmd_script_preamble(self.config)
        bash_file.write(cmd_script_preamble)

        # Where the analysis folder is:
        bash_file.write("path_check_setup=" + folder_check_setup + "\n")

        # Change how this bash file is run:
        bash_file.write("\n# Fail whenever something is fishy,"
                        + " use -x to get verbose logfiles:\n")
        bash_file.write("set -e -u -x\n")

        # NOTE: There is no input argument for this bash file.

        # Change path to a temporary job compute workspace:
        #   the path is based on what users provide in section 'job_compute_space' in YAML file:
        cmd_job_compute_space = generate_cmd_job_compute_space(self.config)
        bash_file.write(cmd_job_compute_space)

        # Call `test_job.py`:
        # get which python:
        bash_file.write("\n# Call `test_job.py`:\n")
        bash_file.write("which_python=`which python`\n")
        bash_file.write("current_pwd=${PWD}" + "\n")
        # call `test_job.py`:
        bash_file.write("echo 'Calling `test_job.py`...'\n")
        bash_file.write("${which_python} " + fn_test_job
                        + " --path-workspace ${current_pwd}"
                        + " --path-check-setup " + folder_check_setup + "\n")

        # Echo success:
        bash_file.write("\necho SUCCESS\n")

        proc_chmod_bashfile = subprocess.run(
            ["chmod", "+x", fn_call_test_job],  # e.g., chmod +x code/participant_job.sh
            stdout=subprocess.PIPE
            )
        proc_chmod_bashfile.check_returncode()

        # ==============================================================
        # Generate `test_job.py`, similar to `container_zip.sh`
        # ==============================================================
        # Check if the bash file already exist:
        if op.exists(fn_test_job):
            os.remove(fn_test_job)  # remove it

        # Copy the existing python script to this BABS project:
        # location of current python script:
        #   `op.abspath()` is to make sure always returns abs path, regardless of python version
        #   ref: https://note.nkmk.me/en/python-script-file-path/
        __location__ = op.realpath(op.dirname(op.abspath(__file__)))
        fn_from = op.join(__location__, "template_test_job.py")
        # copy:
        shutil.copy(fn_from, fn_test_job)

        # change the permission of this bash file:
        proc_chmod_pyfile = subprocess.run(
            ["chmod", "+x", fn_test_job],  # e.g., chmod +x code/participant_job.sh
            stdout=subprocess.PIPE
            )
        proc_chmod_pyfile.check_returncode()

    def generate_job_submit_template(self, yaml_path, input_ds, babs, system):
        """
        This is to generate a YAML file that serves as a template
        of job submission of one participant (or session).

        Parameters:
        -------------
        yaml_path: str
            The path to the yaml file to be generated. It should be in the `analysis/code` folder.
            It has several fields: 1) cmd_template; 2) job_name_template
        input_ds: class `Input_ds`
            input dataset(s) information
        babs: class `BABS`
            information about the BABS project
        system: class `System`
            information on cluster management system
        """

        # Section 1: Command for submitting the job: ---------------------------
        # Flags when submitting the job:
        if system.type == "sge":
            submit_head = "qsub -cwd"
            env_flags = "-v DSLOCKFILE=" + babs.analysis_path + "/.SGE_datalad_lock"
            eo_args = "-e " + babs.analysis_path + "/logs " \
                + "-o " + babs.analysis_path + "/logs"
        else:
            warnings.warn("not supporting systems other than sge...")

        # Check if the bash file already exist:
        if op.exists(yaml_path):
            os.remove(yaml_path)  # remove it

        # Write into the bash file:
        yaml_file = open(yaml_path, "a")   # open in append mode
        yaml_file.write("# '${sub_id}' and '${ses_id}' are placeholders." + "\n")

        # Variables to use:
        # `dssource`: Input RIA:
        dssource = babs.input_ria_url + "#" + babs.analysis_dataset_id
        # `pushgitremote`: Output RIA:
        pushgitremote = babs.output_ria_data_dir

        # Generate the command:
        #   several rows in the text file; in between, to insert sub and ses id.
        if babs.type_session == "single-ses":
            cmd = submit_head + " " + env_flags \
                + " -N " + self.container_name[0:3] + "_" + "${sub_id}"
            cmd += " " \
                + eo_args + " " \
                + babs.analysis_path + "/code/participant_job.sh" + " " \
                + dssource + " " \
                + pushgitremote + " " + "${sub_id}"

        elif babs.type_session == "multi-ses":
            cmd = submit_head + " " + env_flags \
                + " -N " + self.container_name[0:3] + "_" + "${sub_id}_${ses_id}"
            cmd += " " \
                + eo_args + " " \
                + babs.analysis_path + "/code/participant_job.sh" + " " \
                + dssource + " " \
                + pushgitremote + " " + "${sub_id} ${ses_id}"

        yaml_file.write("cmd_template: '" + cmd + "'" + "\n")

        # TODO: currently only support SGE.

        # Section 2: Job name: ---------------------------
        job_name = self.container_name[0:3] + "_" + "${sub_id}"
        if babs.type_session == "multi-ses":
            job_name += "_${ses_id}"

        yaml_file.write("job_name_template: '" + job_name + "'\n")

        yaml_file.close()

    def generate_test_job_submit_template(self, yaml_path, babs, system):
        """
        This is to generate a YAML file that serves as a template
        of *test* job submission, which will be used in `babs-check-setup`.

        Parameters:
        ------------
        yaml_path: str
            The path to the yaml file to be generated.
            It should be in the `analysis/code/check_setup` folder.
            It has several fields: 1) cmd_template; 2) job_name_template
        babs: class `BABS`
            information about the BABS project
        system: class `System`
            information on cluster management system
        """

        # Section 1: Command for submitting the job: ---------------------------
        # Flags when submitting the job:
        if system.type == "sge":
            submit_head = "qsub -cwd"
            env_flags = "-v DSLOCKFILE=" + babs.analysis_path + "/.SGE_datalad_lock"
            eo_args = "-e " + babs.analysis_path + "/logs " \
                + "-o " + babs.analysis_path + "/logs"
        else:
            warnings.warn("not supporting systems other than sge...")

        # Check if the bash file already exist:
        if op.exists(yaml_path):
            os.remove(yaml_path)  # remove it

        # Write into the bash file:
        yaml_file = open(yaml_path, "a")   # open in append mode

        # Generate the command:
        cmd = submit_head + " " + env_flags \
            + " -N " + self.container_name[0:3] + "_" + "test_job"
        cmd += " " \
            + eo_args + " " \
            + babs.analysis_path + "/code/check_setup/call_test_job.sh"

        yaml_file.write("cmd_template: '" + cmd + "'" + "\n")

        # TODO: currently only support SGE.

        # Section 2: Job name: ---------------------------
        job_name = self.container_name[0:3] + "_" + "test_job"

        yaml_file.write("job_name_template: '" + job_name + "'\n")

        yaml_file.close()
