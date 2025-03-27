"""This is the main module."""

import os
import os.path as op
import re
import subprocess
import time
import warnings
from datetime import datetime
from urllib.parse import urlparse

import datalad.api as dlapi
import numpy as np
import pandas as pd
from filelock import FileLock, Timeout
from jinja2 import Environment, PackageLoader, StrictUndefined

from babs.container import Container
from babs.system import validate_queue
from babs.utils import (
    calcu_runtime,
    ceildiv,
    df_status_update,
    df_submit_update,
    get_alert_message_in_log_files,
    get_cmd_cancel_job,
    get_config_msg_alert,
    get_git_show_ref_shasum,
    get_immediate_subdirectories,
    get_last_line,
    get_list_sub_ses,
    prepare_job_array_df,
    print_versions_from_yaml,
    read_job_status_csv,
    read_yaml,
    report_job_status,
    request_all_job_status,
    submit_array,
    submit_one_test_job,
    validate_processing_level,
    validate_unzipped_datasets,
    write_yaml,
)


class BABS:
    """The BABS class is for babs projects of BIDS Apps"""

    def __init__(self, project_root, processing_level, queue):
        """The BABS class is for babs projects of BIDS Apps.

        Parameters
        ----------
        project_root: Path
            absolute path to the root of this babs project
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        queue: str
            the type of job scheduling system, "sge" or "slurm"

        Attributes
        ----------
        project_root: str
            absolute path to the root of this babs project
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        queue: str
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
                '/path/to/analysis/code/sub_ses_final_inclu.csv' for session dataset.
        job_status_path_rel: str
            Path to the `job_status.csv` file.
            This is relative to `analysis` folder.
        job_status_path_abs: str
            Absolute path of `job_status_path_abs`.
            Example: '/path/to/analysis/code/job_status.csv'
        job_submit_path_abs: str
            Absolute path of `job_submit_path_abs`.
            Example: '/path/to/analysis/code/job_submit.csv'
        """

        # validation:
        processing_level = validate_processing_level(processing_level)
        queue = validate_queue(queue)

        # attributes:
        self.project_root = str(project_root)
        self.processing_level = processing_level
        self.queue = queue

        self.analysis_path = op.join(self.project_root, 'analysis')
        self.analysis_datalad_handle = None

        self.config_path = op.join(self.analysis_path, 'code/babs_proj_config.yaml')

        self.input_ria_path = op.join(self.project_root, 'input_ria')
        self.output_ria_path = op.join(self.project_root, 'output_ria')

        self.input_ria_url = 'ria+file://' + self.input_ria_path
        self.output_ria_url = 'ria+file://' + self.output_ria_path

        self.output_ria_data_dir = None  # not known yet before output_ria is created
        self.analysis_dataset_id = None  # to update later

        # attribute `list_sub_path_*`:
        if self.processing_level == 'subject':
            self.list_sub_path_rel = 'code/sub_final_inclu.csv'
        elif self.processing_level == 'session':
            self.list_sub_path_rel = 'code/sub_ses_final_inclu.csv'
        self.list_sub_path_abs = op.join(self.analysis_path, self.list_sub_path_rel)

        self.job_status_path_rel = 'code/job_status.csv'
        self.job_status_path_abs = op.join(self.analysis_path, self.job_status_path_rel)
        self.job_submit_path_abs = op.join(self.analysis_path, 'code/job_submit.csv')

    def datalad_save(self, path, message=None, filter_files=None):
        """
        Save the current status of datalad dataset `analysis`
        Also checks that all the statuses returned are "ok" (or "notneeded")

        Parameters
        ----------
        path: str or list of str
            the path to the file(s) or folder(s) to save
        message: str or None
            commit message in `datalad save`
        filter_files: list of str or None
            list of filenames to exclude from saving
            if None, no files will be filtered

        Notes
        -----
        If the path does not exist, the status will be "notneeded", and won't be error message
            And there won't be a commit with that message
        """
        if filter_files is not None:
            # Create a temporary .gitignore file to exclude specified files
            gitignore_path = os.path.join(self.analysis_path, '.gitignore')
            with open(gitignore_path, 'w') as f:
                for file in filter_files:
                    f.write(f'{file}\n')

            try:
                statuses = self.analysis_datalad_handle.save(path=path, message=message)
            finally:
                # Clean up the temporary .gitignore file
                if os.path.exists(gitignore_path):
                    os.remove(gitignore_path)
        else:
            statuses = self.analysis_datalad_handle.save(path=path, message=message)

        # ^^ number of dicts in list `statuses` = len(path)
        # check that all statuses returned are "okay":
        # below is from cubids
        saved_status = {status['status'] for status in statuses}
        if saved_status.issubset({'ok', 'notneeded'}) is False:
            # exists element in `saved_status` that is not "ok" or "notneeded"
            # ^^ "notneeded": nothing to save
            raise Exception('`datalad save` failed!')

    def wtf_key_info(self, flag_output_ria_only=False):
        """
        This is to get some key information on DataLad dataset `analysis`,
        and assign to `output_ria_data_dir` and `analysis_dataset_id`.
        This function relies on `git` and `datalad wtf`
        This needs to be done after the output RIA is created.

        Parameters
        ----------
        flag_output_ria_only: bool
            if only to get information on output RIA.
            This may expedite the process as other information requires
            calling `datalad` in terminal, which would takes several seconds.
        """

        # Get the `self.output_ria_data_dir`:
        # e.g., /full/path/output_ria/238/da2f2-2fc4-4b88-a2c5-aa6e754b5d0b
        analysis_git_path = op.join(self.analysis_path, '.git')
        proc_output_ria_data_dir = subprocess.run(
            [
                'git',
                '--git-dir',
                analysis_git_path,
                'remote',
                'get-url',
                '--push',
                'output',
            ],
            stdout=subprocess.PIPE,
        )
        # ^^: for `analysis`: git remote get-url --push output
        # ^^ another way to change the wd temporarily: add `cwd=self.xxx` in `subprocess.run()`
        # if success: no output; if failed: will raise CalledProcessError
        proc_output_ria_data_dir.check_returncode()
        self.output_ria_data_dir = urlparse(proc_output_ria_data_dir.stdout.decode('utf-8')).path
        if self.output_ria_data_dir[-1:] == '\n':
            # remove the last 2 characters
            self.output_ria_data_dir = self.output_ria_data_dir[:-1]

        if not flag_output_ria_only:  # also want other information:
            # Get the dataset ID of `analysis`, i.e., `analysis_dataset_id`:
            # way #2: command line of datalad:
            proc_analysis_dataset_id = subprocess.run(
                ['datalad', '-f', "'{infos[dataset][id]}'", 'wtf', '-S', 'dataset'],
                cwd=self.analysis_path,
                stdout=subprocess.PIPE,
            )
            # datalad -f '{infos[dataset][id]}' wtf -S dataset
            proc_analysis_dataset_id.check_returncode()
            self.analysis_dataset_id = proc_analysis_dataset_id.stdout.decode('utf-8')
            # remove the `\n`:
            if self.analysis_dataset_id[-1:] == '\n':
                # remove the last 2 characters
                self.analysis_dataset_id = self.analysis_dataset_id[:-1]
            # remove the double quotes:
            if (self.analysis_dataset_id[0] == "'") & (self.analysis_dataset_id[-1] == "'"):
                # if first and the last characters are quotes: remove them
                self.analysis_dataset_id = self.analysis_dataset_id[1:-1]

    def babs_bootstrap(self, input_ds, container_ds, container_name, container_config, system):
        """
        Bootstrap a babs project: initialize datalad-tracked RIAs, generate scripts to be used, etc

        Parameters
        ----------
        input_ds: class `InputDatasets`
            Input dataset(s).
        container_name: str
            name of the container, best to include version number.
            e.g., 'fmriprep-0-0-0'
        container_ds: str
            path to the container datalad dataset which the user provides
        container_config: str
            Path to a YAML file that contains the configurations
            of how to run the BIDS App container
        system: class `System`
            information about the cluster management system
        """

        # ==============================================================
        # Initialize:
        # ==============================================================

        # Make a directory of project_root:
        os.makedirs(self.project_root)  # we don't allow creation if folder exists

        # Create `analysis` folder: -----------------------------
        print('\nCreating `analysis` folder (also a datalad dataset)...')
        self.analysis_datalad_handle = dlapi.create(
            self.analysis_path, cfg_proc='yoda', annex=True
        )

        # Prepare `.gitignore` ------------------------------
        # write into .gitignore so won't be tracked by git:
        gitignore_path = op.join(self.analysis_path, '.gitignore')
        # if exists already, remove it:
        if op.exists(gitignore_path):
            os.remove(gitignore_path)
        gitignore_file = open(gitignore_path, 'a')  # open in append mode

        # not to track `logs` folder:
        gitignore_file.write('\nlogs')
        # not to track `.*_datalad_lock`:
        if system.type == 'sge':
            gitignore_file.write('\n.SGE_datalad_lock')
        elif system.type == 'slurm':
            gitignore_file.write('\n.SLURM_datalad_lock')
        else:
            warnings.warn(
                'Not supporting systems other than SGE or Slurm' + " for '.gitignore'.",
                stacklevel=2,
            )
        # not to track lock file:
        gitignore_file.write('\n' + 'code/babs_proj_config.yaml.lock')
        # not to track `job_status.csv`:
        gitignore_file.write('\n' + 'code/job_status.csv')
        gitignore_file.write('\n' + 'code/job_status.csv.lock')
        # not to track files generated by `babs check-setup`:
        gitignore_file.write('\n' + 'code/check_setup/test_job_info.yaml')
        gitignore_file.write('\n' + 'code/check_setup/check_env.yaml')
        gitignore_file.write('\n')

        gitignore_file.close()
        self.datalad_save(path='.gitignore', message='Save .gitignore file')

        # Create `babs_proj_config.yaml` file: ----------------------
        print('Save BABS project configurations in a YAML file ...')
        print("Path to this yaml file will be: 'analysis/code/babs_proj_config.yaml'")

        env = Environment(
            loader=PackageLoader('babs', 'templates'),
            autoescape=False,
            undefined=StrictUndefined,
        )
        template = env.get_template('babs_proj_config.yaml.jinja2')

        with open(self.config_path, 'w') as f:
            f.write(
                template.render(
                    processing_level=self.processing_level,
                    queue=self.queue,
                    input_ds=input_ds,
                    container_name=container_name,
                    container_ds=container_ds,
                )
            )
        self.datalad_save(
            path=self.config_path,
            message='Initial save of babs_proj_config.yaml',
        )
        # Create output RIA sibling: -----------------------------
        print('\nCreating output and input RIA...')
        self.analysis_datalad_handle.create_sibling_ria(
            name='output', url=self.output_ria_url, new_store_ok=True
        )
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
            name='input',
            url=self.input_ria_url,
            storage_sibling=False,  # False is `off` in CLI of datalad
            new_store_ok=True,
        )

        # Register the input dataset(s): -----------------------------
        print('\nRegistering the input dataset(s)...')
        for i_ds in range(0, input_ds.num_ds):
            # path to cloned dataset:
            i_ds_path = op.join(self.analysis_path, input_ds.df.loc[i_ds, 'path_now_rel'])
            print(f'Cloning input dataset #{i_ds + 1}: ' + input_ds.df.loc[i_ds, 'name'])
            # clone input dataset(s) as sub-dataset into `analysis` dataset:
            dlapi.clone(
                dataset=self.analysis_path,
                source=input_ds.df.loc[i_ds, 'path_in'],  # input dataset(s)
                path=i_ds_path,
            )  # path to clone into

            # amend the previous commit with a nicer commit message:
            proc_git_commit_amend = subprocess.run(
                [
                    'git',
                    'commit',
                    '--amend',
                    '-m',
                    "Register input data dataset '"
                    + input_ds.df.loc[i_ds, 'name']
                    + "' as a subdataset",
                ],
                cwd=self.analysis_path,
                stdout=subprocess.PIPE,
            )
            proc_git_commit_amend.check_returncode()

        # get the current absolute path to the input dataset:
        input_ds.assign_path_now_abs(self.analysis_path)

        # Check the type of each input dataset: (zipped? unzipped?)
        #   this also gets `is_zipped`
        print('\nChecking whether each input dataset is a zipped or unzipped dataset...')
        input_ds.check_if_zipped()
        # sanity checks:
        input_ds.check_validity_zipped_input_dataset(self.processing_level)

        # Check validity of unzipped ds:
        #   if session, has `ses-*` in each `sub-*`; if subject, has a `sub-*`
        validate_unzipped_datasets(input_ds, self.processing_level)

        # Update input ds information in `babs_proj_config.yaml`:
        babs_proj_config = read_yaml(self.config_path, if_filelock=True)
        for i_ds in range(0, input_ds.num_ds):
            ds_index_str = '$INPUT_DATASET_#' + str(i_ds + 1)
            # update `path_data_rel`:
            babs_proj_config['input_ds'][ds_index_str]['path_data_rel'] = input_ds.df.loc[
                i_ds, 'path_data_rel'
            ]
            # update `is_zipped`:
            babs_proj_config['input_ds'][ds_index_str]['is_zipped'] = input_ds.df.loc[
                i_ds, 'is_zipped'
            ]
        # dump:
        write_yaml(babs_proj_config, self.config_path, if_filelock=True)
        # datalad save: update:
        self.datalad_save(
            path='code/babs_proj_config.yaml',
            message='Update configurations of input dataset of this BABS project',
        )

        # Add container as sub-dataset of `analysis`: -----------------------------
        # XXX: WHY DO WE NEED TO CLONE IT FIRST INTO `project_root`???

        # directly add container as sub-dataset of `analysis`:
        print('\nAdding the container as a sub-dataset of `analysis` dataset...')
        dlapi.install(
            dataset=self.analysis_path,
            source=container_ds,  # container datalad dataset
            path=op.join(self.analysis_path, 'containers'),
        )
        # into `analysis/containers` folder

        container = Container(container_ds, container_name, container_config)

        # sanity check of container ds:
        container.sanity_check(self.analysis_path)

        # ==============================================================
        # Bootstrap scripts:
        # ==============================================================

        # Generate `<containerName>_zip.sh`: ----------------------------------
        # which is a bash script of singularity run + zip
        # in folder: `analysis/code`
        print('\nGenerating a bash script for running container and zipping the outputs...')
        print('This bash script will be named as `' + container_name + '_zip.sh`')
        bash_path = op.join(self.analysis_path, 'code', container_name + '_zip.sh')
        container.generate_bash_run_bidsapp(bash_path, input_ds, self.processing_level)
        self.datalad_save(
            path='code/' + container_name + '_zip.sh',
            message='Generate script of running container',
        )

        # make another folder within `code` for test jobs:
        os.makedirs(op.join(self.analysis_path, 'code/check_setup'), exist_ok=True)

        # Generate `participant_job.sh`: --------------------------------------
        print('\nGenerating a bash script for running jobs at participant (or session) level...')
        print('This bash script will be named as `participant_job.sh`')
        bash_path = op.join(self.analysis_path, 'code', 'participant_job.sh')
        container.generate_bash_participant_job(bash_path, input_ds, self.processing_level, system)

        # also, generate a bash script of a test job used by `babs check-setup`:
        path_check_setup = op.join(self.analysis_path, 'code/check_setup')
        container.generate_bash_test_job(path_check_setup, system)

        self.datalad_save(
            path=[
                'code/participant_job.sh',
                'code/check_setup/call_test_job.sh',
                'code/check_setup/test_job.py',
            ],
            message='Participant compute job implementation',
        )
        # NOTE: `dlapi.save()` does not work...
        # e.g., datalad save -m "Participant compute job implementation"

        # Copy in any other files needed:
        imported_files = []
        for imported_file in container.config.get('imported_files', []):
            # Check that the file exists:
            assert op.exists(imported_file['original_path']), (
                f'Requested imported file {imported_file["original_path"]} does not exist.'
            )
            imported_location = op.join(self.analysis_path, imported_file['analysis_path'])
            # Copy the file using pure Python:
            with (
                open(imported_file['original_path'], 'rb') as src,
                open(imported_location, 'wb') as dst,
            ):
                dst.write(src.read())
            if not op.exists(imported_location):
                raise FileNotFoundError(
                    f'Failed to copy file {imported_file["original_path"]} to {imported_location}'
                )
            # Append the relative path instead of absolute path
            imported_files.append(op.relpath(imported_location, self.analysis_path))
        if imported_files:
            self.datalad_save(
                path=imported_files,
                message='Import files',
            )

        # Determine the list of subjects to analyze: -----------------------------
        print('\nDetermining the list of subjects (and sessions) to analyze...')
        _ = get_list_sub_ses(input_ds, container.config, self)
        self.datalad_save(
            path='code/*.csv', message='Record of inclusion/exclusion of participants'
        )

        # Generate the template of job submission: --------------------------------
        print('\nGenerating a template for job submission calls...')
        print('The template text file will be named as `submit_job_template.yaml`.')
        yaml_path = op.join(self.analysis_path, 'code', 'submit_job_template.yaml')
        container.generate_job_submit_template(yaml_path, self, system)

        # also, generate template for testing job used by `babs check-setup`:
        yaml_test_path = op.join(
            self.analysis_path, 'code/check_setup', 'submit_test_job_template.yaml'
        )
        container.generate_job_submit_template(yaml_test_path, self, system, test=True)

        # datalad save:
        self.datalad_save(
            path=[
                'code/submit_job_template.yaml',
                'code/check_setup/submit_test_job_template.yaml',
            ],
            message='Template for job submission',
        )

        # Finish up and get ready for clusters running: -----------------------
        # create folder `logs` in `analysis`; future log files go here
        #   this won't be tracked by git (as already added to `.gitignore`)
        log_path = op.join(self.analysis_path, 'logs')
        if not op.exists(log_path):
            os.makedirs(log_path)

        # in case anything in `code/` was not saved:
        #   If there is anything not saved yet, probably should be added to `.gitignore`
        #   at the beginning of `babs init`.
        self.datalad_save(
            path='code/', message="Save anything in folder code/ that hasn't been saved"
        )

        # ==============================================================
        # Final steps in bootstrapping:
        # ==============================================================

        print('\nFinal steps...')
        # No need to keep the input dataset(s):
        #   old version: datalad uninstall -r --nocheck inputs/data
        print("DataLad dropping input dataset's contents...")
        for i_ds in range(0, input_ds.num_ds):
            _ = self.analysis_datalad_handle.drop(
                path=input_ds.df.loc[i_ds, 'path_now_rel'],
                recursive=True,  # and potential subdataset
                reckless='availability',
            )
            # not to check availability
            # seems have to specify the dataset (by above `handle`);
            # otherwise, dl thinks the dataset is where current python is running

        # Update input and output RIA:
        print('Updating input and output RIA...')
        #   datalad push --to input
        #   datalad push --to output
        self.analysis_datalad_handle.push(to='input')
        self.analysis_datalad_handle.push(to='output')

        # Add an alias to the data in output RIA store:
        print("Adding an alias 'data' to output RIA store...")
        """
        RIA_DIR=$(find $PROJECTROOT/output_ria/???/ -maxdepth 1 -type d | sort | tail -n 1)
        mkdir -p ${PROJECTROOT}/output_ria/alias
        ln -s ${RIA_DIR} ${PROJECTROOT}/output_ria/alias/data
        """
        if not op.exists(op.join(self.output_ria_path, 'alias')):
            os.makedirs(op.join(self.output_ria_path, 'alias'))
        # create a symbolic link:
        the_symlink = op.join(self.output_ria_path, 'alias', 'data')
        if op.exists(the_symlink) & op.islink(the_symlink):
            # exists and is a symlink: remove first
            os.remove(the_symlink)
        os.symlink(self.output_ria_data_dir, the_symlink)
        # to check this symbolic link, just: $ ls -l <output_ria/alias/data>
        #   it should point to /full/path/output_ria/xxx/xxx-xxx-xxx-xxx

        # SUCCESS!
        print('\n')
        print(
            'BABS project has been initialized!'
            " Path to this BABS project: '" + self.project_root + "'"
        )
        print('`babs init` was successful!')

    def clean_up(self, input_ds):
        """
        If `babs init` failed, this function cleans up the BABS project `babs init` creates.

        Parameters
        ----------
        input_ds: class `InputDatasets`
            information of input dataset(s)

        Notes
        -----
        Steps in `babs init`:
        * create `analysis` datalad dataset
        * create input and output RIA
        * clone input dataset(s)
        * generate bootstrapped scripts
        * finish up
        """
        if op.exists(self.project_root):  # if BABS project root folder has been created:
            if op.exists(self.analysis_path):  # analysis folder is created by datalad
                self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
                # Remove each input dataset:
                print('Removing input dataset(s) if cloned...')
                for i_ds in range(0, input_ds.num_ds):
                    # check if it exists yet:
                    path_now_abs = op.join(
                        self.analysis_path, input_ds.df.loc[i_ds, 'path_now_rel']
                    )
                    if op.exists(path_now_abs):  # this input dataset has been cloned:
                        # use `datalad remove` to remove:
                        _ = self.analysis_datalad_handle.remove(
                            path=path_now_abs, reckless='modification'
                        )

                # `git annex dead here`:
                print('\nRunning `git annex dead here`...')
                proc_git_annex_dead = subprocess.run(
                    ['git', 'annex', 'dead', 'here'],
                    cwd=self.analysis_path,
                    stdout=subprocess.PIPE,
                )
                proc_git_annex_dead.check_returncode()

                # Update input and output RIA:
                print('\nUpdating input and output RIA if created...')
                #   datalad push --to input
                #   datalad push --to output
                if op.exists(self.input_ria_path):
                    self.analysis_datalad_handle.push(to='input')
                if op.exists(self.output_ria_path):
                    self.analysis_datalad_handle.push(to='output')

            # Now we can delete this project folder:
            print('\nDeleting created BABS project folder...')
            proc_rm_project_folder = subprocess.run(
                ['rm', '-rf', self.project_root], stdout=subprocess.PIPE
            )
            proc_rm_project_folder.check_returncode()

        # confirm the BABS project has been removed:
        assert not op.exists(self.project_root), (
            'Created BABS project was not completely deleted!'
            " Path to created BABS project: '" + self.project_root + "'"
        )

        print('\nCreated BABS project has been cleaned up.')

    def babs_check_setup(self, input_ds, flag_job_test):
        """
        This function validates the setups by babs init.

        Parameters
        ----------
        input_ds: class `InputDatasets`
            information of input dataset(s)
        flag_job_test: bool
            Whether to submit and run a test job.
        """
        from .constants import CHECK_MARK

        babs_proj_config = read_yaml(self.config_path, if_filelock=True)

        print('Will check setups of BABS project located at: ' + self.project_root)
        if flag_job_test:
            print('Will submit a test job for testing; will take longer time.')
        else:
            print('Did not request `--job-test`; will not submit a test job.')

        # Print out the saved configuration info: ----------------
        print(
            'Below is the configuration information saved during `babs init`'
            " in file 'analysis/code/babs_proj_config.yaml':\n"
        )
        f = open(op.join(self.analysis_path, 'code/babs_proj_config.yaml'))
        file_contents = f.read()
        print(file_contents)
        f.close()

        # Check the project itself: ---------------------------
        print('Checking the BABS project itself...')
        # check if `analysis_path` exists
        #   (^^ though should be checked in `get_existing_babs_proj()` in cli.py)
        assert op.exists(self.analysis_path), (
            "Folder 'analysis' does not exist in this BABS project!"
            ' Current path to analysis folder: ' + self.analysis_path
        )
        # if there is `analysis`:
        # update `analysis_datalad_handle`:
        if self.analysis_datalad_handle is None:
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
        print(CHECK_MARK + ' All good!')

        # Check `analysis` datalad dataset: ----------------------
        print("\nCheck status of 'analysis' DataLad dataset...")
        # Are there anything unsaved? ref: CuBIDS function
        analysis_statuses = {
            status['state']
            for status in self.analysis_datalad_handle.status(
                eval_subdataset_state='commit'
                # not to fully eval subdataset (e.g. input ds) status
                # otherwise, would take too long..
            )
        }

        # statuses should be all "clean", without anything else e.g., "modified":
        if not analysis_statuses == {'clean'}:
            problem_statuses = [
                status
                for status in self.analysis_datalad_handle.status(eval_subdataset_state='commit')
                if status['state'] != 'clean'
            ]
            raise Exception(
                "Analysis DataLad dataset's status is not clean. "
                'There are the following issues:' + str(problem_statuses)
            )

        print(CHECK_MARK + ' All good!')

        # Check input dataset(s): ---------------------------
        print('\nChecking input dataset(s)...')
        # check if there is at least one folder in the `inputs/data` dir:
        temp_list = get_immediate_subdirectories(op.join(self.analysis_path, 'inputs/data'))
        assert len(temp_list) > 0, (
            "There is no sub-directory (i.e., no input dataset) in 'inputs/data'!"
            " Full path to folder 'inputs/data': " + op.join(self.analysis_path, 'inputs/data')
        )

        # check each input ds:
        for i_ds in range(0, input_ds.num_ds):
            path_now_abs = input_ds.df.loc[i_ds, 'path_now_abs']

            # check if the dir of this input ds exists:
            assert op.exists(path_now_abs), (
                'The path to the cloned input dataset #'
                + str(i_ds + 1)
                + " '"
                + input_ds.df.loc[i_ds, 'name']
                + "' does not exist: "
                + path_now_abs
            )

            # check if dir of input ds is a datalad dataset:
            assert op.exists(op.join(path_now_abs, '.datalad/config')), (
                'The input dataset #'
                + str(i_ds + 1)
                + " '"
                + input_ds.df.loc[i_ds, 'name']
                + "' is not a valid DataLad dataset:"
                + " There is no file '.datalad/config' in its directory: "
                + path_now_abs
            )

            # ROADMAP: check if input dataset ID saved in YAML file
            #           (not saved yet, also need to add to InputDatasets class too)
            #           = that in `.gitmodules` in cloned ds
            #   However, It's pretty unlikely that someone changes inputs/data on their own
            #       if they're using BABS

        print(CHECK_MARK + ' All good!')

        # Check container datalad dataset: ---------------------------
        print('\nChecking container datalad dataset...')
        folder_container = op.join(self.analysis_path, 'containers')
        container_name = babs_proj_config['container']['name']
        # assert it's a datalad ds in `containers` folder:
        assert op.exists(op.join(folder_container, '.datalad/config')), (
            'There is no containers DataLad dataset in folder: ' + folder_container
        )

        # ROADMAP: check if container dataset ID saved in YAML file (not saved yet)
        #           (not saved yet, probably better to add to Container class?)
        #           = that in `.gitmodules` in cloned ds
        #   However, It's pretty unlikely that someone changes it on their own
        #       if they're using BABS

        # no action now; when `babs init`, has done `Container.sanity_check()`
        #               to make sure the container named `container_name` exists.
        print(CHECK_MARK + ' All good!')

        # Check `analysis/code`: ---------------------------------
        print('\nChecking `analysis/code/` folder...')
        # folder `analysis/code` should exist:
        assert op.exists(op.join(self.analysis_path, 'code')), (
            "Folder 'code' does not exist in 'analysis' folder!"
        )

        # assert the list of files in the `code` folder,
        #   and bash files should be executable:
        list_files_code = [
            'babs_proj_config.yaml',
            container_name + '_zip.sh',
            'participant_job.sh',
            'submit_job_template.yaml',
        ]
        if self.processing_level == 'subject':
            list_files_code.append('sub_final_inclu.csv')
        else:
            list_files_code.append('sub_ses_final_inclu.csv')

        for temp_filename in list_files_code:
            temp_fn = op.join(self.analysis_path, 'code', temp_filename)
            # the file should exist:
            assert op.isfile(temp_fn), (
                "Required file '"
                + temp_filename
                + "' does not exist"
                + " in 'analysis/code' folder in this BABS project!"
            )
            # check if bash files are executable:
            if op.splitext(temp_fn)[1] == '.sh':  # extension is '.sh':
                assert os.access(temp_fn, os.X_OK), (
                    'This code file should be executable: ' + temp_fn
                )
        print(CHECK_MARK + ' All good!')

        # Check input and output RIA: ----------------------
        print('\nChecking input and output RIA...')

        # check if they are siblings of `analysis`:
        print("\tDatalad dataset `analysis`'s siblings:")
        analysis_siblings = self.analysis_datalad_handle.siblings(action='query')
        # get the actual `output_ria_data_dir`;
        #   the one in `self` attr is directly got from `analysis` remote,
        #   so should not use that here.
        # output_ria:
        actual_output_ria_data_dir = urlparse(
            os.readlink(op.join(self.output_ria_path, 'alias/data'))
        ).path  # get the symlink of `alias/data` then change to path
        assert op.exists(actual_output_ria_data_dir)  # make sure this exists
        # get '000/0000-0000-0000-0000':
        data_foldername = op.join(
            op.basename(op.dirname(actual_output_ria_data_dir)),
            op.basename(actual_output_ria_data_dir),
        )
        # input_ria:
        actual_input_ria_data_dir = op.join(self.input_ria_path, data_foldername)
        assert op.exists(actual_input_ria_data_dir)  # make sure this exists

        if_found_sibling_input = False
        if_found_sibling_output = False
        for i_sibling in range(0, len(analysis_siblings)):
            the_sibling = analysis_siblings[i_sibling]
            if the_sibling['name'] == 'output':  # output ria:
                if_found_sibling_output = True
                assert the_sibling['url'] == actual_output_ria_data_dir, (
                    "The `analysis` datalad dataset's sibling 'output' url does not match"
                    ' the path to the output RIA.'
                    ' Former = ' + the_sibling['url'] + ';'
                    ' Latter = ' + actual_output_ria_data_dir
                )
            if the_sibling['name'] == 'input':  # input ria:
                if_found_sibling_input = True

        if not if_found_sibling_input:
            raise Exception(
                "Did not find a sibling of 'analysis' DataLad dataset"
                " that's called 'input'. There may be something wrong when"
                ' setting up input RIA!'
            )
        if not if_found_sibling_output:
            raise Exception(
                "Did not find a sibling of 'analysis' DataLad dataset"
                " that's called 'output'. There may be something wrong when"
                ' setting up output RIA!'
            )

        # output_ria_datalad_handle = dlapi.Dataset(self.output_ria_data_dir)

        # check if the current commit in `analysis` has been pushed to RIA:
        #   i.e., if commit hash are matched:
        # analysis' commit hash:
        proc_hash_analysis = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=self.analysis_path, stdout=subprocess.PIPE
        )
        proc_hash_analysis.check_returncode()
        hash_analysis = proc_hash_analysis.stdout.decode('utf-8').replace('\n', '')

        # input ria's commit hash:
        proc_hash_input_ria = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=actual_input_ria_data_dir,  # using the actual one we just got
            stdout=subprocess.PIPE,
        )
        proc_hash_input_ria.check_returncode()
        hash_input_ria = proc_hash_input_ria.stdout.decode('utf-8').replace('\n', '')
        assert hash_analysis == hash_input_ria, (
            'The hash of current commit of `analysis` datalad dataset does not match'
            ' with that of input RIA.'
            ' Former = ' + hash_analysis + ';'
            ' Latter = ' + hash_input_ria + '.'
            '\n'
            'It might be because that latest commits in'
            ' `analysis` were not pushed to input RIA.'
            " Try running this command at directory '" + self.analysis_path + "': \n"
            '$ datalad push --to input'
        )

        # output ria's commit hash:
        proc_hash_output_ria = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=actual_output_ria_data_dir,  # using the actual one we just got
            stdout=subprocess.PIPE,
        )
        proc_hash_output_ria.check_returncode()
        hash_output_ria = proc_hash_output_ria.stdout.decode('utf-8').replace('\n', '')
        # only throw out a warning if not matched, as after there is branch in output RIA,
        #   not recommend to push updates from analysis to output RIA:
        if hash_analysis != hash_output_ria:
            flag_warning_output_ria = True
            warnings.warn(
                'The hash of current commit of `analysis` datalad dataset does not match'
                ' with that of output RIA.'
                ' Former = ' + hash_analysis + ';'
                ' Latter = ' + hash_output_ria + '.\n'
                'It might be because that latest commits in'
                ' `analysis` were not pushed to output RIA.\n'
                'If there are already successful job(s) finished, please do NOT push updates'
                ' from `analysis` to output RIA.\n'
                "If you're sure there is no successful job finished, you may try running"
                " this command at directory '" + self.analysis_path + "': \n"
                '$ datalad push --to output',
                stacklevel=2,
            )
        else:
            flag_warning_output_ria = False

        if flag_warning_output_ria:
            print(
                'There is warning for output RIA - Please check it out!'
                ' Else in input and output RIA is good.'
            )
        else:
            print(CHECK_MARK + ' All good!')

        # Submit a test job (if requested) --------------------------------
        if not flag_job_test:
            print(
                "\nNot to submit a test job as it's not requested."
                " We recommend running a test job with `--job-test` if you haven't done so;"
                ' It will gather setup information in the designated environment'
                ' and make sure future BABS jobs with current setups'
                ' will be able to finish successfully.'
            )
            print('\n`babs check-setup` was successful! ')
        else:
            print('\nSubmitting a test job, will take a while to finish...')
            print(
                'Although the script will be submitted to a compute node,'
                ' this test job will not run the BIDS App;'
                ' instead, this test job will gather setup information'
                ' in the designated environment'
                ' and make sure future BABS jobs with current setups'
                ' will be able to finish successfully.'
            )

            _, job_id_str, log_filename = submit_one_test_job(self.analysis_path, self.queue)
            log_fn = op.join(self.analysis_path, 'logs', log_filename)  # abs path
            o_fn = log_fn.replace('.*', '.o') + '_1'  # add task_id of test job "_1"
            # write this information in a YAML file:
            fn_test_job_info = op.join(
                self.analysis_path, 'code/check_setup', 'test_job_info.yaml'
            )
            if op.exists(fn_test_job_info):
                os.remove(fn_test_job_info)  # remove it

            test_job_info_file = open(fn_test_job_info, 'w')
            test_job_info_file.write('# Information of submitted test job:\n')
            test_job_info_file.write("job_id: '" + job_id_str + "'\n")
            test_job_info_file.write("log_filename: '" + log_filename + "'\n")

            test_job_info_file.close()

            # check job status every 1 min:
            flag_done = False  # whether job is out of queue (True)
            flag_success_test_job = False  # whether job was successfully finished (True)
            print("Will check the test job's status using backoff strategy")
            sleeptime = 1
            while not flag_done:
                time.sleep(sleeptime)
                # check the job status
                df_all_job_status = request_all_job_status(self.queue)
                d_now_str = str(datetime.now())
                to_print = d_now_str + ': '
                if job_id_str + '_1' in df_all_job_status.index.to_list():  # Add task_id
                    # ^^ if `df` is empty, `.index.to_list()` will return []
                    # if the job is still in the queue:
                    # state_category = df_all_job_status.at[job_id_str, '@state']
                    state_code = df_all_job_status.at[job_id_str + '_1', 'state']  # Add task_id
                    # ^^ column `@state`: 'running' or 'pending'

                    # print some information:
                    if state_code == 'r':
                        to_print += 'Test job is running (`r`)...'
                    elif state_code == 'qw':
                        to_print += 'Test job is pending (`qw`)...'
                    elif state_code == 'eqw':
                        to_print += 'Test job is stalled (`eqw`)...'
                    sleeptime = sleeptime * 2
                    print(f'Waiting {sleeptime} seconds before retry')

                else:  # the job is not in queue:
                    flag_done = True
                    # get the last line of the log file:
                    last_line = get_last_line(o_fn).replace('\n', '')
                    # check if it's "SUCCESS":
                    if last_line == 'SUCCESS':
                        flag_success_test_job = True
                        to_print += 'Test job is successfully finished!'
                    else:  # failed:
                        flag_success_test_job = False
                        to_print += 'Test job was not successfully finished'
                        to_print += ' and is currently out of queue.'
                        to_print += " Last line of stdout log file: '" + last_line + "'."
                        to_print += ' Path to the log file: ' + log_fn
                print(to_print)

            if not flag_success_test_job:  # failed
                raise Exception(
                    '\nThere is something wrong probably in the setups.'
                    ' Please check the log files'
                    ' and the `--container_config`'
                    ' provided in `babs init`!'
                )
            else:  # flag_success_test_job == True:
                # go thru `code/check_setup/check_env.yaml`: check if anything wrong:
                fn_check_env_yaml = op.join(
                    self.analysis_path, 'code/check_setup', 'check_env.yaml'
                )
                flag_writable, flag_all_installed = print_versions_from_yaml(fn_check_env_yaml)
                if not flag_writable:
                    raise Exception(
                        'The designated workspace is not writable!'
                        ' Please change it in the YAML file'
                        ' used in `babs init --container-config`,'
                        ' then rerun `babs init` with updated YAML file.'
                    )
                    # NOTE: ^^ currently this is not aligned with YAML file sections;
                    # this will make more sense after adding section of workspace path in YAML file
                if not flag_all_installed:
                    raise Exception(
                        'Some required package(s) were not installed'
                        ' in the designated environment!'
                        ' Please install them in the designated environment,'
                        ' or change the designated environment you hope to use'
                        ' in `--container-config` and rerun `babs init`!'
                    )

                print(
                    'Please check if above versions are the ones you hope to use!'
                    ' If not, please change the version in the designated environment,'
                    ' or change the designated environment you hope to use'
                    ' in `--container-config` and rerun `babs init`.'
                )
                print(CHECK_MARK + ' All good in test job!')
                print('\n`babs check-setup` was successful! ')

        if flag_warning_output_ria:
            print('\nPlease check out the warning for output RIA!')

    def babs_submit(self, count=1, df_job_specified=None):
        """
        This function submits jobs and prints out job status.

        Parameters
        ----------
        count: int
            number of jobs to be submitted
            default: 1
            negative value: to submit all jobs
        df_job_specified: pd.DataFrame or None
            list of specified job(s) to submit.
            columns: 'sub_id' (and 'ses_id', if session)
            If `--job` was not specified in `babs submit`, it will be None.
        """

        #  = 10
        # ^^ if `j_count` is several times of `count_report_progress`, report progress

        # update `analysis_datalad_handle`:
        if self.analysis_datalad_handle is None:
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)

        # `create_job_status_csv(self)` has been called in `babs_status()`
        #   in `cli.py`

        # Load the csv file
        lock_path = self.job_submit_path_abs + '.lock'
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                df_job = read_job_status_csv(self.job_status_path_abs)

                # create and save a job array df to submit
                # (based either on df_job_specified or count):
                df_job_submit = prepare_job_array_df(
                    df_job, df_job_specified, count, self.processing_level
                )
                # only run `babs submit` when there are subjects/sessions not yet submitted
                if df_job_submit.shape[0] > 0:
                    maxarray = str(df_job_submit.shape[0])
                    # run array submission
                    job_id, _, task_id_list, log_filename_list = submit_array(
                        self.analysis_path,
                        self.processing_level,
                        self.queue,
                        maxarray,
                    )
                    # Update `analysis/code/job_submit.csv` with new status
                    df_job_submit_updated = df_submit_update(
                        df_job_submit,
                        job_id,
                        task_id_list,
                        log_filename_list,
                        submitted=True,
                    )
                    # Update `analysis/code/job_status.csv` with new status
                    df_job_updated = df_job.copy()
                    df_job_updated = df_status_update(
                        df_job_updated,
                        df_job_submit_updated,
                        submitted=True,
                    )
                    # COMMENT OUT BECAUSE ONLY 1 JOB IS SUBMITTED AT A TIME
                    # if it's several times of `count_report_progress`:
                    # if (i_progress + 1) % count_report_progress == 0:
                    #     print('So far ' + str(i_progress + 1) + ' jobs have been submitted.')

                    num_rows_to_print = 6
                    print(
                        '\nFirst '
                        + str(num_rows_to_print)
                        + " rows of 'analysis/code/job_status.csv':"
                    )
                    with pd.option_context(
                        'display.max_rows',
                        None,
                        'display.max_columns',
                        None,
                        'display.width',
                        120,
                    ):  # default is 80 characters...
                        # ^^ print all the columns and rows (with returns)
                        print(df_job_updated.head(num_rows_to_print))  # only first several rows

                    # save updated df:
                    df_job_updated.to_csv(self.job_status_path_abs, index=False)
                    df_job_submit_updated.to_csv(self.job_submit_path_abs, index=False)
                # here, the job status was not checked, so message from `report_job_status()`
                #   based on current df is not trustable:
                # # Report the job status:
                # report_job_status(df_job_updated)

        except Timeout:  # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print('Another instance of this application currently holds the lock.')

    def babs_status(
        self,
        flags_resubmit,
        df_resubmit_task_specific=None,
        reckless=False,
        container_config=None,
    ):
        """
        This function checks job status and resubmit jobs if requested.

        Parameters
        ----------
        flags_resubmit: list
            Under what condition to perform job resubmit.
            Element choices are: 'failed', 'pending'.
            CLI does not support 'stalled' right now, as it's not tested.
        df_resubmit_task_specific: pd.DataFrame or None
            list of specified job(s) to resubmit, requested by `--resubmit-job`
            columns: 'sub_id' (and 'ses_id', if session)
            if `--resubmit-job` was not specified in `babs status`, it will be None.
        reckless: bool
            Whether to resubmit jobs listed in `df_resubmit_task_specific`,
            even they're done or running.
            This is used when `--resubmit-job`.
            NOTE: currently this argument has not been tested;
            NOTE: `--reckless` has been removed from `babs status` CLI. Always: `reckless=False`
        container_config: str or None
            Path to a YAML file that contains the configurations
            of how to run the BIDS App container.
            It may include 'alert_log_messages' section
            to be used by babs status.
        """

        # `create_job_status_csv(self)` has been called in `babs_status()`
        #   in `cli.py`

        from .constants import MSG_NO_ALERT_IN_LOGS

        # Load the csv file
        lock_path = self.job_submit_path_abs + '.lock'
        lock = FileLock(lock_path)

        # Prepare for checking alert messages in log files:
        #   get the pre-defined alert messages:
        config_msg_alert = get_config_msg_alert(container_config)

        # Get the list of branches in output RIA:
        proc_git_branch_all = subprocess.run(
            ['git', 'branch', '-a'],
            cwd=self.output_ria_data_dir,
            stdout=subprocess.PIPE,
        )
        proc_git_branch_all.check_returncode()
        msg = proc_git_branch_all.stdout.decode('utf-8')
        list_branches = msg.split()

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                df_job = read_job_status_csv(self.job_status_path_abs)
                df_job_updated = df_job.copy()

                # Get all jobs' status:
                df_all_job_status = request_all_job_status(self.queue)

                # For jobs that have been submitted but not successful yet:
                # Update job status, and resubmit if requested:
                # get the list of jobs submitted, but `is_done` is not True:
                temp = (df_job['has_submitted']) & (~df_job['is_done'])
                list_index_task_tocheck = df_job.index[temp].tolist()
                for i_task in list_index_task_tocheck:
                    # Get basic information for this job:
                    job_id = df_job.at[i_task, 'job_id']
                    job_id_str = str(job_id)
                    task_id = df_job.at[i_task, 'task_id']
                    task_id_str = str(task_id)
                    job_task_id_str = job_id_str + '_' + task_id_str  # eg: 3536406_1
                    log_filename = df_job.at[i_task, 'log_filename']  # with "*"
                    log_fn = op.join(self.analysis_path, 'logs', log_filename)  # abs path
                    o_fn = log_fn.replace('.*', '.o')

                    # did_resubmit = False   # reset: did not resubmit this job

                    if self.processing_level == 'subject':
                        sub = df_job.at[i_task, 'sub_id']
                        ses = None
                        branchname = 'job-' + job_id_str + '-' + sub
                        # e.g., job-00000-sub-01
                    elif self.processing_level == 'session':
                        sub = df_job.at[i_task, 'sub_id']
                        ses = df_job.at[i_task, 'ses_id']
                        branchname = 'job-' + job_id_str + '-' + sub + '-' + ses
                        # e.g., job-00000-sub-01-ses-B

                    # Check if resubmission of this task is requested:
                    if_request_resubmit_this_task = False
                    if df_resubmit_task_specific is not None:
                        if self.processing_level == 'subject':
                            temp = df_resubmit_task_specific['sub_id'] == sub
                        elif self.processing_level == 'session':
                            temp = (df_resubmit_task_specific['sub_id'] == sub) & (
                                df_resubmit_task_specific['ses_id'] == ses
                            )

                        if any(temp):  # any matched; `temp` is pd.Series of True or False
                            if_request_resubmit_this_task = True
                            # print("debugging purpose: request to resubmit job: " + sub + ", "
                            #  + ses)
                            # ^^ only for session!

                    # Update the "last_line_stdout_file":
                    df_job_updated.at[i_task, 'last_line_stdout_file'] = get_last_line(o_fn)

                    # Check if any alert message in log files for this job:
                    # NOTE: in theory can skip failed jobs in previous round,
                    #       but making assigning variables hard; so not to skip
                    #       if df_job.at[i_job, "is_failed"] is not True:    # np.nan or False
                    (
                        alert_message_in_log_files,
                        if_no_alert_in_log,
                        if_found_log_files,
                    ) = get_alert_message_in_log_files(config_msg_alert, log_fn)
                    # ^^ the function will handle even if `config_msg_alert=None`
                    df_job_updated.at[i_task, 'alert_message'] = alert_message_in_log_files

                    # Check if there is a branch in output RIA:
                    #   check if branch name of current job is in the list of all branches:
                    if branchname in list_branches:
                        # found the branch:
                        df_job_updated.at[i_task, 'is_done'] = True
                        # reset/update:
                        df_job_updated.at[i_task, 'job_state_category'] = np.nan
                        df_job_updated.at[i_task, 'job_state_code'] = np.nan
                        df_job_updated.at[i_task, 'duration'] = np.nan
                        #   ROADMAP: ^^ get duration via `qacct`
                        #       (though qacct may not be accurate)
                        df_job_updated.at[i_task, 'is_failed'] = False

                        # check if echoed "SUCCESS":
                        # TODO ^^

                    else:  # did not find the branch
                        # Check the job status:
                        if job_task_id_str in df_all_job_status.index.to_list():
                            # ^^ if `df` is empty, `.index.to_list()` will return []
                            state_category = df_all_job_status.at[job_task_id_str, '@state']
                            state_code = df_all_job_status.at[job_task_id_str, 'state']
                            # ^^ column `@state`: 'running' or 'pending'

                            if state_code == 'r':
                                # Check if resubmit is requested:
                                if if_request_resubmit_this_task & (not reckless):
                                    # requested resubmit, but without `reckless`: print msg
                                    to_print = 'Although resubmission for job: ' + sub
                                    if self.processing_level == 'session':
                                        to_print += ', ' + ses
                                    to_print += (
                                        ' was requested, as this job is running,'
                                        " BABS won't resubmit this job."
                                    )
                                    # NOTE: removed "and `--reckless` was not specified, "
                                    #   can add this ^^ back after supporting `--reckless` in CLI
                                    warnings.warn(to_print, stacklevel=2)

                                else:  # just let it run:
                                    df_job_updated.at[i_task, 'job_state_category'] = (
                                        state_category
                                    )
                                    df_job_updated.at[i_task, 'job_state_code'] = state_code
                                    # get the duration:
                                    if 'duration' in df_all_job_status:
                                        # e.g., slurm `squeue` automatically returns the duration,
                                        #   so no need to calcu again.
                                        duration = df_all_job_status.at[
                                            job_task_id_str, 'duration'
                                        ]
                                    else:
                                        # This duration time may be slightly longer than actual
                                        # time, as this is using current time, instead of
                                        # the time when `qstat`/requesting job queue.
                                        duration = calcu_runtime(
                                            df_all_job_status.at[job_task_id_str, 'JAT_start_time']
                                        )
                                    df_job_updated.at[i_task, 'duration'] = duration

                                    # do nothing else, just wait

                            elif state_code == 'qw':
                                # pending so set `is_failed` to False
                                df_job_updated.at[i_task, 'is_failed'] = False
                                # resubmit pending
                                if ('pending' in flags_resubmit) or (
                                    if_request_resubmit_this_task
                                ):
                                    # Resubmit:
                                    # did_resubmit = True
                                    df_job_updated.at[i_task, 'needs_resubmit'] = True

                                    # print a message:
                                    to_print = 'Resubmit job for ' + sub
                                    if self.processing_level == 'session':
                                        to_print += ', ' + ses
                                    to_print += ', as it was pending and resubmit was requested.'
                                    print(to_print)

                                    # kill original one
                                    proc_kill = subprocess.run(
                                        [
                                            get_cmd_cancel_job(self.queue),
                                            job_id_str,
                                        ],  # e.g., `qdel <job_id>`
                                        stdout=subprocess.PIPE,
                                    )
                                    proc_kill.check_returncode()
                                    # RESUBMIT ARRAY BELOW

                                else:  # not to resubmit:
                                    # update fields:
                                    df_job_updated.at[i_task, 'job_state_category'] = (
                                        state_category
                                    )
                                    df_job_updated.at[i_task, 'job_state_code'] = state_code

                        else:  # did not find in `df_all_job_status`, i.e., job queue
                            # probably error
                            df_job_updated.at[i_task, 'is_failed'] = True
                            # reset:
                            df_job_updated.at[i_task, 'job_state_category'] = np.nan
                            df_job_updated.at[i_task, 'job_state_code'] = np.nan
                            df_job_updated.at[i_task, 'duration'] = np.nan
                            # ROADMAP: ^^ get duration via `qacct`
                            if if_found_log_files is False:  # bool or np.nan
                                # If there is no log files, the alert message would be 'np.nan';
                                # however this is a failed job, so it should have log files,
                                #   unless it was killed by the user when pending.
                                # change the 'alert_message' to no alert in logs,
                                #   so that when reporting job status,
                                #   info from job accounting will be reported
                                df_job_updated.at[i_task, 'alert_message'] = MSG_NO_ALERT_IN_LOGS

                            # check the log file:
                            # TODO ^^
                            # TODO: assign error category in df; also print it out

                            # resubmit if requested:
                            elif ('failed' in flags_resubmit) or (if_request_resubmit_this_task):
                                # Resubmit:
                                # did_resubmit = True
                                df_job_updated.at[i_task, 'needs_resubmit'] = True

                                # print a message:
                                to_print = 'Resubmit job for ' + sub
                                if self.processing_level == 'session':
                                    to_print += ', ' + ses
                                to_print += ', as it failed and resubmit was requested.'
                                print(to_print)

                                # no need to kill original one!
                                #   As it already failed and out of job queue...
                                # RESUBMIT ARRAY BELOW

                            else:  # resubmit 'error' was not requested:
                                # reset:
                                df_job_updated.at[i_task, 'job_state_category'] = np.nan
                                df_job_updated.at[i_task, 'job_state_code'] = np.nan
                                df_job_updated.at[i_task, 'duration'] = np.nan
                                # ROADMAP: ^^ get duration via `qacct`

                # Collect all to-be-resubmitted tasks into a single DataFrame
                df_job_resubmit = df_job_updated[df_job_updated['needs_resubmit']].copy()
                df_job_resubmit.reset_index(drop=True, inplace=True)
                if df_job_resubmit.shape[0] > 0:
                    maxarray = str(df_job_resubmit.shape[0])
                    # run array submission
                    job_id, _, task_id_list, log_filename_list = submit_array(
                        self.analysis_path,
                        self.processing_level,
                        self.queue,
                        maxarray,
                    )
                    # Update `analysis/code/job_submit.csv` with new status
                    df_job_resubmit_updated = df_submit_update(
                        df_job_resubmit,
                        job_id,
                        task_id_list,
                        log_filename_list,
                        submitted=True,
                    )
                    # Update `analysis/code/job_status.csv` with new status
                    df_job_updated = df_status_update(
                        df_job_updated,
                        df_job_resubmit_updated,
                        submitted=True,
                    )
                    df_job_resubmit_updated.to_csv(self.job_submit_path_abs, index=False)
                # Done: submitted jobs that not 'is_done'

                # For 'is_done' jobs in previous round:
                temp = (df_job['has_submitted']) & (df_job['is_done'])
                list_index_task_is_done = df_job.index[temp].tolist()
                for i_task in list_index_task_is_done:
                    # Get basic information for this job:
                    job_id = df_job.at[i_task, 'job_id']
                    job_id_str = str(job_id)
                    task_id = df_job.at[i_task, 'task_id']
                    task_id_str = str(task_id)
                    job_task_id_str = job_id_str + '_' + task_id_str  # eg: 3536406_1
                    log_filename = df_job.at[i_task, 'log_filename']  # with "*"
                    log_fn = op.join(self.analysis_path, 'logs', log_filename)  # abs path
                    o_fn = log_fn.replace('.*', '.o')

                    if self.processing_level == 'subject':
                        sub = df_job.at[i_task, 'sub_id']
                        ses = None
                        branchname = 'job-' + job_id_str + '-' + sub
                        # e.g., job-00000-sub-01
                    elif self.processing_level == 'session':
                        sub = df_job.at[i_task, 'sub_id']
                        ses = df_job.at[i_task, 'ses_id']
                        branchname = 'job-' + job_id_str + '-' + sub + '-' + ses
                        # e.g., job-00000-sub-01-ses-B

                    # Check if resubmission of this job is requested:
                    if_request_resubmit_this_task = False
                    if df_resubmit_task_specific is not None:
                        if self.processing_level == 'subject':
                            temp = df_resubmit_task_specific['sub_id'] == sub
                        elif self.processing_level == 'session':
                            temp = (df_resubmit_task_specific['sub_id'] == sub) & (
                                df_resubmit_task_specific['ses_id'] == ses
                            )

                        if any(temp):  # any matched; `temp` is pd.Series of True or False
                            if_request_resubmit_this_task = True
                            # print("debugging purpose: request to resubmit job:" + sub + ", "
                            #  + ses)
                            # ^^ only for session

                    # if want to resubmit, but `--reckless` is NOT specified: print msg:
                    if if_request_resubmit_this_task & (not reckless):
                        to_print = 'Although resubmission for job: ' + sub
                        if self.processing_level == 'session':
                            to_print += ', ' + ses
                        to_print += (
                            " was requested, as this job is done, BABS won't resubmit this job."
                        )
                        # NOTE: removed "and `--reckless` was not specified, "
                        #   can add this ^^ back after supporting `--reckless` in CLI
                        warnings.warn(to_print, stacklevel=2)

                    # COMMENT OUT BECAUSE reckless is always False
                    # AND THIS HAS BEEN REMOVE FROM CLI
                    # if resubmit is requested, and `--reckless` is specified:
                    # if if_request_resubmit_this_task & reckless:
                    #     # Resubmit:
                    #     # did_resubmit = True
                    #     # print a message:
                    #     to_print = "Resubmit job for " + sub
                    #     if self.processing_level == "session":
                    #         to_print += ", " + ses
                    #     to_print += ", although it is done," \
                    #         + " resubmit for this job was requested" \
                    #         + " and `--reckless` was specified."
                    #     print(to_print)

                    #     # TODO: delete the original branch?

                    #     # kill original one
                    #     proc_kill = subprocess.run(
                    #         [get_cmd_cancel_job(self.queue),
                    #          job_id_str],   # e.g., `qdel <job_id>`
                    #         stdout=subprocess.PIPE
                    #     )
                    #     proc_kill.check_returncode()
                    #     # submit new one:
                    #     job_id_updated, _, log_filename = \
                    #         submit_one_job(self.analysis_path,
                    #                        self.processing_level,
                    #                        self.queue,
                    #                        sub, ses)
                    #     # update fields:
                    #     df_job_updated = df_update_one_job(df_job_updated, i_job, job_id_updated,
                    #                                        log_filename, done=False, debug=True)

                    else:  # did not request resubmit, or `--reckless` is None:
                        # just perform normal stuff for a successful job:
                        # Update the "last_line_stdout_file":
                        df_job_updated.at[i_task, 'last_line_stdout_file'] = get_last_line(o_fn)
                        # Check if any alert message in log files for this job:
                        #   this is to update `alert_message` in case user changes configs in yaml
                        alert_message_in_log_files, if_no_alert_in_log, _ = (
                            get_alert_message_in_log_files(config_msg_alert, log_fn)
                        )
                        # ^^ the function will handle even if `config_msg_alert=None`
                        df_job_updated.at[i_task, 'alert_message'] = alert_message_in_log_files
                # Done: 'is_done' jobs.

                # For jobs that haven't been submitted yet:
                #   just to throw out warnings if `--resubmit-job` was requested...
                if df_resubmit_task_specific is not None:
                    # only keep those not submitted:
                    df_job_not_submitted = df_job[~df_job['has_submitted']]
                    # only keep columns of `sub_id` and `ses_id`:
                    if self.processing_level == 'subject':
                        df_job_not_submitted_slim = df_job_not_submitted[['sub_id']]
                    elif self.processing_level == 'session':
                        df_job_not_submitted_slim = df_job_not_submitted[['sub_id', 'ses_id']]

                    # check if `--resubmit-job` was requested for any these jobs:
                    df_intersection = df_resubmit_task_specific.merge(df_job_not_submitted_slim)
                    if len(df_intersection) > 0:
                        warnings.warn(
                            'Jobs for some of the subjects (and sessions) requested in'
                            " `--resubmit-job` haven't been submitted yet."
                            ' Please use `babs submit` first.',
                            stacklevel=2,
                        )
                # Done: jobs that haven't submitted yet

                # Finish up `babs status`:
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

        except Timeout:  # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print('Another instance of this application currently holds the lock.')

    def babs_merge(self, chunk_size, trial_run):
        """
        This function merges results and provenance from all successfully finished jobs.

        Parameters
        ----------
        chunk_size: int
            Number of branches in a chunk when merging at a time.
        trial_run: bool
            Whether to run as a trial run which won't push the merging actions back to output RIA.
            This option should only be used by developers for testing purpose.
        """
        if_any_warning = False
        self.wtf_key_info()  # get `self.analysis_dataset_id`
        # path to `merge_ds`:
        merge_ds_path = op.join(self.project_root, 'merge_ds')

        if op.exists(merge_ds_path):
            raise Exception(
                "Folder 'merge_ds' already exists. `babs merge` won't proceed."
                " If you're sure you want to rerun `babs merge`,"
                ' please remove this folder before you rerun `babs merge`.'
                " Path to 'merge_ds': '" + merge_ds_path + "'. "
            )

        # Define (potential) text files:
        #   in 'merge_ds/code' folder
        #   as `merge_ds` should not exist at the moment,
        #   no need to check existence/remove these files.
        # define path to text file of invalid job list exists:
        fn_list_invalid_jobs = op.join(merge_ds_path, 'code', 'list_invalid_job_when_merging.txt')
        # define path to text file of files with missing content:
        fn_list_content_missing = op.join(merge_ds_path, 'code', 'list_content_missing.txt')
        # define path to printed messages from `git annex fsck`:
        # ^^ this will be absolutely used if `babs merge` does not fail:
        fn_msg_fsck = op.join(merge_ds_path, 'code', 'log_git_annex_fsck.txt')

        # Clone output RIA to `merge_ds`:
        print("Cloning output RIA to 'merge_ds'...")
        # get the path to output RIA:
        #   'ria+file:///path/to/BABS_project/output_ria#0000000-000-xxx-xxxxxxxx'
        output_ria_source = self.output_ria_url + '#' + self.analysis_dataset_id
        # clone: `datalad clone ${outputsource} merge_ds`
        dlapi.clone(source=output_ria_source, path=merge_ds_path)

        # List all branches in output RIA:
        print('\nListing all branches in output RIA...')
        # get all branches:
        proc_git_branch_all = subprocess.run(
            ['git', 'branch', '-a'], cwd=merge_ds_path, stdout=subprocess.PIPE
        )
        proc_git_branch_all.check_returncode()
        msg = proc_git_branch_all.stdout.decode('utf-8')
        list_branches_all = msg.split()

        # only keep those having pattern `job-`:
        list_branches_jobs = [ele for ele in list_branches_all if 'job-' in ele]
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
            raise Exception(
                'There is no successfully finished job yet. Please run `babs submit` first.'
            )

        # Find all valid branches (i.e., those with results --> have different SHASUM):
        print('\nFinding all valid job branches to merge...')
        # get default branch's name: master or main:
        #   `git remote show origin | sed -n '/HEAD branch/s/.*: //p'`
        proc_git_remote_show_origin = subprocess.run(
            ['git', 'remote', 'show', 'origin'],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE,
        )
        proc_git_remote_show_origin.check_returncode()
        msg = proc_git_remote_show_origin.stdout.decode('utf-8')
        # e.g., '... HEAD branch: master\n....': search between 'HEAD branch: ' and '\n':
        temp = re.search('HEAD branch: ' + '(.+?)' + '\n', msg)
        if temp:  # not empty:
            default_branch_name = temp.group(1)  # what's between those two keywords
            # another way: `default_branch_name = msg.split("HEAD branch: ")[1].split("\n")[0]`
        else:
            raise Exception('There is no HEAD branch in output RIA!')
        print("Git default branch's name of output RIA is: '" + default_branch_name + "'")

        # get current git commit SHASUM before merging as a reference:
        git_ref, _ = get_git_show_ref_shasum(default_branch_name, merge_ds_path)

        # check if each job branch has a new commit
        #   that's different from current git commit SHASUM (`git_ref`):
        list_branches_no_results = []
        list_branches_with_results = []
        for branch_job in list_branches_jobs:
            # get the job's `git show-ref`:
            git_ref_branch_job, _ = get_git_show_ref_shasum(branch_job, merge_ds_path)
            if git_ref_branch_job == git_ref:  # no new commit --> no results in this branch
                list_branches_no_results.append(branch_job)
            else:  # has results:
                list_branches_with_results.append(branch_job)

        # check if there is any valid job (with results):
        if len(list_branches_with_results) == 0:  # empty:
            raise Exception(
                'There is no job branch in output RIA that has results yet,'
                ' i.e., there is no successfully finished job yet.'
                ' Please run `babs submit` first.'
            )

        # check if there is invalid job (without results):
        if len(list_branches_no_results) > 0:  # not empty
            # save to a text file:
            #   note: this file has been removed at the beginning of babs_merge() if it existed)
            if_any_warning = True
            warnings.warn(
                'There are invalid job branch(es) in output RIA,'
                ' and these job(s) do not have results.'
                ' The list of such invalid jobs will be saved to'
                " the following text file: '" + fn_list_invalid_jobs + "'."
                ' Please review it.',
                stacklevel=2,
            )
            with open(fn_list_invalid_jobs, 'w') as f:
                f.write('\n'.join(list_branches_no_results))
                f.write('\n')  # add a new line at the end
        # NOTE to developers: when testing ^^:
        #   You can `git branch job-test` in `output_ria/000/000-000` to make a fake branch
        #       that has the same SHASUM as master branch's
        #       then you should see above warning.
        #   However, if you finish running `babs merge`, this branch `job-test` will have
        #       a *different* SHASUM from master's, making it a "valid" job now.
        #   To continue testing above warning, you need to delete this branch:
        #       `git branch --delete job-test` in `output_ria/000/000-000`
        #       then re-create a new one: `git branch job-test`

        # Merge valid branches chunk by chunk:
        print('\nMerging valid job branches chunk by chunk...')
        print('Total number of job branches to merge = ' + str(len(list_branches_with_results)))
        print('Chunk size (number of job branches per chunk) = ' + str(chunk_size))
        # turn the list into numpy array:
        arr = np.asarray(list_branches_with_results)
        # ^^ e.g., array([1, 7, 0, 6, 2, 5, 6])   # but with `dtype='<U24'`
        # split into several chunks:
        num_chunks = ceildiv(len(arr), chunk_size)
        print('--> Number of chunks = ' + str(num_chunks))
        all_chunks = np.array_split(arr, num_chunks)
        # ^^ e.g., [array([1, 7, 0]), array([6, 2]), array([5, 6])]

        # iterate across chunks:
        for i_chunk in range(0, num_chunks):
            print(
                'Merging chunk #'
                + str(i_chunk + 1)
                + ' (total of '
                + str(num_chunks)
                + ' chunk[s] to merge)...'
            )
            the_chunk = all_chunks[i_chunk]  # e.g., array(['a', 'b', 'c'])
            # join all branches in this chunk:
            joined_by_space = ' '.join(the_chunk)  # e.g., 'a b c'
            # command to run:
            commit_msg = 'merge results chunk ' + str(i_chunk + 1) + '/' + str(num_chunks)
            # ^^ okay to not to be quoted,
            #   as in `subprocess.run` this is a separate element in the `cmd` list
            cmd = ['git', 'merge', '-m', commit_msg] + joined_by_space.split(' ')  # split by space
            proc_git_merge = subprocess.run(cmd, cwd=merge_ds_path, stdout=subprocess.PIPE)
            proc_git_merge.check_returncode()
            print(proc_git_merge.stdout.decode('utf-8'))

        # Push merging actions back to output RIA:
        if not trial_run:
            print('\nPushing merging actions to output RIA...')
            # `git push`:
            proc_git_push = subprocess.run(
                ['git', 'push'], cwd=merge_ds_path, stdout=subprocess.PIPE
            )
            proc_git_push.check_returncode()
            print(proc_git_push.stdout.decode('utf-8'))

            # Get file availability information: which is very important!
            # `git annex fsck --fast -f output-storage`:
            #   `git annex fsck` = file system check
            #   We've done the git merge of the symlinks of the files,
            #   now we need to match the symlinks with the data content in `output-storage`.
            #   `--fast`: just use the existing MD5, not to re-create a new one
            proc_git_annex_fsck = subprocess.run(
                ['git', 'annex', 'fsck', '--fast', '-f', 'output-storage'],
                cwd=merge_ds_path,
                stdout=subprocess.PIPE,
            )
            proc_git_annex_fsck.check_returncode()
            # if printing the returned msg,
            #   will be a long list of "fsck xxx.zip (fixing location log) ok"
            #   or "fsck xxx.zip ok"
            # instead, save it into a text file:
            with open(fn_msg_fsck, 'w') as f:
                f.write(
                    '# Below are printed messages from'
                    ' `git annex fsck --fast -f output-storage`:\n\n'
                )
                f.write(proc_git_annex_fsck.stdout.decode('utf-8'))
                f.write('\n')
            # now we can delete `proc_git_annex_fsck` to save memory:
            del proc_git_annex_fsck

            # Double check: there should not be file content that's not in `output-storage`:
            #   This should not print anything - we never has this error before
            # `git annex find --not --in output-storage`
            proc_git_annex_find_missing = subprocess.run(
                ['git', 'annex', 'find', '--not', '--in', 'output-storage'],
                cwd=merge_ds_path,
                stdout=subprocess.PIPE,
            )
            proc_git_annex_find_missing.check_returncode()
            msg = proc_git_annex_find_missing.stdout.decode('utf-8')
            # `msg` should be empty:
            if msg != '':  # if not empty:
                # save into a file:
                with open(fn_list_content_missing, 'w') as f:
                    f.write(msg)
                    f.write('\n')
                raise Exception(
                    'Unable to find file content for some file(s).'
                    " The information has been saved to this text file: '"
                    + fn_list_content_missing
                    + "'."
                )

            # `git annex dead here`:
            #   stop tracking clone `merge_ds`,
            #   i.e., not to get data from this `merge_ds` sibling:
            proc_git_annex_dead_here = subprocess.run(
                ['git', 'annex', 'dead', 'here'],
                cwd=merge_ds_path,
                stdout=subprocess.PIPE,
            )
            proc_git_annex_dead_here.check_returncode()
            print(proc_git_annex_dead_here.stdout.decode('utf-8'))

            # Final `datalad push` to output RIA:
            # `datalad push --data nothing`:
            #   pushing to `git` branch in output RIA: has done with `git push`;
            #   pushing to `git-annex` branch in output RIA: hasn't done after `git annex fsck`
            #   `--data nothing`: don't transfer data from this local annex `merge_ds`
            proc_datalad_push = subprocess.run(
                ['datalad', 'push', '--data', 'nothing'],
                cwd=merge_ds_path,
                stdout=subprocess.PIPE,
            )
            proc_datalad_push.check_returncode()
            print(proc_datalad_push.stdout.decode('utf-8'))

            # Done:
            if if_any_warning:
                print(
                    '\n`babs merge` has finished but had warning(s)!'
                    ' Please check out the warning message(s) above!'
                )
            else:
                print('\n`babs merge` was successful!')

        else:  # `--trial-run` is on:
            print('')  # new empty line
            warnings.warn(
                '`--trial-run` was requested, not to push merging actions to output RIA.',
                stacklevel=2,
            )
            print('\n`babs merge` did not fully finish yet!')

    def babs_unzip(self, container_config):
        """
        This function unzips results and extract desired files.
        This is done in 3 steps:
        1. Generate scripts used by `babs-unzip`
        2. Run scripts to unzip data
        3. Merge all branches of unzipping

        Parameters
        ----------
        config: dict
            loaded container config yaml file
        """

        # ====================================================
        # Generate scripts used by `babs-unzip`
        # ====================================================

        # Prepare input_ds_unzip:
        # Call `babs_bootstrap()`:
        #   !!!! using babs_proj_unzip, instead current `self`!!!

        print('TODO')

        # ====================================================
        # Run scripts to unzip data
        # ====================================================

        # ====================================================
        # Merge all branches of unzipping
        # ====================================================
