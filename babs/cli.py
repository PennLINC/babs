"""This provides command-line interfaces of babs functions"""

import argparse
import os
import warnings
from functools import partial
from pathlib import Path

import yaml

from babs.babs import BABS
from babs.input_datasets import InputDatasets
from babs.scheduler import create_job_status_csv
from babs.system import System
from babs.utils import RUNNING_PYTEST, get_datalad_version, read_yaml, validate_processing_level


def _path_exists(path, parser):
    """Ensure a given path exists."""
    if path is None or not Path(path).exists():
        raise parser.error(f'The path <{path}> does not exist.')

    return Path(path).absolute()


def _path_does_not_exist(path, parser):
    """Ensure a given path does not exist."""
    if path is None:
        raise parser.error('The path is required.')
    elif Path(path).exists():
        raise parser.error(f'The path <{path}> already exists.')

    return Path(path).absolute()


def _parse_init():
    """Create and configure the argument parser for the `babs init` command.

    It includes a description and formatter class, and adds arguments for the command.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Initialize a BABS project and bootstrap scripts that will be used later.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    PathDoesNotExist = partial(_path_does_not_exist, parser=parser)

    parser.add_argument(
        'project_root',
        type=PathDoesNotExist,
        metavar='PATH',
        help=(
            'Absolute path to the directory where the BABS project will be located. '
            'This folder will be automatically created.'
        ),
    )
    parser.add_argument(
        '--list_sub_file',
        '--list-sub-file',  # optional flag
        type=str,
        help='Path to the CSV file that lists the subject (and sessions) to analyze; '
        ' If there is no such file, please not to specify this flag.'
        " Single-session data: column of 'sub_id';"
        " Multi-session data: columns of 'sub_id' and 'ses_id'.",
    )
    parser.add_argument(
        '--container_ds',
        '--container-ds',
        help='Path to the container DataLad dataset',
        required=True,
    )
    parser.add_argument(
        '--container_name',
        '--container-name',
        help='The name of the BIDS App container, i.e.,'
        ' the ``<image NAME>`` used when running ``datalad containers-add <image NAME>``.'
        " Importantly, this should include the BIDS App's name"
        ' to make sure the bootstrap scripts are set up correctly;'
        ' Also, the version number should be added, too.'
        ' ``babs init`` is not case sensitive to this ``--container_name``.'
        ' Example: ``toybidsapp-0-0-7`` for toy BIDS App version 0.0.7.',
        # ^^ the BIDS App's name is used to determine: e.g., whether needs/details in $filterfile
        required=True,
    )
    parser.add_argument(
        '--container_config',
        '--container-config',
        help='Path to a YAML file that contains the configurations'
        ' of how to run the BIDS App container',
    )
    parser.add_argument(
        '--processing_level',
        '--processing-level',
        choices=[
            'subject',
            'session',
        ],
        help='Whether jobs should be run on a per-subject or per-session (within subject) basis.',
        required=True,
    )
    parser.add_argument(
        '--queue',
        choices=['slurm'],
        help='The name of the job scheduling queue that you will use.',
        required=True,
    )
    parser.add_argument(
        '--keep_if_failed',
        '--keep-if-failed',
        action='store_true',
        # ^^ if `--keep-if-failed` is specified, args.keep_if_failed = True; otherwise, False
        help='If ``babs init`` fails with error, whether to keep the created BABS project.'
        " By default, you don't need to turn this option on."
        ' However, when ``babs init`` fails and you hope to use ``babs check-setup``'
        ' to diagnose, please turn it on to rerun ``babs init``,'
        ' then run ``babs check-setup``.'
        " Please refer to section below 'What if ``babs init`` fails?' for details.",
        #      ^^ in `babs init.rst`, pointed to below section for more
    )

    return parser


def _enter_init(argv=None):
    """Entry point for `babs-init` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs init` instead.
    """
    if not RUNNING_PYTEST:
        warnings.warn(
            'babs-init is deprecated and will be removed in the future. Please use babs init.',
            DeprecationWarning,
            stacklevel=2,
        )
    options = _parse_init().parse_args(argv)
    args = vars(options).copy()
    babs_init_main(**args)


def babs_init_main(
    project_root: Path,
    list_sub_file: str,
    container_ds: str,
    container_name: str,
    container_config: str,
    processing_level: str,
    queue: str,
    keep_if_failed: bool,
):
    """This is the core function of babs init.

    Parameters
    ----------
    project_root : pathlib.Path
        The path to the directory where the BABS project will be located.
        This folder will be automatically created.
    list_sub_file: str or None
        Path to the CSV file that lists the subject (and sessions) to analyze;
        or `None` if CLI's flag isn't specified
        subject data: column of 'sub_id';
        session data: columns of 'sub_id' and 'ses_id'
    container_ds: str
        path to the container datalad dataset
    container_name: str
        name of the container, best to include version number.
        e.g., 'fmriprep-0-0-0'
    container_config: str
        Path to a YAML file that contains the configurations
        of how to run the BIDS App container
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    queue: str
        sge or slurm
    keep_if_failed: bool
        If `babs init` failed with error, whether to keep the created BABS project.
    """
    # =================================================================
    # Sanity checks:
    # =================================================================
    # check if it exists: if so, raise error
    if project_root.exists():
        raise ValueError(
            f"The project folder '{project_root}' already exists! "
            "`babs init` won't proceed to overwrite this folder."
        )

    # check if parent directory exists:
    if not project_root.parent.exists():
        raise ValueError(
            f"The parent folder '{project_root.parent}' does not exist! `babs init` won't proceed."
        )

    # check if parent directory is writable:
    if not os.access(project_root.parent, os.W_OK):
        raise ValueError(
            f"The parent folder '{project_root.parent}' is not writable! "
            "`babs init` won't proceed."
        )

    # print datalad version:
    #   if no datalad is installed, will raise error
    print('DataLad version: ' + get_datalad_version())

    # validate `processing_level`:
    processing_level = validate_processing_level(processing_level)

    # Read the config yaml to get the datasets:
    with open(container_config) as f:
        babs_config = yaml.safe_load(f)
    datasets = babs_config.get('input_datasets')
    if not datasets:
        raise ValueError('No input datasets found in the container config file.')
    input_ds = InputDatasets(processing_level, datasets)
    input_ds.set_inclusion_dataframe(list_sub_file, processing_level)

    # Note: not to perform sanity check on the input dataset re: if it exists
    #   as: 1) robust way is to clone it, which will take longer time;
    #           so better tob just leave to the real cloning when `babs init`;
    #       2) otherwise, if using "if `.datalad/config` exists" to check, then need to check
    #           if input dataset is local or not, and it's very tricky to check that...
    #       3) otherwise, if using "dlapi.status(dataset=the_input_ds)": will take long time
    #           for big dataset; in addition, also need to check if it's local or not...
    # currently solution: add notes in Debugging in `babs init` docs: `babs init.rst`

    # Create an instance of babs class:
    babs_proj = BABS(project_root, processing_level, queue)

    # Validate system's type name `queue`:
    system = System(queue)

    # print out key information for visual check:
    print('')
    print('project_root of this BABS project: ' + babs_proj.project_root)
    print('processing level of this BABS project: ' + babs_proj.processing_level)
    print('job scheduling system of this BABS project: ' + babs_proj.queue)
    print('')

    try:
        babs_proj.babs_bootstrap(
            input_ds,
            container_ds,
            container_name,
            container_config,
            system,
        )
    except Exception as exc:
        print('\n`babs init` failed! Below is the error message:')
        if not keep_if_failed:
            print('\nCleaning up created BABS project...')
            babs_proj.clean_up(input_ds)
        else:
            print('\n`--keep-if-failed` is requested, so not to clean up created BABS project.')
        raise exc


def _parse_check_setup():
    """Create and configure the argument parser for the `babs check-setup` command.

    It includes a description and formatter class, and adds arguments for the command.

    Returns
    -------
    argparse.ArgumentParser
    """

    parser = argparse.ArgumentParser(
        description='Validate setup created by ``babs init``.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    PathExists = partial(_path_exists, parser=parser)
    parser.add_argument(
        'project_root',
        metavar='PATH',
        help=(
            'Absolute path to the root of BABS project. '
            "For example, '/path/to/my_BABS_project/' "
            '(default is current working directory).'
        ),
        nargs='?',
        default=Path.cwd(),
        type=PathExists,
    )
    parser.add_argument(
        '--job_test',
        '--job-test',
        action='store_true',
        # ^^ if `--job-test` is specified, args.job_test = True; otherwise, False
        help='Whether to submit and run a test job. Will take longer time if doing so.',
    )

    return parser


def _enter_check_setup(argv=None):
    """Entry point for `babs-check-setup` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs check-setup` instead.
    """
    if not RUNNING_PYTEST:
        warnings.warn(
            'babs-check-setup is deprecated and will be removed in the future. '
            'Please use babs check-setup.',
            DeprecationWarning,
            stacklevel=2,
        )
    options = _parse_check_setup().parse_args(argv)
    babs_check_setup_main(**vars(options))


def babs_check_setup_main(
    project_root: str,
    job_test: bool,
):
    """
    This is the core function of babs check-setup,
    which validates the setup by `babs init`.

    project_root: str
        Absolute path to the root of BABS project.
        For example, '/path/to/my_BABS_project/'.
    job_test: bool
        Whether to submit and run a test job.
    """
    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, input_ds = get_existing_babs_proj(project_root)

    # Call method `babs_check_setup()`:
    babs_proj.babs_check_setup(input_ds, job_test)


def _parse_submit():
    """Create and configure the argument parser for the `babs submit` command.

    It includes a description and formatter class, and adds arguments for the command.

    Can choose one of these flags:
    --count <number of jobs to submit>
    --select sub-id ses-id   # can repeat
    --inclusion-file <path to inclusion file>

    If none of these flags are specified, will only submit one job array task.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Submit jobs to cluster compute nodes.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    PathExists = partial(_path_exists, parser=parser)
    parser.add_argument(
        'project_root',
        metavar='PATH',
        help=(
            'Absolute path to the root of BABS project. '
            "For example, '/path/to/my_BABS_project/' "
            '(default is current working directory).'
        ),
        nargs='?',
        default=Path.cwd(),
        type=PathExists,
    )

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        '--count',
        type=int,
        help='Submit this many jobs instead of submitting all remaining jobs.',
    )

    group.add_argument(
        '--select',
        action='append',  # append each `--job` as a list;
        nargs='+',
        help='The subject ID (and session ID) whose job to be submitted.'
        ' Can repeat to submit more than one job.'
        ' Format would be `--job sub-xx` for single-session dataset,'
        ' and `--job sub-xx ses-yy` for multiple-session dataset.',
    )

    group.add_argument(
        '--inclusion-file',
        help='Path to a CSV file that lists the subjects (and sessions) to analyze.'
        ' The file should columns: `sub_id` and, if session-level processing, `ses_id`.'
        ' If this flag is specified, it will override the `--select` flag.',
        type=PathExists,
    )

    return parser


