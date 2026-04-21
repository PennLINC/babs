"""This is the main module."""

import configparser
import os
import os.path as op
import subprocess
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

import datalad.api as dlapi
import pandas as pd

from babs.input_datasets import InputDatasets, OutputDatasets
from babs.scheduler import (
    request_all_job_status,
    run_squeue,
)
from babs.status import (
    read_job_status_csv,
    update_from_branches,
    update_from_scheduler,
    write_job_status_csv,
)
from babs.system import validate_queue
from babs.utils import (
    combine_inclusion_dataframes,
    get_latest_submitted_jobs_columns,
    get_results_branches,
    identify_running_jobs,
    read_yaml,
    results_status_columns,
    scheduler_status_columns,
    status_dtypes,
    validate_processing_level,
)

CONFIG_SECTIONS = ['processing_level', 'queue', 'input_datasets', 'container']
EMPTY_JOB_STATUS_DF = pd.DataFrame(
    columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'has_results']
)
EMPTY_JOB_SUBMIT_DF = pd.DataFrame(columns=['sub_id', 'ses_id', 'task_id', 'job_id', 'state'])


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
        self._shared_group_enabled_cache = None
        self._apply_config()

    def _apply_config(self) -> None:
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

        # Check for pipeline configuration (optional)
        self.pipeline = config_yaml.get('pipeline', None)
        if self.pipeline is not None:
            self._validate_pipeline_config()

        # Check the output RIA:
        self.wtf_key_info(flag_output_ria_only=True)

        self.input_datasets = InputDatasets(self.processing_level, config_yaml['input_datasets'])
        self.input_datasets.update_abs_paths(Path(self.project_root) / 'analysis')
        self.ensure_shared_group_git_safe_directories()

    def _validate_pipeline_config(self) -> None:
        """Validate the pipeline configuration if present.

        Raises
        ------
        ValueError
            If the pipeline configuration is invalid.
        """
        if not isinstance(self.pipeline, list):
            raise ValueError('Pipeline configuration must be a list of steps')

        if len(self.pipeline) == 0:
            raise ValueError('Pipeline configuration cannot be empty')

        print(f'\nValidating pipeline configuration with {len(self.pipeline)} steps...')

        for i, step in enumerate(self.pipeline):
            if not isinstance(step, dict):
                raise ValueError(f'Pipeline step {i} must be a dictionary')

            required_fields = ['container_name']
            for field in required_fields:
                if field not in step:
                    raise ValueError(f'Pipeline step {i} missing required field: {field}')

            step_name = step['container_name']
            print(f'  Step {i + 1}: {step_name}')

            # Validate step configuration
            step_config = step.get('config', {})
            if step_config:
                print(f'    Config: {len(step_config)} configuration items')

                # Check for step-specific cluster resources
                cluster_resources = step_config.get('cluster_resources', {})
                if cluster_resources:
                    print(f'    Cluster resources: {list(cluster_resources.keys())}')

                # Check for step-specific bids_app_args
                bids_app_args = step_config.get('bids_app_args', {})
                if bids_app_args:
                    print(f'    BIDS app args: {len(bids_app_args)} arguments')

                # Check for step-specific singularity_args
                singularity_args = step_config.get('singularity_args', [])
                if singularity_args:
                    print(f'    Singularity args: {len(singularity_args)} arguments')

            # Check for inter-step commands
            if 'inter_step_cmds' in step:
                print('    Inter-step commands: present')

        print('Pipeline configuration validation complete!')

    def _update_inclusion_dataframe(
        self, initial_inclusion_df: pd.DataFrame | None = None
    ) -> None:
        # If the user sent an initial inclusion dataframe, combine it with the one
        # generated by the input datasets
        print('\nDetermining the list of subjects (and sessions) to analyze...')
        sub_ses_inclusion_df = self.input_datasets.generate_inclusion_dataframe()

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

    def _get_merged_results_from_analysis_dir(self) -> pd.DataFrame:
        """Get the results from the analysis directory."""
        output_datasets = OutputDatasets(self.input_datasets)
        out_df = output_datasets.generate_inclusion_dataframe()
        return out_df

    def wtf_key_info(self, flag_output_ria_only=False) -> None:
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

        # If the URL points to the RIA store root (no .git there), resolve to the
        # actual dataset git dir via the alias symlink (e.g. output_ria/alias/data -> XX/xxx-uuid).
        if not op.exists(op.join(self.output_ria_data_dir, '.git')):
            alias_link = op.join(self.output_ria_path, 'alias', 'data')
            if op.exists(alias_link) and os.path.islink(alias_link):
                self.output_ria_data_dir = op.realpath(alias_link)

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

    @staticmethod
    def source_to_local_path(source: str) -> str | None:
        """Convert a local dataset source URL/path to a filesystem path."""
        if not source:
            return None
        if source.startswith('ria+file://'):
            local_path = source[len('ria+file://') :]
        elif source.startswith('file://'):
            local_path = source[len('file://') :]
        elif '://' not in source:
            local_path = source
        else:
            return None
        return local_path.split('#', 1)[0]

    def analysis_git_config_path(self) -> str | None:
        """Return absolute path to analysis git config file."""
        git_path = op.join(self.analysis_path, '.git')
        # Standard repo layout: `.git/` is a directory containing `config`.
        if op.isdir(git_path):
            config_path = op.join(git_path, 'config')
            return config_path if op.exists(config_path) else None

        # Alternate layout (e.g., worktree/submodule): `.git` is a file with
        # a pointer like `gitdir: /actual/path/to/gitdir`.
        if op.isfile(git_path):
            with open(git_path) as f:
                first_line = f.readline().strip()
            if first_line.startswith('gitdir:'):
                git_dir = first_line.split(':', 1)[1].strip()
                # The gitdir pointer can be relative to `analysis_path`.
                if not op.isabs(git_dir):
                    git_dir = op.normpath(op.join(self.analysis_path, git_dir))
                config_path = op.join(git_dir, 'config')
                return config_path if op.exists(config_path) else None
        # No recognizable git metadata/config path found.
        return None

    def is_shared_group_project(self) -> bool:
        """Return whether this project is configured for shared-group permissions."""
        # During `babs init`, shared mode is known from the CLI flag directly.
        if getattr(self, 'shared_group', None) is not None:
            return True
        # Reuse the computed value to avoid repeatedly reading git config.
        if self._shared_group_enabled_cache is not None:
            return self._shared_group_enabled_cache

        # For existing projects, infer shared mode from git's core setting.
        config_path = self.analysis_git_config_path()
        if config_path is None:
            self._shared_group_enabled_cache = False
            return False

        parser = configparser.ConfigParser()
        parser.read(config_path)
        # Git may encode shared mode as text ('group') or truthy values.
        shared_mode = parser.get('core', 'sharedrepository', fallback='').strip().lower()
        self._shared_group_enabled_cache = shared_mode in {'group', '1', 'true', 'yes'}
        return self._shared_group_enabled_cache

    def ensure_shared_group_git_safe_directories(self) -> None:
        """Register project repositories in git safe.directory for shared mode."""
        if not self.is_shared_group_project():
            return

        safe_dirs = set()
        if op.exists(self.analysis_path):
            safe_dirs.add(op.realpath(self.analysis_path))

        for ria_root in (self.input_ria_path, self.output_ria_path):
            ria_root_path = Path(ria_root)
            if not ria_root_path.exists():
                continue
            for repo_dir in ria_root_path.glob('*/*'):
                if repo_dir.is_dir():
                    safe_dirs.add(str(repo_dir.resolve()))

        alias_data = op.join(self.output_ria_path, 'alias', 'data')
        if op.exists(alias_data):
            safe_dirs.add(op.realpath(alias_data))

        if hasattr(self, 'input_datasets'):
            for in_ds in self.input_datasets:
                local_path = self.source_to_local_path(getattr(in_ds, 'origin_url', ''))
                if local_path is not None:
                    safe_dirs.add(op.realpath(local_path))

        proc_existing = subprocess.run(
            ['git', 'config', '--global', '--get-all', 'safe.directory'],
            capture_output=True,
            text=True,
        )
        existing = (
            {line.strip() for line in proc_existing.stdout.splitlines() if line.strip()}
            if proc_existing.returncode == 0
            else set()
        )

        for repo_path in sorted(safe_dirs):
            if not op.exists(repo_path) or repo_path in existing:
                continue
            subprocess.run(
                ['git', 'config', '--global', '--add', 'safe.directory', repo_path],
                capture_output=True,
                text=True,
            )
            existing.add(repo_path)

    def ensure_shared_group_runtime_ready(self) -> None:
        """Apply git-safe-directory safeguards for shared projects."""
        self.ensure_shared_group_git_safe_directories()

    @property
    def analysis_datalad_handle(self) -> dlapi.Dataset:
        """Cached property of `analysis_datalad_handle`."""
        if self._analysis_datalad_handle is None:
            self._analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
        return self._analysis_datalad_handle

    @property
    def inclusion_dataframe(self) -> pd.DataFrame:
        """Cached property of `inclusion_dataframe`."""
        return pd.read_csv(self.list_sub_path_abs)

    def datalad_save(
        self, path: str, message: str | None = None, filter_files: list[str] | None = None
    ) -> None:
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

    def _get_results_branches(self) -> list[str]:
        """Get the results branch names from the output RIA in a list."""
        return get_results_branches(self.output_ria_data_dir)

    def _update_results_status(self) -> dict:
        """Update job statuses from external sources and write to CSV.

        Returns
        -------
        dict[tuple, JobStatus]
            Updated statuses keyed by (sub_id,) or (sub_id, ses_id).
        """
        # Read current state from CSV
        if op.exists(self.job_status_path_abs):
            statuses = read_job_status_csv(self.job_status_path_abs)
        else:
            statuses = {}

        # Update from results branches in output RIA
        branches = self._get_results_branches()
        statuses = update_from_branches(statuses, branches)

        # Update from merged zip files in analysis dir
        merged_zip_df = self._get_merged_results_from_analysis_dir()
        if not merged_zip_df.empty:
            for _, row in merged_zip_df.iterrows():
                ses_id = row.get('ses_id') if 'ses_id' in merged_zip_df.columns else None
                key = (row['sub_id'], ses_id) if ses_id else (row['sub_id'],)
                if key in statuses:
                    statuses[key] = replace(statuses[key], has_results=True)

        # Update from scheduler (squeue)
        job_ids = sorted(
            {
                job.job_id
                for job in statuses.values()
                if job.submitted and not job.has_results and job.job_id is not None
            }
        )
        raw_squeue_parts = []
        for jid in job_ids:
            raw_squeue_parts.append(run_squeue(self.queue, jid))
        raw_squeue = ''.join(raw_squeue_parts)
        statuses = update_from_scheduler(statuses, raw_squeue)

        # Write updated statuses
        write_job_status_csv(self.job_status_path_abs, statuses)
        return statuses

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
        expected_columns = get_latest_submitted_jobs_columns(self.processing_level)
        if not op.exists(self.job_submit_path_abs):
            return pd.DataFrame(columns=expected_columns)

        try:
            df = pd.read_csv(self.job_submit_path_abs)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=expected_columns)

        # job_submit.csv is written once before submit (without job_id) and then
        # rewritten after submit (with job_id). Tolerate the interim schema so
        # follow-up commands do not crash if submit was interrupted.
        for column_name in expected_columns:
            if column_name not in df.columns:
                df[column_name] = pd.NA
            df[column_name] = df[column_name].astype(status_dtypes[column_name])

        return df[expected_columns]

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

        def _empty_running():
            cols = scheduler_status_columns + ['sub_id']
            if self.processing_level == 'session':
                cols = cols + ['ses_id']
            return pd.DataFrame(columns=cols)

        job_status_df = self.get_job_status_df()
        last_submitted_jobs_df = self.get_latest_submitted_jobs_df()

        # Rows that are submitted but don't have results yet (candidates for "running")
        if not job_status_df.empty:
            sub = job_status_df['submitted'].fillna(False)
            no_res = ~job_status_df['has_results'].fillna(False)
            job_status_df = job_status_df.loc[sub & no_res].copy()

        # Use status rows (submitted, no results) or last submit file for job_id -> sub/ses
        mapping_df = job_status_df if not job_status_df.empty else last_submitted_jobs_df.copy()
        if mapping_df.empty:
            return _empty_running()

        # Keep only columns needed to join scheduler output with subject/session
        mapping_cols = ['job_id', 'task_id', 'sub_id']
        if 'ses_id' in mapping_df:
            mapping_cols.append('ses_id')
        mapping_df = mapping_df[mapping_cols].copy()
        # Drop rows with missing or invalid job/task ids so we only query real jobs
        mapping_df = mapping_df[
            mapping_df['job_id'].notna()
            & mapping_df['task_id'].notna()
            & (mapping_df['job_id'] > 0)
            & (mapping_df['task_id'] > 0)
        ]
        if mapping_df.empty:
            return _empty_running()

        # Ask scheduler for each distinct job_id, keep only non-empty responses
        job_ids = sorted({int(j) for j in mapping_df['job_id'].unique()})
        running_dfs = [request_all_job_status(self.queue, j) for j in job_ids]
        running_dfs = [d for d in running_dfs if not d.empty]
        if not running_dfs:
            return _empty_running()

        # Attach sub_id (and ses_id) to scheduler rows and return
        return identify_running_jobs(mapping_df, pd.concat(running_dfs, ignore_index=True))

    def get_job_status_df(self):
        """
        Get the results status dataframe.
        """
        if not op.exists(self.job_status_path_abs):
            return EMPTY_JOB_STATUS_DF
        df = pd.read_csv(self.job_status_path_abs)
        for column_name in results_status_columns:
            df[column_name] = df[column_name].astype(status_dtypes[column_name])

        df['has_results'] = df['has_results'].astype('boolean').fillna(False)

        return df
