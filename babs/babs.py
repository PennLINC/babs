"""This is the main module."""

import os
import os.path as op
import re
import subprocess
import time
import warnings
from urllib.parse import urlparse

import datalad.api as dlapi
import numpy as np
import pandas as pd
from jinja2 import Environment, PackageLoader, StrictUndefined

from babs.constants import CHECK_MARK
from babs.container import Container
from babs.scheduler import (
    report_job_status,
    request_all_job_status,
    submit_array,
    submit_one_test_job,
)
from babs.system import validate_queue
from babs.utils import (
    combine_inclusion_dataframes,
    compare_repo_commit_hashes,
    get_git_show_ref_shasum,
    get_immediate_subdirectories,
    get_latest_submitted_jobs_columns,
    get_results_branches,
    identify_running_jobs,
    print_versions_from_yaml,
    read_yaml,
    results_branch_dataframe,
    results_status_columns,
    results_status_default_values,
    status_dtypes,
    update_job_batch_status,
    update_results_status,
    update_submitted_job_ids,
    validate_processing_level,
)

EMPTY_JOB_STATUS_DF = pd.DataFrame(
    columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'has_results']
)
EMPTY_JOB_SUBMIT_DF = pd.DataFrame(columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'state'])


class BABS:
    """The BABS class is for babs projects of BIDS Apps"""

    def __init__(self, project_root, processing_level, queue):
        """The BABS class is for babs projects of BIDS Apps.

        The constructor only initializes the attributes.
        The actual initialization (e.g., creating the RIA stores, finding
        the subjects/sessions to analyze) is done in `babs_bootstrap()`.

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

    def babs_bootstrap(
        self,
        input_ds,
        container_ds,
        container_name,
        container_config,
        system,
        initial_inclusion_df=None,
    ):
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
        initial_inclusion_df: pd.DataFrame
            initial inclusion dataframe of subjects/sessions to analyze
        """
        # Make a directory of project_root:
        os.makedirs(self.project_root)  # we don't allow creation if folder exists

        # Create `analysis` folder: -----------------------------
        print('\nCreating `analysis` folder (also a datalad dataset)...')
        self.analysis_datalad_handle = dlapi.create(
            self.analysis_path, cfg_proc='yoda', annex=True
        )
        input_ds.update_abs_paths(self.analysis_path)

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
        for idx, in_ds in enumerate(input_ds):
            # path to cloned dataset:
            dataset_name = in_ds.name
            dataset_source = in_ds.origin_url

            print(f'Cloning input dataset #{idx + 1}: {dataset_name}')

            # clone input dataset(s) as sub-dataset into `analysis` dataset:
            dlapi.clone(
                dataset=self.analysis_path,
                source=dataset_source,
                path=in_ds.babs_project_analysis_path,
            )

            # amend the previous commit with a nicer commit message:
            commit_message = f"Register input data dataset '{dataset_name}' as a subdataset"
            git_cmd = ['git', 'commit', '--amend', '-m', commit_message]

            result = subprocess.run(
                git_cmd,
                cwd=self.analysis_path,
                stdout=subprocess.PIPE,
                check=True,
            )
            result.check_returncode()

        # get the current absolute path to the input dataset:
        input_ds.update_abs_paths(self.analysis_path)

        # Perform checks on the inputs:
        input_ds.validate_input_contents()

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
        self._init_import_files(container.config.get('imported_files', []))

        print('\nDetermining the list of subjects (and sessions) to analyze...')
        sub_ses_inclusion_df = input_ds.generate_inclusion_dataframe()

        # If the user sent an initial inclusion dataframe, combine it with the one
        # generated by the input datasets
        if initial_inclusion_df is not None:
            sub_ses_inclusion_df = combine_inclusion_dataframes(
                [initial_inclusion_df, sub_ses_inclusion_df]
            )
            if sub_ses_inclusion_df.empty:
                raise ValueError(
                    'No subjects/sessions to analyze!'
                    ' Please check the inclusion file you provided.'
                )
            if sub_ses_inclusion_df.shape[0] < initial_inclusion_df.shape[0]:
                print(
                    'Warning: The initial inclusion dataframe you provided '
                    'contains fewer subjects/sessions than the input datasets.'
                )
        # Create the inclusion file
        sub_ses_inclusion_df.to_csv(self.list_sub_path_abs, index=False)
        self.datalad_save(
            path=self.list_sub_path_abs,
            message='Record of inclusion/exclusion of participants/sessions',
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

        print('\nFinal steps...')
        # No need to keep the input dataset(s):
        #   old version: datalad uninstall -r --nocheck inputs/data
        print("DataLad dropping input dataset's contents...")
        for in_ds in input_ds:
            _ = self.analysis_datalad_handle.drop(
                path=in_ds.babs_project_analysis_path,
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

        # Initialize the job status csv file:
        self._create_initial_job_status_csv()

        print('\n')
        print(
            'BABS project has been initialized!'
            " Path to this BABS project: '" + self.project_root + "'"
        )
        print('`babs init` was successful!')

    def _init_import_files(self, file_list):
        """
        Import files into the BABS project and datalad save.

        Parameters
        ----------
        file_list: list
            List of dictionaries containing the following keys:
            - 'original_path': str
                The path to the file in the BABS project
            - 'analysis_path': str
                The path to the file in the analysis folder
        """
        imported_files = []
        for imported_file in file_list:
            # Check that the file exists:
            if not op.exists(imported_file['original_path']):
                raise FileNotFoundError(
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

                print('Removing input dataset(s) if cloned...')
                for in_ds in input_ds:
                    if op.exists(in_ds.babs_project_analysis_path):
                        # use `datalad remove` to remove:
                        _ = self.analysis_datalad_handle.remove(
                            path=in_ds.babs_project_analysis_path, reckless='modification'
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

    def babs_check_setup(self, input_ds, submit_a_test_job):
        """
        This function validates the setup by babs init.

        Parameters
        ----------
        input_ds: class `InputDatasets`
            information of input dataset(s)
        submit_a_test_job: bool
            Whether to submit and run a test job.
        """
        babs_proj_config = read_yaml(self.config_path, use_filelock=True)

        print('Checking setup of BABS project located at: ' + self.project_root)
        if submit_a_test_job:
            print('Will submit a test job for testing; will take longer time.')
        else:
            print('Did not request `--job-test`; will not submit a test job.')

        # Print out the saved configuration info: ----------------
        print(
            'Below is the configuration information saved during `babs init`'
            " in file 'analysis/code/babs_proj_config.yaml':\n"
        )
        with open(op.join(self.analysis_path, 'code/babs_proj_config.yaml')) as f:
            file_contents = f.read()
        print(file_contents)

        # Check the project itself: ---------------------------
        print('Checking the BABS project itself...')
        if not op.exists(self.analysis_path):
            raise FileNotFoundError(
                "Folder 'analysis' does not exist in this BABS project!"
                ' Current path to analysis folder: ' + self.analysis_path
            )
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
            raise ValueError(
                "Analysis DataLad dataset's status is not clean. "
                'There are the following issues:' + str(problem_statuses)
            )

        print(CHECK_MARK + ' All good!')

        # Check input dataset(s): ---------------------------
        print('\nChecking input dataset(s)...')
        # check if there is at least one folder in the `inputs/data` dir:
        temp_list = get_immediate_subdirectories(op.join(self.analysis_path, 'inputs/data'))
        if not temp_list:
            raise ValueError(
                "There is no sub-directory (i.e., no input dataset) in 'inputs/data'!"
                " Full path to folder 'inputs/data': " + op.join(self.analysis_path, 'inputs/data')
            )

        # check each input ds:
        for idx, in_ds in enumerate(input_ds):
            abs_path = in_ds.babs_project_analysis_path
            dataset_name = in_ds.name

            # check if the dir of this input ds exists:
            if not op.exists(abs_path):
                raise FileNotFoundError(
                    f'The path to the cloned input dataset #{idx + 1} '
                    f"'{dataset_name}' does not exist: {abs_path}"
                )

            # check if dir of input ds is a datalad dataset:
            if not op.exists(op.join(abs_path, '.datalad/config')):
                raise ValueError(
                    f'The input dataset #{idx + 1} '
                    f"'{dataset_name}' is not a valid DataLad dataset:"
                    f" There is no file '.datalad/config' in its directory: {abs_path}"
                )
        print(CHECK_MARK + ' All good!')

        # Check container datalad dataset: ---------------------------
        print('\nChecking container datalad dataset...')
        folder_container = op.join(self.analysis_path, 'containers')
        container_name = babs_proj_config['container']['name']
        # assert it's a datalad ds in `containers` folder:
        if not op.exists(op.join(folder_container, '.datalad/config')):
            raise FileNotFoundError(
                'There is no containers DataLad dataset in folder: ' + folder_container
            )
        print(CHECK_MARK + ' All good!')

        # Check `analysis/code`: ---------------------------------
        print('\nChecking `analysis/code/` folder...')
        # folder `analysis/code` should exist:
        if not op.exists(op.join(self.analysis_path, 'code')):
            raise FileNotFoundError("Folder 'code' does not exist in 'analysis' folder!")

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
            if not op.isfile(temp_fn):
                raise FileNotFoundError(
                    "Required file '"
                    + temp_filename
                    + "' does not exist"
                    + " in 'analysis/code' folder in this BABS project!"
                )
            # check if bash files are executable:
            if op.splitext(temp_fn)[1] == '.sh':  # extension is '.sh':
                if not os.access(temp_fn, os.X_OK):
                    raise PermissionError('This code file should be executable: ' + temp_fn)
        print(CHECK_MARK + ' All good!')

        # Check input and output RIA: ----------------------
        print('\nChecking input and output RIA...')

        # check if they are siblings of `analysis`:
        actual_output_ria_data_dir = urlparse(
            os.readlink(op.join(self.output_ria_path, 'alias/data'))
        ).path  # get the symlink of `alias/data` then change to path
        if not op.exists(actual_output_ria_data_dir):
            raise FileNotFoundError(
                'The output RIA data directory does not exist: ' + actual_output_ria_data_dir
            )
        # get '000/0000-0000-0000-0000':
        data_foldername = op.join(
            op.basename(op.dirname(actual_output_ria_data_dir)),
            op.basename(actual_output_ria_data_dir),
        )
        # input_ria:
        actual_input_ria_data_dir = op.join(self.input_ria_path, data_foldername)
        if not op.exists(actual_input_ria_data_dir):
            raise FileNotFoundError(
                'The input RIA data directory does not exist: ' + actual_input_ria_data_dir
            )

        print("\tDatalad dataset `analysis`'s siblings:")
        analysis_siblings = self.analysis_datalad_handle.siblings(action='query')
        has_sibling_input = False
        has_sibling_output = False
        for i_sibling in range(0, len(analysis_siblings)):
            the_sibling = analysis_siblings[i_sibling]
            if the_sibling['name'] == 'output':  # output ria:
                has_sibling_output = True
                if the_sibling['url'] != actual_output_ria_data_dir:
                    raise ValueError(
                        "The `analysis` datalad dataset's sibling 'output' url does not match"
                        ' the path to the output RIA.'
                        ' Former = ' + the_sibling['url'] + ';'
                        ' Latter = ' + actual_output_ria_data_dir
                    )
            if the_sibling['name'] == 'input':  # input ria:
                has_sibling_input = True

        if not has_sibling_input:
            raise ValueError(
                "Did not find a sibling of 'analysis' DataLad dataset"
                " that's called 'input'. There may be something wrong when"
                ' setting up input RIA!'
            )
        if not has_sibling_output:
            raise ValueError(
                "Did not find a sibling of 'analysis' DataLad dataset"
                " that's called 'output'. There may be something wrong when"
                ' setting up output RIA!'
            )

        # check that our RIAs are in sync:
        compare_repo_commit_hashes(
            self.analysis_path,
            actual_input_ria_data_dir,
            'analysis',
            'input RIA',
        )

        compare_repo_commit_hashes(
            self.analysis_path,
            actual_output_ria_data_dir,
            'analysis',
            'output RIA',
        )
        print(CHECK_MARK + ' All good!')

        # Submit a test job (if requested) --------------------------------
        if not submit_a_test_job:
            print(
                '\n'
                " We recommend running a test job with `--job-test` if you haven't done so;"
                ' It will gather setup information in the designated environment'
                ' and make sure future BABS jobs with current setup'
                ' will be able to finish successfully.'
            )
            print('\n`babs check-setup` was successful! ')
        else:
            self._submit_test_job()

    def _submit_test_job(self):
        print('\nSubmitting a test job, will take a while to finish...')
        print(
            'Although the script will be submitted to a compute node,'
            ' this test job will not run the BIDS App;'
            ' instead, this test job will gather setup information'
            ' in the designated environment'
            ' and make sure future BABS jobs with the current setup'
            ' will be able to finish successfully.'
        )

        job_id = submit_one_test_job(self.analysis_path, self.queue)
        job_status = new_job_status = request_all_job_status(self.queue, job_id)

        # Check until the job is out of the queue:
        sleeptime = 0
        while not new_job_status.empty:
            sleeptime += 1
            time.sleep(sleeptime)
            job_status = new_job_status.copy()
            new_job_status = request_all_job_status(self.queue, job_id)

        if not job_status.shape[0] == 1:
            raise Exception(f'Expected 1 job, got {job_status.shape[0]}')

        test_info = job_status.iloc[0].to_dict()

        stdout_path = op.join(
            self.analysis_path,
            'logs',
            f'{test_info["name"]}.o{test_info["job_id"]}_{test_info["task_id"]}',
        )

        # test_job_info_file = open(log_path, 'w')
        # test_job_info_file.write('# Information of submitted test job:\n')
        # test_job_info_file.write("job_id: '" + job_id_str + "'\n")
        # test_job_info_file.write("log_filename: '" + log_filename + "'\n")

        # test_job_info_file.close()

        if not op.exists(stdout_path):
            raise FileNotFoundError('The test job failed to produce an output log.')

        # go thru `code/check_setup/check_env.yaml`: check if anything wrong:
        fn_check_env_yaml = op.join(self.analysis_path, 'code/check_setup', 'check_env.yaml')
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
        print(f'{CHECK_MARK} All good in test job!')
        print('\n`babs check-setup` was successful! ')

    def _create_initial_job_status_csv(self):
        """
        Create the initial job status csv file.
        """
        if op.exists(self.job_status_path_abs):
            return

        # Load the complete list of subjects and optionally sessions
        df_sub = pd.read_csv(self.list_sub_path_abs)
        df_job = df_sub.copy()

        # Fill the columns that should get default values
        for column_name, default_value in results_status_default_values.items():
            df_job[column_name] = default_value

        # ensure dtypes for all the columns
        for column_name in results_status_columns:
            df_job[column_name] = df_job[column_name].astype(status_dtypes[column_name])

        df_job.to_csv(self.job_status_path_abs, index=False)

    def babs_submit(self, count=None, submit_df=None, skip_failed=False):
        """
        This function submits jobs that don't have results yet and prints out job status.

        Parameters
        ----------
        count: int or None
            number of jobs to be submitted
            default: 1
            negative value: to submit all jobs
        submit_df: pd.DataFrame
            dataframe of jobs to be submitted
            default: None
        """
        # update `analysis_datalad_handle`:
        if self.analysis_datalad_handle is None:
            self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)

        # Check if there are still jobs running
        currently_running_df = self.get_currently_running_jobs_df()
        if currently_running_df.shape[0] > 0:
            raise Exception(
                'There are still jobs running. Please wait for them to finish or cancel them.'
                f' Current running jobs:\n{currently_running_df}'
            )

        # Find the rows that don't have results yet
        status_df = self.get_results_status_df()
        df_needs_submit = status_df[~status_df['has_results']].reset_index(drop=True)
        if skip_failed:
            df_needs_submit = df_needs_submit[~df_needs_submit['submitted']]

        if submit_df is not None:
            df_needs_submit = submit_df

        # only run `babs submit` when there are subjects/sessions not yet submitted
        if df_needs_submit.empty:
            print('No jobs to submit')
            return

        # If count is positive, submit the first `count` jobs
        if count is not None:
            print(f'Submitting the first {count} jobs')
            df_needs_submit = df_needs_submit.head(min(count, df_needs_submit.shape[0]))

        # We know task_id ahead of time, so we can add it to the dataframe
        df_needs_submit['task_id'] = np.arange(1, df_needs_submit.shape[0] + 1)
        submit_cols = (
            ['sub_id', 'ses_id', 'job_id', 'task_id']
            if self.processing_level == 'session'
            else ['sub_id', 'job_id', 'task_id']
        )
        # Write the job submission dataframe to a csv file
        df_needs_submit[submit_cols].to_csv(self.job_submit_path_abs, index=False)
        job_id = submit_array(
            self.analysis_path,
            self.queue,
            df_needs_submit.shape[0],
        )

        df_needs_submit['job_id'] = job_id
        # Update the job submission dataframe with the new job id
        print(f'Submitting the following jobs:\n{df_needs_submit}')
        df_needs_submit[submit_cols].to_csv(self.job_submit_path_abs, index=False)

        # Update the results df
        updated_results_df = update_submitted_job_ids(
            self.get_results_status_df(), df_needs_submit[submit_cols]
        )
        updated_results_df.to_csv(self.job_status_path_abs, index=False)

    def _update_results_status(self):
        """
        Update the status of jobs based on results in the output RIA.
        """

        # Step 1: get a list of branches in the output ria to update the status
        list_branches = get_results_branches(self.output_ria_data_dir)
        previous_job_completion_df = self.get_results_status_df()

        if not list_branches:
            return
        # Update the results status
        job_completion_df = results_branch_dataframe(list_branches)
        current_status_df = update_results_status(previous_job_completion_df, job_completion_df)

        # Part 2: Update which jobs are running
        currently_running_df = self.get_currently_running_jobs_df()
        current_status_df = update_job_batch_status(current_status_df, currently_running_df)
        current_status_df['has_results'].fillna(False)
        current_status_df.to_csv(self.job_status_path_abs, index=False)

    def babs_status(self):
        """
        Check job status and makes a nice report.
        """
        self._update_results_status()
        currently_running_df = self.get_currently_running_jobs_df()
        current_results_df = self.get_results_status_df()
        report_job_status(current_results_df, currently_running_df, self.analysis_path)

    def get_latest_submitted_jobs_df(self):
        """
        Get the latest submitted jobs.

        Example:
        --------
        >>> bbs.get_latest_submitted_jobs_df()

            sub_id  job_id  task_id
        0  sub-0001       1        1
        1  sub-0002       1        2

        """
        if not op.exists(self.job_submit_path_abs):
            return EMPTY_JOB_STATUS_DF
        df = pd.read_csv(self.job_submit_path_abs)
        for column_name in get_latest_submitted_jobs_columns(self.processing_level):
            df[column_name] = df[column_name].astype(status_dtypes[column_name])
        return df

    def get_currently_running_jobs_df(self):
        """
        Get the currently running jobs. Subject/session information is added.

        This only reflects currently running jobs, not all of those that have been submitted.
        It is a quick check on job status.

        Examples:
        ---------
        Right after submitting the jobs:
        >>> bbs.get_currently_running_jobs_df()
        job_id  task_id state time_used  time_limit  nodes  cpus partition name    sub_id
        0       1        2    PD      0:00  5-00:00:00      1     1    normal  sim  sub-0002
        1       1        1     R      0:27  5-00:00:00      1     1    normal  sim  sub-0001

        After waiting for a while, the queue will empty:
        >>> bbs.get_currently_running_jobs_df()
        Empty DataFrame
        Columns: [
            job_id, task_id, state, time_used, time_limit, nodes, cpus,
            partition, name, sub_id]
        Index: []

        """
        last_submitted_jobs_df = self.get_latest_submitted_jobs_df()
        if last_submitted_jobs_df.empty:
            return EMPTY_JOB_SUBMIT_DF
        job_ids = last_submitted_jobs_df['job_id'].unique()
        if not len(job_ids) == 1:
            raise Exception(f'Expected 1 job id, got {len(job_ids)}')
        job_id = job_ids[0]
        currently_running_df = request_all_job_status(self.queue, job_id)
        return identify_running_jobs(last_submitted_jobs_df, currently_running_df)

    def get_results_status_df(self):
        """
        Get the results status dataframe.
        """
        if not op.exists(self.job_status_path_abs):
            return EMPTY_JOB_STATUS_DF
        df = pd.read_csv(self.job_status_path_abs)
        for column_name in results_status_columns:
            df[column_name] = df[column_name].astype(status_dtypes[column_name])

        df['has_results'] = df['has_results'].fillna(False)

        return df

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
        warning_encountered = False
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
            warning_encountered = True
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
            if warning_encountered:
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


def ceildiv(a, b):
    """
    This is to calculate the ceiling of division of a/b.
    ref: https://stackoverflow.com/questions/14822184/...
      ...is-there-a-ceiling-equivalent-of-operator-in-python
    """
    return -(a // -b)