def _enter_submit(argv=None):
    """Entry point for `babs-submit` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs submit` instead.
    """
    if not RUNNING_PYTEST:
        warnings.warn(
            'babs-submit is deprecated and will be removed in the future. Please use babs submit.',
            DeprecationWarning,
            stacklevel=2,
        )
    options = _parse_submit().parse_args(argv)
    babs_submit_main(**vars(options))


def babs_submit_main(
    project_root: str,
    count: int | None,
    select: list | None,
    inclusion_file: Path | None,
):
    """This is the core function of ``babs submit``.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
    count: int or None
        number of jobs to be submitted. If not set, all remaining jobs will be submitted.
    select: list
        list of subject IDs and session IDs to be submitted.
    inclusion_file: Path
        path to a CSV file that lists the subjects (and sessions) to analyze.
    """
    import pandas as pd

    from babs.utils import parse_select_arg

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Check if this csv file has been created, if not, create it:
    create_job_status_csv(babs_proj)

    # Get a selection dataframe in order of preference
    if inclusion_file is not None:
        df_job_specified = pd.read_csv(inclusion_file)
    elif select is not None:
        df_job_specified = parse_select_arg(select)
    else:
        df_job_specified = None

    # Call method `babs_submit()`:
    babs_proj.babs_submit(count=count, df_job_specified=df_job_specified)


