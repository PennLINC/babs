"""This is the main module."""

import os.path as op
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from babs.input_datasets import InputDatasets
from babs.system import validate_queue
from babs.utils import (
    read_yaml,
    validate_processing_level,
)

CONFIG_SECTIONS = ['processing_level', 'queue', 'input_datasets', 'container']


class BABS:
    """The BABS base class holds common attributes and methods for all BABS classes."""

    def __init__(self, project_root):
        """The BABS class is for babs projects of BIDS Apps.

        The constructor only initializes the attributes.

        Parameters
        ----------
        project_root: Path
            absolute path to the root of this babs project

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
            Example: '/path/to/analysis/code/processing_inclusion.csv'
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

        # attributes:
        self.project_root = str(project_root)

        self.analysis_path = op.join(self.project_root, 'analysis')
        self.analysis_datalad_handle = None

        self.config_path = op.join(self.analysis_path, 'code/babs_proj_config.yaml')

        self.input_ria_path = op.join(self.project_root, 'input_ria')
        self.output_ria_path = op.join(self.project_root, 'output_ria')

        self.input_ria_url = 'ria+file://' + self.input_ria_path
        self.output_ria_url = 'ria+file://' + self.output_ria_path

        self.output_ria_data_dir = None  # not known yet before output_ria is created
        self.analysis_dataset_id = None  # to update later

        self.list_sub_path_rel = 'code/processing_inclusion.csv'
        self.list_sub_path_abs = op.join(self.analysis_path, self.list_sub_path_rel)

        self.job_status_path_rel = 'code/job_status.csv'
        self.job_status_path_abs = op.join(self.analysis_path, self.job_status_path_rel)
        self.job_submit_path_abs = op.join(self.analysis_path, 'code/job_submit.csv')
        self._apply_config()

    def _apply_config(self):
        """Apply the configuration to the BABS project.

        The following attributes are set in this function:

          - processing_level
          - queue
          - container
          - input_datasets

        """
        # Sanity check: the path `project_root` exists:
        if not op.exists(self.project_root):
            raise Exception(
                f'`project_root` does not exist! Requested `project_root` was: {self.project_root}'
            )
        if not op.exists(self.analysis_path):
            raise FileNotFoundError(
                f'Missing: {self.analysis_path}\n'
                f'{self.project_root} is not a valid BABS project.\n\n'
                'Please run `babs init` first.'
            )
        if not op.exists(self.config_path):
            raise FileNotFoundError(
                f'Missing: {self.config_path}\n'
                f'{self.project_root} is not a valid BABS project.\n\n'
                'Please run `babs init` first.'
            )

        config_yaml = read_yaml(self.config_path)
        for section in CONFIG_SECTIONS:
            if section not in config_yaml:
                raise ValueError(f'Section {section} not found in {self.config_path}')

        self.processing_level = validate_processing_level(config_yaml['processing_level'])
        self.queue = validate_queue(config_yaml['queue'])
        self.container = config_yaml['container']

        # Check the output RIA:
        self.wtf_key_info(flag_output_ria_only=True)

        self.input_datasets = InputDatasets(self.processing_level, config_yaml['input_datasets'])
        self.input_datasets.update_abs_paths(Path(self.project_root) / 'analysis')

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
