"""This provides command-line interfaces of babs functions"""

import argparse
import os
import traceback
import warnings
from functools import partial
from pathlib import Path

import pandas as pd
from filelock import FileLock, Timeout

from babs.babs import BABS
from babs.dataset import InputDatasets
from babs.system import System
from babs.utils import (
    ToDict,
    _path_does_not_exist,
    _path_exists,
    create_job_status_csv,
    get_datalad_version,
    read_job_status_csv,
    read_yaml,
    validate_processing_level,
)


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
        '--datasets',
        action=ToDict,
        metavar='NAME=PATH',
        type=str,
        nargs='+',
        help=(
            'Input BIDS datasets. '
            'These must be provided as named folders '
            '(e.g., `--datasets smriprep=/path/to/smriprep`).'
        ),
        required=True,
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
    datasets: dict,
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
    datasets : dictionary
        Keys are the names of the input BIDS datasets, and values are the paths to the input BIDS
        datasets.
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

    # input dataset:
    input_ds = InputDatasets(datasets)
    input_ds.get_initial_inclu_df(list_sub_file, processing_level)

    # Note: not to perform sanity check on the input dataset re: if it exists
    #   as: 1) robust way is to clone it, which will take longer time;
    #           so better to just leave to the real cloning when `babs init`;
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

    # Call method `babs_bootstrap()`:
    #   if success, good!
    #   if failed, and if not `keep_if_failed`: delete the BABS project `babs init` creates!
    try:
        babs_proj.babs_bootstrap(
            input_ds,
            container_ds,
            container_name,
            container_config,
            system,
        )
    except Exception:
        print('\n`babs init` failed! Below is the error message:')
        traceback.print_exc()  # print out the traceback error messages
        if not keep_if_failed:
            # clean up:
            print('\nCleaning up created BABS project...')
            babs_proj.clean_up(input_ds)
            print(
                'Please check the error messages above!'
                ' Then fix the problem, and rerun `babs init`.'
            )
        else:
            print('\n`--keep-if-failed` is requested, so not to clean up created BABS project.')
            print(
                'Please check the error messages above!'
                ' Then fix the problem, delete this failed BABS project,'
                ' and rerun `babs init`.'
            )


def _parse_check_setup():
    """Create and configure the argument parser for the `babs check-setup` command.

    It includes a description and formatter class, and adds arguments for the command.

    Returns
    -------
    argparse.ArgumentParser
    """

    parser = argparse.ArgumentParser(
        description='Validate setups created by ``babs init``.',
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
    which validates the setups by `babs init`.

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
    --count <number of jobs to submit>  # should be larger than # of `--job`
    --all   # if specified, will submit all remaining jobs that haven't been submitted.
    --job sub-id ses-id   # can repeat

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

    # --count, --job: can only request one of them and none of them are required.
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        '--count',
        type=int,
        help='Number of jobs to submit. It should be a positive integer.',
    )
    group.add_argument(
        '--all',
        action='store_true',
        dest='submit_all',
        # ^^ if `--all` is specified, args.all = True; otherwise, False
        help="Request to run all jobs that haven't been submitted.",
    )
    group.add_argument(
        '--job',
        action='append',  # append each `--job` as a list;
        nargs='+',
        help='The subject ID (and session ID) whose job to be submitted.'
        ' Can repeat to submit more than one job.'
        ' Format would be `--job sub-xx` for single-session dataset,'
        ' and `--job sub-xx ses-yy` for multiple-session dataset.',
    )

    return parser