def _parse_status():
    """Create and configure the argument parser for the `babs status` command.

    It includes a description and formatter class, and adds arguments for the command.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Check job status in a BABS project.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    PathExists = partial(_path_exists, parser=parser)
    parser.add_argument(
        'project_root',
        metavar='PATH',
        help=(
            'Absolute path to the root of BABS project. '
            "For example, '/path/to/my_BABS_project/' "
            '(default is current working directory).'
        ),
        nargs='?',
        default=Path.cwd(),
        type=PathExists,
    )

    return parser


def _enter_status(argv=None):
    """Entry point for `babs-status` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs status` instead.
    """
    if not RUNNING_PYTEST:
        warnings.warn(
            'babs-status is deprecated and will be removed in the future. Please use babs status.',
            DeprecationWarning,
            stacklevel=2,
        )
    options = _parse_status().parse_args(argv)
    babs_status_main(**vars(options))


def babs_status_main(
    project_root: str,
):
    """
    This is the core function of `babs status`.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
    """
    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Check if this csv file has been created, if not, create it:
    create_job_status_csv(babs_proj)

    babs_proj.babs_status()


def _parse_merge():
    """Create and configure the argument parser for the `babs merge` command.

    It includes a description and formatter class, and adds arguments for the command.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Merge results and provenance from all successfully finished jobs.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    user_args = parser.add_argument_group('User arguments')
    PathExists = partial(_path_exists, parser=parser)
    user_args.add_argument(
        'project_root',
        metavar='PATH',
        help=(
            'Absolute path to the root of BABS project. '
            "For example, '/path/to/my_BABS_project/' "
            '(default is current working directory).'
        ),
        nargs='?',
        default=Path.cwd(),
        type=PathExists,
    )
    dev_args = parser.add_argument_group(
        'Developer arguments', 'Parameters for developers. Users should not use these.'
    )
    dev_args.add_argument(
        '--chunk-size',
        '--chunk_size',
        type=int,
        default=2000,
        help='Number of branches in a chunk when merging at a time.'
        ' We recommend using default value.',
    )
    # Matt: 5000 is not good, 2000 is appropriate.
    #   Smaller chunk is, more merging commits which is fine.
    dev_args.add_argument(
        '--trial-run',
        '--trial_run',
        action='store_true',
        # ^^ if `--trial-run` is specified, args.trial_run = True; otherwise, False
        help="Whether to run as a trial run which won't push the merge back to output RIA."
        ' This option should only be used by developers for testing purpose.'
        " Users: please don't turn this on!",
    )

    return parser


def _enter_merge(argv=None):
    """Entry point for `babs-merge` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs merge` instead.
    """
    if not RUNNING_PYTEST:
        warnings.warn(
            'babs-merge is deprecated and will be removed in the future. Please use babs merge.',
            DeprecationWarning,
            stacklevel=2,
        )
    options = _parse_merge().parse_args(argv)
    babs_merge_main(**vars(options))


def babs_merge_main(
    project_root,
    chunk_size,
    trial_run,
):
    """
    To merge results and provenance from all successfully finished jobs.

    Parameters
    ----------
    project_root: str
        Absolute path to the root of BABS project.
    chunk_size: int
        Number of branches in a chunk when merging at a time.
    trial_run: bool
        Whether to run as a trial run which won't push the merging actions back to output RIA.
        This option should only be used by developers for testing purpose.
    """
    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Call method `babs_merge()`:
    babs_proj.babs_merge(chunk_size, trial_run)


def _parse_unzip():
    """Create and configure the argument parser for the `babs unzip` command.

    It includes a description and formatter class, and adds arguments for the command.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Unzip results zip files and extracts desired files',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    PathExists = partial(_path_exists, parser=parser)
    parser.add_argument(
        'project_root',
        metavar='PATH',
        help=(
            'Absolute path to the root of BABS project. '
            "For example, '/path/to/my_BABS_project/' "
            '(default is current working directory).'
        ),
        nargs='?',
        default=Path.cwd(),
        type=PathExists,
    )
    parser.add_argument(
        '--container_config',
        '--container-config',
        help='Path to a YAML file of the BIDS App container that contains information of'
        ' what files to unzip etc.',
    )

    return parser


