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

import datalad.api as dlapi
from datalad_container.find_container import find_container_

from babs.utils import (get_immediate_subdirectories,
                        check_validity_unzipped_input_dataset, generate_cmd_envvar,
                        generate_cmd_filterfile,
                        generate_cmd_singularityRun_from_config, generate_cmd_unzip_inputds,
                        generate_cmd_zipping_from_config,
                        validate_type_session,
                        validate_type_system,
                        generate_bashhead_resources,
                        generate_cmd_script_preamble,
                        generate_cmd_datalad_run,
                        generate_cmd_determine_zipfilename,
                        get_list_sub_ses,
                        submit_one_job,
                        create_job_status_csv,
                        read_job_status_csv,
                        report_job_status,
                        request_job_status,
                        request_all_job_status,
                        calcu_runtime)

# import pandas as pd


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

        # entry_pwd = os.getcwd()

        # ==============================================================
        # Initialize:
        # ==============================================================

        # Make a directory of project_root:
        if not op.exists(self.project_root):
            os.makedirs(self.project_root)

        # Create `analysis` folder:
        print("\nCreating `analysis` folder (also a datalad dataset)...")
        if op.exists(self.analysis_path):
            # check if it's a datalad dataset:
            try:
                _ = dlapi.status(dataset=self.analysis_path)
                # TODO: we should apply `datalad update`
                #   in case there is any updates from the original place
                print("Folder 'analysis' exists in the `project_root` and is a datalad dataset; "
                      "not to re-create it.")
                self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
            except:
                raise Exception("Folder 'analysis' exists but is not a datalad dataset. "
                                "Please remove this folder and rerun.")
        else:
            self.analysis_datalad_handle = dlapi.create(self.analysis_path,
                                                        cfg_proc='yoda',
                                                        annex=True)

        # create `babs_proj_config.yaml` file:
        print("Save configurations of BABS project in a yaml file ...")
        print("Path to this yaml file will be: 'analysis/code/babs_proj_config.yaml'")
        babs_proj_config_file = open(self.config_path, "w")
        babs_proj_config_file.write("type_session: '"
                                    + self.type_session + "'\n")
        babs_proj_config_file.write("type_system: '"
                                    + self.type_system + "'\n")
        babs_proj_config_file.write("input_ds:\n")   # input dataset's name(s)
        for i_ds in range(0, input_ds.num_ds):
            babs_proj_config_file.write("  - " + input_ds.df["name"][i_ds] + "\n")

        babs_proj_config_file.close()
        self.datalad_save(path="code/babs_proj_config.yaml",
                          message="Save configurations of this BABS project")

        # Create output RIA sibling:
        print("\nCreating output and input RIA...")
        if op.exists(self.output_ria_path):
            pass
            # TODO: add sanity check: if the input_ria and output_ria have been created,
            # check if they are analysis's siblings + they are ria siblings;
            # then, update them with datalad push from anlaysis folder
        else:
            self.analysis_datalad_handle.create_sibling_ria(name="output",
                                                            url=self.output_ria_url,
                                                            new_store_ok=True)
        # ^ ref: in python environment:
            # import datalad; help(datalad.distributed.create_sibling_ria)
            # sometimes, have to first `temp = dlapi.Dataset("/path/to/analysis/folder")`,
            # then `help(temp.create_sibling_ria)`, you can stop here,
            # or now you can help(datalad.distributed.create_sibling_ria)
            # seems there is no docs online?
        # source code:
            # https://github.com/datalad/datalad/blob/master/datalad/distributed/create_sibling_ria.py

        # Get some key information re: DataLad dataset `analysis`,
        # after creating output RIA:
        self.wtf_key_info()

        # Create input RIA sibling:
        if op.exists(self.input_ria_path):
            pass
            # TODO: add sanity check: if the input_ria and output_ria have been created,
            # check if they are analysis's siblings + they are ria siblings;
            # then, update them with datalad push from anlaysis folder
        else:
            self.analysis_datalad_handle.create_sibling_ria(name="input",
                                                            url=self.input_ria_url,
                                                            storage_sibling=False,   # False is `off` in CLI of datalad
                                                            new_store_ok=True)

        # Register the input dataset(s):
        print("\nRegistering the input dataset(s)...")
        for i_ds in range(0, input_ds.num_ds):
            # path to cloned dataset:
            i_ds_path = op.join(self.analysis_path,
                                input_ds.df["path_now_rel"][i_ds])
            if op.exists(i_ds_path):
                print("The input dataset #" + str(i_ds+1) + " '"
                      + input_ds.df["name"][i_ds] + "'"
                      + " has been copied into `analysis` folder; "
                      "not to copy again.")
                pass
                # TODO: add sanity check: if its datalad sibling is input dataset
            else:
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
        print("\nChecking whether each input dataset is a zipped or unzipped dataset...")
        input_ds.check_if_zipped()
        # sanity checks:
        input_ds.check_validity_zipped_input_dataset(self.type_session)

        # Check validity of unzipped ds:
        #   if multi-ses, has `ses-*` in each `sub-*`; if single-ses, has a `sub-*`
        check_validity_unzipped_input_dataset(input_ds, self.type_session)

        # Add container as sub-dataset of `analysis`:
        # # TO ASK: WHY WE NEED TO CLONE IT FIRST INTO `project_root`???
        # dlapi.clone(source = container_ds,    # container datalad dataset
        #             path = op.join(self.project_root, "containers"))   # path to clone into

        # directly add container as sub-dataset of `analysis`:
        print("\nAdding the container as a sub-dataset of `analysis` dataset...")
        if op.exists(op.join(self.analysis_path, "containers")):
            print("The container has been added as a sub-dataset; not to do it again.")
            pass
            # TODO: check if the container has been successfully added as a sub-dataset!
        else:
            # clone input dataset(s) as sub-dataset into `analysis` dataset
            dlapi.install(dataset=self.analysis_path,
                          source=container_ds,    # container datalad dataset
                          path=op.join(self.analysis_path, "containers"))
            # into `analysis\containers` folder

        # original bash command, if directly going into as sub-dataset:
        # datalad install -d . --source ../../toybidsapp-container-docker/ containers

        # from our the way:
        # cd ${PROJECTROOT}/analysis
        # datalad install -d . --source ${PROJECTROOT}/pennlinc-containers

        # ==============================================================
        # Bootstrap scripts:
        # ==============================================================

        container = Container(container_ds, container_name, container_config_yaml_file)

        # Generate `<containerName>_zip.sh`: ----------------------------------
        # which is a bash script of singularity run + zip
        # in folder: `analysis/code`
        print("\nGenerating a bash script for running container and zipping the outputs...")
        print("This bash script will be named as `" + container_name + "_zip.sh`")
        bash_path = op.join(self.analysis_path, "code", container_name + "_zip.sh")
        container.generate_bash_run_bidsapp(bash_path, input_ds, self.type_session)
        self.datalad_save(path="code/" + container_name + "_zip.sh",
                          message="Generate script of running container")

        # Generate `participant_job.sh`: --------------------------------------
        print("\nGenerating a bash script for running jobs at participant (or session) level...")
        print("This bash script will be named as `participant_job.sh`")
        bash_path = op.join(self.analysis_path, "code", "participant_job.sh")
        container.generate_bash_participant_job(bash_path, input_ds, self.type_session,
                                                system)

        # datalad save `<containerName>_zip.sh` and `participant_job.sh`:
        self.datalad_save(path="code/participant_job.sh",
                          message="Participant compute job implementation")
        # NOTE: `dlapi.save()` does not work...
        # e.g., datalad save -m "Participant compute job implementation"

        # # Generate `submit_jobs.sh`: ------------------------------------------
        # # this is temporary, and will be replaced by `babs-submit`
        # print("\nGenerating a bash script for submitting jobs"
        #       + " at participant (or session) level...")
        # print("This bash script will be named as `submit_jobs.sh`")
        # print("This will be deprecated and replaced by `babs-submit`")
        # bash_path = op.join(self.analysis_path, "code", "submit_jobs.sh")
        # container.generate_bash_submit_jobs(bash_path, input_ds, self,
        #                                     system)
        # self.datalad_save(path="code/submit_jobs.sh",
        #                   message="Commands for job submission")
        # self.datalad_save(path="code/*.csv",
        #                   message="Record of inclusion/exclusion of participants")

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
        self.datalad_save(path="code/submit_job_template.yaml",
                          message="Template for job submission")

        # Generate `merge_outputs.sh`: ----------------------------------------
        # this is temporary, and will be replaced by `babs-merge`
        print("\nGenerating a bash script for merging the result branches...")
        print("This bash script will be named as `merge_outputs.sh`")
        print("This will be deprecated and replaced by `babs-merge`")
        bash_path = op.join(self.analysis_path, "code", "merge_outputs.sh")
        container.generate_bash_merge_outputs(bash_path, self)
        self.datalad_save(path="code/merge_outputs.sh",
                          message="Bash script for merging result branches")

        # Finish up and get ready for clusters running: -----------------------

        # create folder `logs` in `analysis`; future log files go here
        log_path = op.join(self.analysis_path, "logs")
        if not op.exists(log_path):
            os.makedirs(log_path)

        # write into .gitignore so won't be tracked by git:
        gitignore_path = op.join(self.analysis_path, ".gitignore")
        gitignore_file = open(gitignore_path, "a")   # open in append mode

        gitignore_file.write("\nlogs")   # not to track `logs` folder
        # not to track `.*_datalad_lock`:
        if system.type == "sge":
            gitignore_file.write("\n.SGE_datalad_lock")
        elif system.type == "slurm":
            # TODO: add command for `slurm`!!!
            print("Not supported yet... To work on...")
        gitignore_file.write("\n")

        gitignore_file.close()

        self.datalad_save(path=["code/", ".gitignore"],
                          message="Submission setup")

        # ==============================================================
        # Clean up:
        # ==============================================================

        print("\nCleaning up...")
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

    def babs_submit(self, count=1, df_job_specified=None):
        """
        This function submits jobs and prints out job status.

        Parameters:
        -------------------
        count: int
            number of jobs to be submitted
            default: 1 (no upper limit number of job submission)
            negative value: to submit all jobs
        df_job_specified: pd.DataFrame or None
            list of specified job(s) to submit.
            columnes: 'sub_id' (and 'ses_id', if multi-ses)
            If `--job` was not specified in `babs-submit`, it will be None.
        """

        count_report_progress = 10
        # ^^ if `j_count` is several times of `count_report_progress`, report progress

        # update `analysis_datalad_handle`:
        if self.analysis_datalad_handle is None:
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)

        # Check if this csv file has been created, if not, create it:
        create_job_status_csv(self)

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
                        # sanity check: there should only be one `i_job`:
                        assert_msg = "There are duplications in `job_status.csv`" \
                            + " for " + sub
                        if self.type_session == "multi-ses":
                            assert_msg += ", " + ses
                        assert len(i_job) == 1, assert_msg + "!"
                        i_job = i_job[0]   # take the element out of the list

                        # check if the job has already been submitted:
                        if not df_job["has_submitted"][i_job]:  # to run
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
                        else:
                            to_print = "The job for " + sub
                            if self.type_session == "multi-ses":
                                to_print += ", " + ses
                            to_print += " has already been submitted," \
                                + " so it won't be submitted again." \
                                + " If you want to resubmit it, please use `babs-status --resubmit`"
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

                print(df_job_updated)

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

    def babs_status(self, flags_resubmit):
        """
        This function checks job status and resubmit jobs if requested.

        Parameters:
        -------------
        flags_resubmit: list
            Under what condition to perform job resubmit.
            Element choices are: 'failed', 'pending', 'stalled'.
        """

        # Check if this csv file has been created, if not, create it:
        create_job_status_csv(self)

        # Load the csv file
        lock_path = self.job_status_path_abs + ".lock"
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                df_job = read_job_status_csv(self.job_status_path_abs)
                df_job_updated = df_job.copy()

                # Get all jobs' status:
                df_all_job_status = request_all_job_status()

                # Update job status, and resubmit if requested:
                # get the list of jobs submitted, but `is_done` is not True:
                temp = (df_job['has_submitted']) & (~df_job['is_done'])
                list_index_job_tocheck = df_job.index[temp].tolist()
                for i_job in list_index_job_tocheck:
                    # Get basic information for this job:
                    job_id = df_job.at[i_job, "job_id"]
                    job_id_str = str(job_id)
                    if self.type_session == "single-ses":
                        sub = df_job.at[i_job, "sub_id"]
                        ses = None
                        pattern_branchname = sub
                    if self.type_session == "multi-ses":
                        sub = df_job.at[i_job, "sub_id"]
                        ses = df_job.at[i_job, "ses_id"]
                        pattern_branchname = sub + "-" + ses

                    # Check if there is a branch in output RIA:
                    proc_git_branch_all = subprocess.run(
                        ["git", "branch", "-a"],
                        cwd=self.output_ria_data_dir,
                        stdout=subprocess.PIPE
                    )
                    proc_git_branch_all.check_returncode()
                    msg = proc_git_branch_all.stdout.decode('utf-8')
                    # if any branch name contains the pattern of current job:
                    if any(pattern_branchname in branchname for branchname in msg.split()):
                        # found the branch:
                        df_job_updated.at[i_job, "is_done"] = True
                        # reset/update:
                        df_job_updated.at[i_job, "job_state_category"] = np.nan
                        df_job_updated.at[i_job, "job_state_code"] = np.nan
                        df_job_updated.at[i_job, "duration"] = np.nan
                        #   ROADMAP: ^^ get duration via `qaact`
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
                                df_job_updated.at[i_job, "job_state_category"] = state_category
                                df_job_updated.at[i_job, "job_state_code"] = state_code
                                # get the duration:
                                duration = calcu_runtime(
                                    df_all_job_status.at[job_id_str, "JAT_start_time"])
                                df_job_updated.at[i_job, "duration"] = duration

                                # do nothing else, just wait

                            elif state_code == "qw":
                                if 'pending' in flags_resubmit:
                                    # Resubmit:
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

                                else:   # not to resubmit:
                                    # update fields:
                                    df_job_updated.at[i_job, "job_state_category"] = state_category
                                    df_job_updated.at[i_job, "job_state_code"] = state_code

                        else:   # did not find in `df_all_job_status`
                            # probably error
                            df_job.at[i_job, "is_failed"] = "True"
                            # reset:
                            df_job_updated.at[i_job, "job_state_category"] = np.nan
                            df_job_updated.at[i_job, "job_state_code"] = np.nan
                            df_job_updated.at[i_job, "duration"] = np.nan
                            df_job_updated.at[i_job, "is_done"] = np.nan  # may not be necessary
                            # ROADMAP: ^^ get duration via `qacct`

                            # check the log file:
                            # TODO ^^
                            # TODO: assign error category in df; also print it out

                            # resubmit if requested:
                            if "error" in flags_resubmit:
                                # Resubmit:
                                # print a message:
                                to_print = "Resubmit job for sub_id '" + sub + "'"
                                if self.type_session == "multi-ses":
                                    to_print += ", ses_id '" + ses + "'"
                                to_print += ", as it has error and resubmit was requested."
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
                                df_job_updated.at[i_job, "is_failed"] = np.nan
                                # reset of `job_state_*` have been done - see above
                            else:  # resubmit 'error' was not requested:
                                # TODO: update fields: error code

                                print("")

                print("")
                print(df_job_updated)

                # save updated df:
                df_job_updated.to_csv(self.job_status_path_abs, index=False)

                # Report the job status:
                report_job_status(df_job_updated, self.analysis_path)

        except Timeout:   # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print("Another instance of this application currently holds the lock.")


