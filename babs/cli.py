"""This provides command-line interfaces of babs functions"""

import argparse
import warnings
from functools import partial
from pathlib import Path

import pandas as pd

from babs.utils import (
    RUNNING_PYTEST,
    validate_sub_ses_processing_inclusion,
)


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

    from babs import BABSBootstrap

    babs_proj = BABSBootstrap(project_root)
    try:
        babs_proj.babs_bootstrap(
            processing_level,
            queue,
            container_ds,
            container_name,
            container_config,
            list_sub_file,
        )
    except Exception as exc:
        print('\n`babs init` failed! Below is the error message:')
        if not keep_if_failed:
            print('\nCleaning up created BABS project...')
            babs_proj.clean_up()
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
    from babs import BABSCheckSetup

    babs_proj = BABSCheckSetup(project_root)
    babs_proj.babs_check_setup(job_test)


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
        help=(
            'Select specific jobs to submit by subject and optionally session. '
            'Use as `--select sub-XX [ses-YY]` and repeat the flag to submit multiple jobs, '
            'or provide multiple values per flag (argparse appends and supports nargs). '
            'Examples: `--select sub-01`, `--select sub-01 ses-01`, '
            '`--select sub-01 --select sub-02`, '
            '`--select sub-01 ses-01 --select sub-02 ses-02`.'
        ),
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

    from babs import BABSInteraction
    from babs.utils import parse_select_arg

    babs_proj = BABSInteraction(project_root)

    # Get a selection dataframe in order of preference
    if inclusion_file is not None:
        df_job_specified = pd.read_csv(inclusion_file)
        validate_sub_ses_processing_inclusion(df_job_specified, babs_proj.processing_level)
    elif select is not None:
        df_job_specified = parse_select_arg(select)
    else:
        df_job_specified = None

    babs_proj.babs_submit(count=count, submit_df=df_job_specified)


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
    from babs import BABSInteraction

    babs_proj = BABSInteraction(project_root)
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
    from babs import BABSMerge

    babs_proj = BABSMerge(project_root)
    babs_proj.babs_merge(chunk_size, trial_run)


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


def babs_sync_code_main(project_root: str, message: str):
    """This is the core function of babs sync-code.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
    message: str
        commit message for datalad save

    """

    from babs import BABSUpdate
    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:

    babs_proj = BABSUpdate(project_root)
    babs_proj.babs_sync_code(commit_message=message)


def _parse_update_input_data():
    """Create and configure the argument parser for the `babs update-input-data` command.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Update the input data in a BABS project.',
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
        '--dataset-name',
        help='Name of the dataset to update.',
        default='BIDS',
    )

    parser.add_argument(
        '--initial-inclusion-df',
        help='Path to a CSV file that lists the subjects (and sessions) to analyze.',
        type=str,
    )

    return parser


def babs_update_input_data_main(
    project_root: str, dataset_name: str, initial_inclusion_df: pd.DataFrame | None = None
):
    """This is the core function of babs update-input-data.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
    dataset_name: str
        name of the dataset to update
    initial_inclusion_df: pd.DataFrame | None
        initial inclusion dataframe to use
    """
    from babs import BABSUpdate

    babs_proj = BABSUpdate(project_root)
    babs_proj.babs_update_input_data(dataset_name, initial_inclusion_df)


COMMANDS = [
    ('init', _parse_init, babs_init_main),
    ('check-setup', _parse_check_setup, babs_check_setup_main),
    ('submit', _parse_submit, babs_submit_main),
    ('status', _parse_status, babs_status_main),
    ('merge', _parse_merge, babs_merge_main),
    ('sync-code', _parse_sync_code, babs_sync_code_main),
    ('update-input-data', _parse_update_input_data, babs_update_input_data_main),
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