def _enter_unzip(argv=None):
    """Entry point for `babs-unzip` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs unzip` instead.
    """
    if not RUNNING_PYTEST:
        warnings.warn(
            'babs-unzip is deprecated and will be removed in the future. Please use babs unzip.',
            DeprecationWarning,
            stacklevel=2,
        )
    options = _parse_unzip().parse_args(argv)
    babs_unzip_main(**vars(options))


def babs_unzip_main(
    project_root: str,
    container_config: str,
):
    """
    This is the core function of babs-unzip, which unzip results zip files
    and extracts desired files.

    project_root: str
        Absolute path to the root of BABS project.
        For example, '/path/to/my_BABS_project/'.
    container_config: str
        path to container's configuration YAML file.
        These two sections will be used:
        1. 'unzip_desired_filenames' - must be included
        2. 'rename_conflict_files' - optional
    """
    # container config:
    config = read_yaml(container_config)
    # ^^ not to use filelock here - otherwise will create `*.lock` file in user's folder

    # Sanity checks:
    if 'unzip_desired_filenames' not in config:
        raise Exception(
            "Section 'unzip_desired_filenames' is not included"
            ' in `--container_config`. This section is required.'
            " Path to this YAML file: '" + container_config + "'."
        )

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Call method `babs_unzip()`:
    babs_proj.babs_unzip(config)