class Input_ds():
    """This class is for input dataset(s)"""

    def __init__(self, input_cli, list_sub_file, type_session):
        """
        This is to initalize `Input_ds` class.

        Parameters:
        --------------
        input_cli: nested list of strings
            see CLI `babs-init --input` for more
        list_sub_file: str or None
            Path to the CSV file that lists the subject (and sessions) to analyze;
            or `None` if that CLI flag was not specified.
            single-ses data: column of 'sub_id';
            multi-ses data: columns of 'sub_id' and 'ses_id'
        type_session: str
            "multi-ses" or "single-ses"


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
            got from `list_sub_file`
            single-session data: column of 'sub_id';
            multi-session data: columns of 'sub_id' and 'ses_id'
        """

        # About input dataset(s):
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
        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__)))

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
            This container datalad ds is prepared by the user.
        container_name: str
            The name of the container when adding to datalad dataset(e.g., `NAME` in
            `datalad containers-add NAME`),
             e.g., fmriprep-0-0-0
        config_yaml_file: str
            The YAML file that contains the configurations of how to run the container
            This is optional argument (of the CLI `babs-init`)
        config: dict
            The configurations regaring running the BIDS App on a cluster
            read from `config_yaml_file`.
        container_path_relToAnalysis: str
            The path to the container image saved in BABS project;
            this path is relative to `analysis` folder.
            e.g., `containers/.datalad/environments/fmriprep-0-0-0/image`
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

        # TODO: validate that this `container_name` really exists in `container_ds`...

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

        type_session = validate_type_session(type_session)
        output_foldername = "outputs"    # folername of BIDS App outputs

        # Check if the folder exist; if not, create it:
        bash_dir = op.dirname(bash_path)
        if not op.exists(bash_dir):
            os.makedirs(bash_dir)

        # check if `self.config` from the YAML file contains information we need:
        if "babs_singularity_run" not in self.config:
            print("The key 'babs_singularity_run' was not included "
                  "in the `container_config_yaml_file`. "
                  "Therefore we will not refer to the yaml file for `singularity run` arguments, "
                  "but will use regular `singularity run` command.")
        #       "command of singularity run will be read from information "
        #       "saved by `call-fmt` when `datalad containers-add.`")
            cmd_singularity_flags = "\n\t"
        else:
            # print("Generate singularity run command from `container_config_yaml_file`")
            # # contain \ for each key-value

            # read config from the yaml file:
            cmd_singularity_flags, flag_fs_license, singuRun_input_dir = \
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

        # Export environment variable:
        cmd_envvar, templateflow_home, singularityenv_templateflow_home = generate_cmd_envvar(
            self.config, self.container_name)
        bash_file.write(cmd_envvar)

        # Write the head of the command `singularity run`:
        bash_file.write("mkdir -p ${PWD}/.git/tmp/wkdir\n")
        cmd_head_singularityRun = "singularity run --cleanenv -B ${PWD}"

        # check if `templateflow_home` needs to be bind:
        if templateflow_home is not None:
            cmd_head_singularityRun += "," + templateflow_home + ":"
            cmd_head_singularityRun += singularityenv_templateflow_home
            # ^^ bind to dir in container

        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += self.container_path_relToAnalysis
        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += singuRun_input_dir  # inputs/data/<name>
        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += output_foldername   # output folder

        # currently all BIDS App support `participant` positional argu:
        # if any(ele in self.container_name.lower() for ele in ["xcp"]):
        #     pass
        # else:
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

        # if needed, copy Freesurfer license:
        if flag_fs_license is True:
            # check if `${FREESURFER_HOME}/license.txt` exists: if not, error
            freesurfer_home = os.getenv('FREESURFER_HOME')  # get env variable
            if freesurfer_home is None:    # did not set
                raise Exception(
                    "FreeSurfer's license will be used"
                    + " but `$FREESURFER_HOME` was not set."
                    + " Therefore, BABS cannot copy and paste FreeSurfer's license..."
                    )
            fs_license_path_from = op.join(freesurfer_home, "license.txt")
            if op.exists(fs_license_path_from) is False:
                raise Exception("There is no `license.txt` file in $FREESURFER_HOME to be copied!")

            fs_license_path_to = op.join(bash_dir, "license.txt")  # `bash_dir` is `analysis/code`
            proc_copy_fs_license = subprocess.run(
                # e.g., cp ${FREESURFER_HOME}/license.txt code/license.txt
                ["cp", fs_license_path_from, fs_license_path_to],
                stdout=subprocess.PIPE
            )
            proc_copy_fs_license.check_returncode()

        # print()

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
            bash_file.write('where_to_run="$5"\n')
        elif type_session == "single-ses":
            bash_file.write('where_to_run="$4"\n')

        # TODO: if `where_to_run` is not specified, change to default = ??

        bash_file.write("\n# Change to a temporary directory or compute space:\n")
        bash_file.write('if [[ "${where_to_run}" == "cbica_tmpdir"  ]]; then\n')
        bash_file.write("\t" + "cd ${CBICA_TMPDIR}" + "\n")
        bash_file.write('elif [[ "${where_to_run}" == "comp_space"   ]]; then\n')
        bash_file.write("\t" + "cd /cbica/comp_space/$(basename $HOME)\n")
        bash_file.write("fi\n")

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

        # `datalad get` the container ??
        # NOTE: only found in `bootstrap-fmriprep-ingressed-fs.sh`...
        #   not sure if this is really needed
        bash_file.write("\n# Get the container dataset:\n")
        bash_file.write("datalad get -r containers" + "\n")
        # NOTE: ^^ not sure if `-r` is needed....

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

    def generate_job_submit_template(self, yaml_path, input_ds, babs, system):
        """
        This is to generate a text file that serves as a template
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
            cmd += " " \
                + "cbica_tmpdir"

        elif babs.type_session == "multi-ses":
            cmd = submit_head + " " + env_flags \
                + " -N " + self.container_name[0:3] + "_" + "${sub_id}_${ses_id}"
            cmd += " " \
                + eo_args + " " \
                + babs.analysis_path + "/code/participant_job.sh" + " " \
                + dssource + " " \
                + pushgitremote + " " + "${sub_id} ${ses_id}"
            cmd += " " \
                + "cbica_tmpdir"

        yaml_file.write("cmd_template: '" + cmd + "'" + "\n")

        # TODO: currently only support SGE.

        # Section 2: Job name: ---------------------------
        job_name = self.container_name[0:3] + "_" + "${sub_id}"
        if babs.type_session == "multi-ses":
            job_name += "_${ses_id}"

        yaml_file.write("job_name_template: '" + job_name + "'\n")

        yaml_file.close()

    def generate_bash_submit_jobs(self, bash_path, input_ds, babs, system):
        """
        !!!DEPRECATED!!!

        This is to generate a bash script that submit jobs for each participant (or session).
        This is a temporary function which will be deprecated and replaced
        by `babs-submit`.

        Parameters:
        -------------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `Input_ds`
            input dataset(s) information
        babs: class `BABS`
            information about the BABS project
        system: class `System`
            information on cluster management system
        """

        # Flags when submitting the job:
        if system.type == "sge":
            submit_head = "qsub -cwd"
            env_flags = "-v DSLOCKFILE=" + babs.analysis_path + "/.SGE_datalad_lock"
            eo_args = "-e " + babs.analysis_path + "/logs " \
                + "-o " + babs.analysis_path + "/logs"
        else:
            warnings.warn("not supporting systems other than sge...")

        # Check if the bash file already exist:
        if op.exists(bash_path):
            os.remove(bash_path)  # remove it

        # Write into the bash file:
        bash_file = open(bash_path, "a")   # open in append mode

        bash_file.write("#!/bin/bash\n")

        # Variables to use:
        # `dssource`: Input RIA:
        dssource = babs.input_ria_url + "#" + babs.analysis_dataset_id
        # `pushgitremote`: Output RIA:
        pushgitremote = babs.output_ria_data_dir

        # Get the list of subjects + generate the commands:
        #   `get_list_sub_ses` will also remove the sub/ses
        #   that does not have required file(s) (based on input yaml file)
        if babs.type_session == "single-ses":
            subs = get_list_sub_ses(input_ds, self.config, babs)
            # iterate across subs:
            for sub in subs:
                str = submit_head + " " + env_flags \
                    + " -N " + self.container_name[0:3] + "_" + sub + " " \
                    + eo_args + " " \
                    + babs.analysis_path + "/code/participant_job.sh" + " " \
                    + dssource + " " \
                    + pushgitremote + " " \
                    + sub + " " \
                    + "cbica_tmpdir" + "\n"
                bash_file.write(str)

        else:   # multi-ses
            dict_sub_ses = get_list_sub_ses(input_ds, self.config, babs)
            # iterate across subs, then iterate across sess:
            for sub in list(dict_sub_ses.keys()):   # keys are subs
                for ses in dict_sub_ses[sub]:
                    str = submit_head + " " + env_flags \
                        + " -N " + self.container_name[0:3] + "_" + sub + "_" + ses + " " \
                        + eo_args + " " \
                        + babs.analysis_path + "/code/participant_job.sh" + " " \
                        + dssource + " " \
                        + pushgitremote + " " \
                        + sub + " " \
                        + ses + " " \
                        + "cbica_tmpdir" + "\n"
                    bash_file.write(str)

        # TODO: currently only support SGE.

        bash_file.close()

        # Change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ["chmod", "+x", bash_path],  # e.g., chmod +x code/submit_jobs.sh
            stdout=subprocess.PIPE
            )
        proc_chmod_bashfile.check_returncode()

    def generate_bash_merge_outputs(self, bash_path, babs):
        """
        This is to generate a bash script that merge result branches.
        This is a temporary function which will be deprecated and replaced
        by `babs-merge`.

        Parameters:
        -------------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        babs: class `BABS`
            information about the BABS project
        """

        # Check if the bash file already exist:
        if op.exists(bash_path):
            os.remove(bash_path)  # remove it

        # Write into the bash file:
        bash_file = open(bash_path, "a")   # open in append mode

        bash_file.write("#!/bin/bash\n")
        bash_file.write("set -e -u -x\n")

        # Variable `outputsource`:
        bash_file.write("outputsource=" + babs.output_ria_url
                        + "#" + babs.analysis_dataset_id + "\n")

        # cd to project root:
        bash_file.write("cd " + babs.project_root + "\n")

        # Read content from `merge_outputs_postscript.sh`:
        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__)))

        fn_meat = op.join(__location__, "merge_outputs_postscript.sh")
        bash_file_meat = open(fn_meat, "r")
        the_meat = bash_file_meat.read()   # read the content
        bash_file_meat.close()

        bash_file.write("\n")
        bash_file.write(the_meat)

        bash_file.close()

        # Change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ["chmod", "+x", bash_path],  # e.g., chmod +x code/submit_jobs.sh
            stdout=subprocess.PIPE
            )
        proc_chmod_bashfile.check_returncode()
