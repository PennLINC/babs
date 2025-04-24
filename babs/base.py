"""This is the main module."""

import os
import os.path as op
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import datalad.api as dlapi

from babs.input_datasets import InputDatasets, OutputDatasets
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
        self._analysis_datalad_handle = None

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
            raise FileNotFoundError(
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

    def _get_merged_results_from_analysis_dir(self):
        """Get the results from the analysis directory."""
        output_datasets = OutputDatasets(self.input_datasets)
        return output_datasets.generate_inclusion_dataframe()

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
        proc_output_ria_data_dir.check_returncode()
        self.output_ria_data_dir = urlparse(
            proc_output_ria_data_dir.stdout.decode('utf-8')
        ).path.strip()

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
            self.analysis_dataset_id = (
                proc_analysis_dataset_id.stdout.decode('utf-8').strip().lstrip("'").rstrip("'")
            )

    @property
    def analysis_datalad_handle(self):
        """Cached property of `analysis_datalad_handle`."""
        if self._analysis_datalad_handle is None:
            self._analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
        return self._analysis_datalad_handle

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
            gitignore_path = op.join(self.analysis_path, '.gitignore')
            with open(gitignore_path, 'w') as f:
                for file in filter_files:
                    f.write(f'{file}\n')

            try:
                statuses = self.analysis_datalad_handle.save(path=path, message=message)
            finally:
                # Clean up the temporary .gitignore file
                if op.exists(gitignore_path):
                    os.remove(gitignore_path)
        else:
            statuses = self.analysis_datalad_handle.save(path=path, message=message)

        # ^^ number of dicts in list `statuses` = len(path)
        # check that all statuses returned are "okay":
        # below is from cubids
        saved_status = {status['status'] for status in statuses}
        if not saved_status.issubset({'ok', 'notneeded'}):
            # exists element in `saved_status` that is not "ok" or "notneeded"
            # ^^ "notneeded": nothing to save
            raise Exception('`datalad save` failed!')