def get_existing_babs_proj(project_root):
    """
    This is to get `babs_proj` (class `BABS`) and `input_ds` (class `InputDatasets`)
    based on existing yaml file `babs_proj_config.yaml`.
    This should be used by `babs_submit()` and `babs_status`.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
        TODO: accept relative path too, like datalad's `-d`

    Returns
    -------
    babs_proj: class `BABS`
        information about a BABS project
    input_ds: class `InputDatasets`
        information about input dataset(s)
    """

    # Sanity check: the path `project_root` exists:
    if not os.path.exists(project_root):
        raise Exception(
            f'`project_root` does not exist! Requested `project_root` was: {project_root}'
        )

    # Read configurations of BABS project from saved yaml file:
    babs_proj_config_yaml = os.path.join(project_root, 'analysis/code/babs_proj_config.yaml')
    if not os.path.exists(babs_proj_config_yaml):
        raise Exception(
            '`babs init` was not successful;'
            " there is no 'analysis/code/babs_proj_config.yaml' file!"
            ' Please rerun `babs init` to finish the setup.'
        )

    babs_proj_config = read_yaml(babs_proj_config_yaml, use_filelock=True)

    # make sure the YAML file has necessary sections:
    list_sections = ['processing_level', 'queue', 'input_datasets', 'container']
    for i in range(0, len(list_sections)):
        the_section = list_sections[i]
        if the_section not in babs_proj_config:
            raise Exception(
                f"There is no section '{the_section}' in 'babs_proj_config.yaml' file "
                "in 'analysis/code' folder! Please rerun `babs init` to finish the setup."
            )

    processing_level = babs_proj_config['processing_level']
    queue = babs_proj_config['queue']

    # Get the class `BABS`:
    babs_proj = BABS(project_root, processing_level, queue)

    # update key information including `output_ria_data_dir`:
    babs_proj.wtf_key_info(flag_output_ria_only=True)

    # Get information for input dataset:
    input_ds_yaml = babs_proj_config['input_datasets']
    # sanity check:
    if len(input_ds_yaml) == 0:  # there was no input ds:
        raise Exception(
            "Section 'input_datasets' in `analysis/code/babs_proj_config.yaml`"
            'does not include any input dataset!'
            ' Something was wrong during `babs init`...'
        )

    # Get the class `InputDatasets`:
    input_ds = InputDatasets(babs_proj_config['processing_level'], input_ds_yaml)
    input_ds.update_abs_paths(project_root / 'analysis')
    return babs_proj, input_ds