def _enter_submit(argv=None):
    """Entry point for `babs-submit` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs submit` instead.
    """
    warnings.warn(
        'babs-submit is deprecated and will be removed in the future. Please use babs submit.',
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_submit().parse_args(argv)
    babs_submit_main(**vars(options))


def babs_submit_main(
    project_root: str,
    count: int,
    submit_all: bool,
    job: list,
):
    """This is the core function of ``babs submit``.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
    submit_all : bool
        whether to submit all remaining jobs
    count: int or None
        number of jobs to be submitted
        default: None (did not specify in cli)
            if `--job` is not requested, it will be changed to `1` before going
            into `babs_submit()`
        any negative int will be treated as submitting all jobs that haven't been submitted.
    job: nested list or None
        For each sub-list, the length should be 1 (for subject) or 2 (for session)
    """
    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Check if this csv file has been created, if not, create it:
    create_job_status_csv(babs_proj)
    # ^^ this is required by the sanity check `check_df_job_specific`

    # Actions on `count`:
    if submit_all:  # if True:
        count = -1  # so that to submit all remaining jobs

    if count is None:
        count = 1  # if not to specify `--count`, change to 1

    # sanity check:
    if count == 0:
        raise Exception(
            '`--count 0` is not valid! Please specify a positive integer. '
            'To submit all jobs, please do not specify `--count`.'
        )

    # Actions on `job`:
    if job is not None:
        count = -1  # just in case; make sure all specified jobs will be submitted

        # sanity check:
        if babs_proj.processing_level == 'subject':
            expected_len = 1
        elif babs_proj.processing_level == 'session':
            expected_len = 2
        for i_job in range(0, len(job)):
            # expected length in each sub-list:
            assert len(job[i_job]) == expected_len, (
                'There should be '
                + str(expected_len)
                + ' arguments in `--job`,'
                + ' as processing level is '
                + babs_proj.processing_level
                + '!'
            )
            # 1st argument:
            assert job[i_job][0][0:4] == 'sub-', (
                'The 1st argument of `--job`' + " should be 'sub-*'!"
            )
            if babs_proj.processing_level == 'session':
                # 2nd argument:
                assert job[i_job][1][0:4] == 'ses-', (
                    'The 2nd argument of `--job`' + " should be 'ses-*'!"
                )

        # turn into a pandas DataFrame:
        if babs_proj.processing_level == 'subject':
            df_job_specified = pd.DataFrame(
                None, index=list(range(0, len(job))), columns=['sub_id']
            )
        elif babs_proj.processing_level == 'session':
            df_job_specified = pd.DataFrame(
                None, index=list(range(0, len(job))), columns=['sub_id', 'ses_id']
            )
        for i_job in range(0, len(job)):
            df_job_specified.at[i_job, 'sub_id'] = job[i_job][0]
            if babs_proj.processing_level == 'session':
                df_job_specified.at[i_job, 'ses_id'] = job[i_job][1]

        # sanity check:
        df_job_specified = check_df_job_specific(
            df_job_specified,
            babs_proj.job_status_path_abs,
            babs_proj.processing_level,
            'babs submit',
        )
    else:  # `job` is None:
        df_job_specified = None

    # Call method `babs_submit()`:
    babs_proj.babs_submit(count, df_job_specified)


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
    parser.add_argument(
        '--resubmit',
        action='append',  # append each `--resubmit` as a list;
        # ref: https://docs.python.org/3/library/argparse.html
        nargs=1,  # expect 1 argument per `--resubmit` from the command line;
        choices=['failed', 'pending'],
        # NOTE: ^^ not to include 'stalled' as it has not been tested yet.
        metavar=('condition to resubmit'),
        help='Resubmit jobs with what kind of status.'
        ' ``failed``: Jobs that failed, i.e.,'
        ' jobs that are out of queue but do not have results pushed to output RIA.'
        ' The list of failed jobs can also be found by filtering jobs with'
        " ``'is_failed' = True`` in ``job_status.csv``;"
        ' ``pending``: Jobs that are pending (without error) in the queue.'
        " Example job status code of pending: 'qw' on SGE, or 'PD' on Slurm.",
    )
    # "'stalled': the previous submitted job is pending with error in the queue "
    # "(example qstat code: 'eqw')."

    parser.add_argument(
        '--resubmit-job',
        action='append',  # append each `--resubmit-job` as a list;
        nargs='+',
        help='The subject ID (and session ID) whose job to be resubmitted.'
        ' You can repeat this argument many times to request resubmissions of more than one job.'
        ' Currently, only pending or failed jobs in the request will be resubmitted.',
    )
    # ^^ NOTE: not to include 'stalled' jobs here;
    # ROADMAP: improve the strategy to deal with `eqw` (stalled) is not to resubmit,
    #                   but fix the issue - Bergman 12/20/22 email
    # NOTE: not to add `--reckless` (below), as it has not been tested yet.
    # parser.add_argument(
    #     '--reckless',
    #     action='store_true',
    #     # ^^ if `--reckless` is specified, args.reckless = True; otherwise, False
    #     help="Whether to resubmit jobs listed in `--resubmit-job`, even they're done or running."
    #     " WARNING: This hasn't been tested yet!!!")
    parser.add_argument(
        '--container_config',
        '--container-config',
        help='Path to a YAML file that contains the configurations'
        ' of how to run the BIDS App container. It may include ``alert_log_messages`` section.'
        ' ``babs status`` will use this section for failed job auditing,'
        ' by checking if any defined alert messages'
        " can be found in failed jobs' log files.",
    )

    return parser


def _enter_status(argv=None):
    """Entry point for `babs-status` command.

    This function is deprecated and will be removed in a future release.
    Please use `babs status` instead.
    """
    warnings.warn(
        'babs-status is deprecated and will be removed in the future. Please use babs status.',
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_status().parse_args(argv)
    babs_status_main(**vars(options))


def babs_status_main(
    project_root: str,
    resubmit: list,
    resubmit_job: list,
    container_config: str,
    reckless: bool = False,
):
    """
    This is the core function of `babs status`.

    Parameters
    ----------
    project_root: str
        absolute path to the directory of BABS project
    resubmit: nested list or None
        each sub-list: one of 'failed', 'pending'. Not to include 'stalled' now until tested.
    resubmit_job: nested list or None
        For each sub-list, the length should be 1 (for subject) or 2 (for session)
    container_config : str or None
        Path to a YAML file that contains the configurations
        of how to run the BIDS App container.
        It may include 'alert_log_messages' section
        to be used by babs status.
    reckless: bool
        Whether to resubmit jobs listed in `--resubmit-job`, even they're done or running.
        This is hardcoded as False for now.

    Notes
    -----
    NOTE: Not to include `reckless` in `babs status` CLI for now.
    If `reckless` is added in the future,
        please make sure you remove command `args.reckless = False` below!
    Below are commented:
    reckless: bool
            Whether to resubmit jobs listed in `--resubmit-job`, even they're done or running
            This is used when `--resubmit-job`
    """
    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Check if this csv file has been created, if not, create it:
    create_job_status_csv(babs_proj)
    # ^^ this is required by the sanity check `check_df_job_specific`

    # Get the list of resubmit conditions:
    if resubmit is not None:  # user specified --resubmit
        # e.g., [['pending'], ['failed']]
        # change nested list to a simple list:
        flags_resubmit = []
        for i in range(0, len(resubmit)):
            flags_resubmit.append(resubmit[i][0])

        # remove duplicated elements:
        flags_resubmit = list(set(flags_resubmit))  # `list(set())`: acts like "unique"

        # print message:
        print(
            'Will resubmit jobs if ' + ' or '.join(flags_resubmit) + '.'
        )  # e.g., `failed`; `failed or pending`

    else:  # `resubmit` is None:
        print('Did not request resubmit based on job states (no `--resubmit`).')
        flags_resubmit = []  # empty list

    # If `resubmit-job` is requested:
    if resubmit_job is not None:
        # sanity check:
        if babs_proj.processing_level == 'subject':
            expected_len = 1
        elif babs_proj.processing_level == 'session':
            expected_len = 2

        for i_job in range(0, len(resubmit_job)):
            # expected length in each sub-list:
            assert len(resubmit_job[i_job]) == expected_len, (
                'There should be '
                + str(expected_len)
                + ' arguments in `--resubmit-job`,'
                + ' as processing level is '
                + babs_proj.processing_level
                + '!'
            )
            # 1st argument:
            assert resubmit_job[i_job][0][0:4] == 'sub-', (
                'The 1st argument of `--resubmit-job`' + " should be 'sub-*'!"
            )
            if babs_proj.processing_level == 'session':
                # 2nd argument:
                assert resubmit_job[i_job][1][0:4] == 'ses-', (
                    'The 2nd argument of `--resubmit-job`' + " should be 'ses-*'!"
                )

        # turn into a pandas DataFrame:
        if babs_proj.processing_level == 'subject':
            df_resubmit_job_specific = pd.DataFrame(
                None, index=list(range(0, len(resubmit_job))), columns=['sub_id']
            )
        elif babs_proj.processing_level == 'session':
            df_resubmit_job_specific = pd.DataFrame(
                None,
                index=list(range(0, len(resubmit_job))),
                columns=['sub_id', 'ses_id'],
            )

        for i_job in range(0, len(resubmit_job)):
            df_resubmit_job_specific.at[i_job, 'sub_id'] = resubmit_job[i_job][0]
            if babs_proj.processing_level == 'session':
                df_resubmit_job_specific.at[i_job, 'ses_id'] = resubmit_job[i_job][1]

        # sanity check:
        df_resubmit_job_specific = check_df_job_specific(
            df_resubmit_job_specific,
            babs_proj.job_status_path_abs,
            babs_proj.processing_level,
            'babs status',
        )

        if len(df_resubmit_job_specific) > 0:
            if reckless:  # if `--reckless`:
                print(
                    'Will resubmit all the job(s) listed in `--resubmit-job`,'
                    " even if they're done or running."
                )
            else:
                print(
                    'Will resubmit the job(s) listed in `--resubmit-job`,'
                    " if they're pending or failed."
                )  # not to include 'stalled'
        else:  # in theory should not happen, but just in case:
            raise Exception('There is no valid job in --resubmit-job!')

    else:  # `--resubmit-job` is None:
        df_resubmit_job_specific = None

    # Call method `babs_status()`:
    babs_proj.babs_status(
        flags_resubmit,
        df_resubmit_job_specific,
        reckless,
        container_config,
    )


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

    babs_proj_config = read_yaml(babs_proj_config_yaml, if_filelock=True)

    # make sure the YAML file has necessary sections:
    list_sections = ['processing_level', 'queue', 'input_ds', 'container']
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
    input_ds_yaml = babs_proj_config['input_ds']
    # sanity check:
    if len(input_ds_yaml) == 0:  # there was no input ds:
        raise Exception(
            "Section 'input_ds' in `analysis/code/babs_proj_config.yaml`"
            'does not include any input dataset!'
            ' Something was wrong during `babs init`...'
        )

    datasets = {}  # to be a nested list
    for i_ds in range(0, len(input_ds_yaml)):
        ds_index_str = '$INPUT_DATASET_#' + str(i_ds + 1)
        datasets[input_ds_yaml[ds_index_str]['name']] = input_ds_yaml[ds_index_str]['path_in']

    # Get the class `InputDatasets`:
    input_ds = InputDatasets(datasets)
    # update information based on current babs project:
    # 1. `path_now_abs`:
    input_ds.assign_path_now_abs(babs_proj.analysis_path)
    # 2. `path_data_rel` and `is_zipped`:
    for i_ds in range(0, input_ds.num_ds):
        ds_index_str = '$INPUT_DATASET_#' + str(i_ds + 1)
        # `path_data_rel`:
        input_ds.df.loc[i_ds, 'path_data_rel'] = babs_proj_config['input_ds'][ds_index_str][
            'path_data_rel'
        ]
        # `is_zipped`:
        input_ds.df.loc[i_ds, 'is_zipped'] = babs_proj_config['input_ds'][ds_index_str][
            'is_zipped'
        ]

    return babs_proj, input_ds


def check_df_job_specific(df, job_status_path_abs, processing_level, which_function):
    """
    This is to perform sanity check on the pd.DataFrame `df`
    which is used by `babs submit --job` and `babs status --resubmit-job`.
    Sanity checks include:
    1. Remove any duplicated jobs in requests
    2. Check if requested jobs are part of the inclusion jobs to run

    Parameters
    ----------
    df: pd.DataFrame
        i.e., `df_job_specific`
        list of sub_id (and ses_id, if session) that the user requests to submit or resubmit
    job_status_path_abs: str
        absolute path to the `job_status.csv`
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    which_function: str
        'babs status' or 'babs submit'
        The warning message will be tailored based on this.

    Returns
    -------
    df: pd.DataFrame
        after removing duplications, if there is

    Notes
    -----
    The `job_status.csv` file must present before running this function!
    Please use `create_job_status_csv()` from `utils.py` to create

    TODO
    ----
    if `--job-csv` is added in `babs submit`, update the `which_function`
    so that warnings/error messages are up-to-date (using `--job or --job-csv`)
    """

    # 1. Sanity check: there should not be duplications in `df`:
    df_unique = df.drop_duplicates(keep='first')  # default: keep='first'
    if df_unique.shape[0] != df.shape[0]:
        to_print = 'There are duplications in requested '
        if which_function == 'babs submit':
            to_print += '`--job`'
        elif which_function == 'babs status':
            to_print += '`--resubmit-job`'
        else:
            raise Exception('Invalid `which_function`: ' + which_function)
        to_print += ' . Only the first occuration(s) will be kept...'
        warnings.warn(to_print, stacklevel=2)

        df = df_unique  # update with the unique one

    # 2. Sanity check: `df` should be a sub-set of all jobs:
    # read the `job_status.csv`:
    lock_path = job_status_path_abs + '.lock'
    lock = FileLock(lock_path)
    try:
        with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
            df_job = read_job_status_csv(job_status_path_abs)

            # check if `df` is sub-set of `df_job`:
            df_intersection = df.merge(df_job).drop_duplicates()
            # `df_job` should not contain duplications, but just in case..
            # ^^ ref: https://stackoverflow.com/questions/49530918/
            #           check-if-pandas-dataframe-is-subset-of-other-dataframe
            if len(df_intersection) != len(df):
                to_print = 'Some of the subjects (and sessions) requested in '
                if which_function == 'babs submit':
                    to_print += '`--job`'
                elif which_function == 'babs status':
                    to_print += '`--resubmit-job`'
                else:
                    raise Exception('Invalid `which_function`: ' + which_function)
                to_print += (
                    ' are not in the final list of included subjects (and sessions).'
                    ' Path to this final inclusion list is at: ' + job_status_path_abs
                )
                raise Exception(to_print)

    except Timeout:  # after waiting for time defined in `timeout`:
        # if another instance also uses locks, and is currently running,
        #   there will be a timeout error
        print('Another instance of this application currently holds the lock.')

    return df


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