def _parse_sync_code():
    """Create and configure the argument parser for the `babs sync-code` command.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Save and push code changes to input dataset.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'project_root',
        nargs='?',
        default=Path.cwd(),
        help=(
            'Absolute path to the root of BABS project. '
            "For example, '/path/to/my_BABS_project/' "
            '(default is current working directory).'
        ),
    )
    parser.add_argument(
        '-m',
        '--message',
        help='Commit message for datalad save',
        default='[babs] sync code changes',
    )

    return parser


def babs_sync_code_main(project_root: str, commit_message: str):
    """This is the core function of babs sync-code.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
    commit_message: str
        commit message for datalad save
    """
    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Change to `analysis/code` directory
    analysis_code_dir = os.path.join(project_root, 'analysis/code')
    if not os.path.exists(analysis_code_dir):
        raise FileNotFoundError(
            f'`analysis/code` directory does not exist at: {analysis_code_dir}'
        )

    # Run datalad commands with filter to exclude specific files
    # job_status and job_submit are modified every time `babs status` or `babs submit` is run
    # no need to save and push these files
    babs_proj.datalad_save(
        analysis_code_dir,
        commit_message,
        filter_files=[
            'job_status.csv',
            'job_status.csv.lock',
            'job_submit.csv',
            'job_submit.csv.lock',
        ],
    )
    babs_proj.datalad_push(analysis_code_dir, '--to input')


def _parse_make_input_dataset():
    """Create and configure the argument parser for the `babs create-input-dataset` command.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Create a BIDS or zipped BIDS derivatives dataset for testing.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'output_path',
        nargs=1,
        help=(
            "Absolute path to the output directory. For example, '/path/to/fake_bids_dataset/' "
        ),
    )
    parser.add_argument(
        '--multiple-sessions',
        help='Create a BIDS dataset with multiple sessions.',
        action='store_true',
    )
    parser.add_argument(
        '--zip-level',
        help='The level at which to zip the dataset.',
        choices=['subject', 'session', 'none'],
        default='subject',
    )

    return parser


COMMANDS = [
    ('init', _parse_init, babs_init_main),
    ('check-setup', _parse_check_setup, babs_check_setup_main),
    ('submit', _parse_submit, babs_submit_main),
    ('status', _parse_status, babs_status_main),
    ('merge', _parse_merge, babs_merge_main),
    ('unzip', _parse_unzip, babs_unzip_main),
    ('sync-code', _parse_sync_code, babs_sync_code_main),
]


def _get_parser():
    """Create the general `babs` parser object.

    This function sets up the argument parser for the `babs` command-line interface.
    It includes a version argument and dynamically adds subparsers for each command
    defined in the COMMANDS list.

    Returns
    -------
    argparse.ArgumentParser
        The argument parser for the "babs" CLI.
    """
    from babs import __version__

    parser = argparse.ArgumentParser(prog='babs', allow_abbrev=False)
    parser.add_argument('-v', '--version', action='version', version=f'babs v{__version__}')
    subparsers = parser.add_subparsers(help='BABS commands')

    for command, parser_func, run_func in COMMANDS:
        subparser = parser_func()
        subparser.set_defaults(func=run_func)
        subparsers.add_parser(
            command,
            parents=[subparser],
            help=subparser.description,
            add_help=False,
            allow_abbrev=False,
        )

    return parser


def _main(argv=None):
    """Entry point for `babs` CLI.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to `sys.argv`.

    Returns
    -------
    None
    """
    options = _get_parser().parse_args(argv)
    args = vars(options).copy()
    args.pop('func')
    options.func(**args)
