"""This provides command-line interfaces of babs functions"""

import argparse
import os
import os.path as op
import traceback
import datalad.api as dlapi
import pandas as pd
import yaml
import warnings
from filelock import Timeout, FileLock
# import sys
# from datalad.interface.base import build_doc

# from babs.core_functions import babs_init, babs_submit, babs_status
from babs.utils import (if_input_ds_from_osf,
                        read_yaml,
                        write_yaml,
                        get_datalad_version,
                        validate_type_session,
                        read_job_status_csv,
                        create_job_status_csv)
from babs.babs import BABS, Input_ds, System

# @build_doc
def babs_init_cli():
    """
    Initialize a BABS project and bootstrap scripts that will be used later.
    """
    parser = argparse.ArgumentParser(
        description="``babs-init`` initializes a BABS project and bootstraps scripts"
                    " that will be used later.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--where_project", "--where-project",
        help="Absolute path to the directory where the babs project will locate",
        required=True)
    parser.add_argument(
        "--project_name", "--project-name",
        help="The name of the babs project; "
             "this folder will be automatically created in the directory"
             " specified in ``--where_project``.",
        required=True)
    parser.add_argument(
        '--input',
        action='append',   # append each `--input` as a list;
        # will get a nested list: [[<ds_name_1>, <ds_path_1>], [<ds_name_2>, <ds_path_2>]]
        # ref: https://docs.python.org/3/library/argparse.html
        nargs=2,   # expect 2 arguments per `--input` from the command line;
        #            they will be gathered as one list
        metavar=('input_dataset_name', 'input_dataset_path'),
        help="Input BIDS DataLad dataset. "
             "Format: ``--input <name> <path/to/input_datalad_dataset>``. "
             "Here ``<name>`` is a name of this input dataset. "
             "``<path/to/input_datalad_dataset>`` is the path to this input dataset.",
        required=True)
    parser.add_argument(
        '--list_sub_file', '--list-sub-file',   # optional flag
        type=str,
        help="Path to the CSV file that lists the subject (and sessions) to analyze; "
        " If there is no such file, please not to specify this flag."
        " Single-session data: column of 'sub_id';"
        " Multi-session data: columns of 'sub_id' and 'ses_id'.",)
    parser.add_argument(
        '--container_ds', '--container-ds',
        help="Path to the container DataLad dataset",
        required=True)
    parser.add_argument(
        '--container_name', '--container-name',
        help="The name of the BIDS App container, i.e.,"
        + " the ``<image NAME>`` used when running ``datalad containers-add <image NAME>``."
        + " Importantly, this should include the BIDS App's name"
        + " to make sure the bootstrap scripts are set up correctly;"
        + " Also, the version number should be added, too."
        + " ``babs-init`` is not case sensitive to this ``--container_name``."
        + " Example: ``toybidsapp-0-0-7`` for toy BIDS App version 0.0.7.",
        # ^^ the BIDS App's name is used to determine: e.g., whether needs/details in $filterfile
        required=True)
    parser.add_argument(
        '--container_config_yaml_file', '--container-config-yaml-file',
        help="Path to a YAML file that contains the configurations"
        " of how to run the BIDS App container")
    parser.add_argument(
        "--type_session", "--type-session",
        choices=['single-ses', 'single_ses', 'single-session', 'single_session',
                 'multi-ses', 'multi_ses', 'multiple-ses', 'multiple_ses',
                 'multi-session', 'multi_session', 'multiple-session', 'multiple_session'],
        help="Whether the input dataset is single-session ['single-ses'] "
             "or multiple-session ['multi-ses']",
        required=True)
    parser.add_argument(
        "--type_system", "--type-system",
        choices=["sge", "slurm"],
        help="The name of the job scheduling type_system that you will use.",
        required=True)
    parser.add_argument(
        "--keep_if_failed", "--keep-if-failed",
        action='store_true',
        # ^^ if `--keep-if-failed` is specified, args.keep_if_failed = True; otherwise, False
        help="If ``babs-init`` fails with error, whether to keep the created BABS project."
             " By default, you don't need to turn this option on."
             " However, when ``babs-init`` fails and you hope to use ``babs-check-setup``"
             " to diagnose, please turn it on to rerun ``babs-init``,"
             " then run ``babs-check-setup``."
             " Please refer to section below 'What if ``babs-init`` fails?' for details."
        #      ^^ in `babs-init.rst`, pointed to below section for more
    )

    return parser

    # args = parser.parse_args()
    # print(args.input)

    # babs_init(args.where_project, args.project_name,
    #           args.input, args.list_sub_file,
    #           args.container_ds,
    #           args.container_name, args.container_config_yaml_file,
    #           args.type_session, args.type_system)


def babs_init_main():
    # def babs_init(where_project, project_name,
    #               input, list_sub_file,
    #               container_ds,
    #               container_name, container_config_yaml_file,
    #               type_session, type_system):
    """
    This is the core function of babs-init.

    Parameters:
    --------------
    where_project: str
        absolute path to the directory where the project will be created
    project_name: str
        the babs project name
    input: nested list
        for each sub-list:
            element 1: name of input datalad dataset (str)
            element 2: path to the input datalad dataset (str)
    list_sub_file: str or None
        Path to the CSV file that lists the subject (and sessions) to analyze;
        or `None` if CLI's flag isn't specified
        single-ses data: column of 'sub_id';
        multi-ses data: columns of 'sub_id' and 'ses_id'
    container_ds: str
        path to the container datalad dataset
    container_name: str
        name of the container, best to include version number.
        e.g., 'fmriprep-0-0-0'
    container_config_yaml_file: str
        Path to a YAML file that contains the configurations
        of how to run the BIDS App container
    type_session: str
        multi-ses or single-ses
    type_system: str
        sge or slurm
    keep_if_failed: bool
        If `babs-init` failed with error, whether to keep the created BABS project.
    """

    # Get arguments:
    args = babs_init_cli().parse_args()

    where_project = args.where_project
    project_name = args.project_name
    input = args.input
    list_sub_file = args.list_sub_file
    container_ds = args.container_ds
    container_name = args.container_name
    container_config_yaml_file = args.container_config_yaml_file
    type_session = args.type_session
    type_system = args.type_system
    keep_if_failed = args.keep_if_failed

    # =================================================================
    # Sanity checks:
    # =================================================================
    project_root = op.join(where_project, project_name)

    # check if it exists: if so, raise error
    if op.exists(project_root):
        raise Exception("The folder `--project_name` '" + project_name
                        + "' already exists in the directory"
                        + " `--where_project` '" + where_project + "'!"
                        + " `babs-init` won't proceed to overwrite this folder.")

    # check if `where_project` exists:
    if not op.exists(where_project):
        raise Exception("Path provided in `--where_project` does not exist!")

    # check if `where_project` is writable:
    if not os.access(where_project, os.W_OK):
        raise Exception("Path provided in `--where_project` is not writable!")

    # print datalad version:
    #   if no datalad is installed, will raise error
    print("DataLad version: " + get_datalad_version())

    # validate `type_session`:
    type_session = validate_type_session(type_session)

    # input dataset:
    input_ds = Input_ds(input)
    input_ds.get_initial_inclu_df(list_sub_file, type_session)

    # Note: not to perform sanity check on the input dataset re: if it exists
    #   as: 1) robust way is to clone it, which will take longer time;
    #           so better to just leave to the real cloning when `babs-init`;
    #       2) otherwise, if using "if `.datalad/config` exists" to check, then need to check
    #           if input dataset is local or not, and it's very tricky to check that...
    #       3) otherwise, if using "dlapi.status(dataset=the_input_ds)": will take long time
    #           for big dataset; in addition, also need to check if it's local or not...
    # currently solution: add notes in Debugging in `babs-init` docs: `babs-init.rst`

    # Create an instance of babs class:
    babs_proj = BABS(project_root,
                     type_session,
                     type_system)

    # Validate system's type name `type_system`:
    system = System(type_system)

    # print out key information for visual check:
    print("")
    print("project_root of this BABS project: " + babs_proj.project_root)
    print("type of data of this BABS project: " + babs_proj.type_session)
    print("job scheduling system of this BABS project: " + babs_proj.type_system)
    print("")

    # Call method `babs_bootstrap()`:
    #   if success, good!
    #   if failed, and if not `keep_if_failed`: delete the BABS project `babs-init` creates!
    try:
        babs_proj.babs_bootstrap(input_ds,
                                 container_ds, container_name, container_config_yaml_file,
                                 system)
    except:
        print("\n`babs-init` failed! Below is the error message:")
        traceback.print_exc()   # print out the traceback error messages
        if not keep_if_failed:
            # clean up:
            print("\nCleaning up created BABS project...")
            babs_proj.clean_up(input_ds)
            print("Please check the error messages above!"
                  + " Then fix the problem, and rerun `babs-init`.")
        else:
            print("\n`--keep-if-failed` is requested, so not to clean up created BABS project.")
            print("Please check the error messages above!"
                  + " Then fix the problem, delete this failed BABS project,"
                  + " and rerun `babs-init`.")


def babs_check_setup_cli():
    """
    This is the CLI for `babs-check-setup`.
    """

    parser = argparse.ArgumentParser(
        description="``babs-check-setup`` validates setups by `babs-init`.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--project_root", "--project-root",
        help="Absolute path to the root of BABS project."
        " For example, '/path/to/my_BABS_project/'.",
        required=True)
    parser.add_argument(
        "--job_test", "--job-test",
        action='store_true',
        # ^^ if `--job-test` is specified, args.job_test = True; otherwise, False
        help="Whether to submit and run a test job. Will take longer time if doing so.")

    return parser


def babs_check_setup_main():
    """
    This is the core function of babs-check-setup,
    which validates the setups by `babs-init`.

    project_root: str
        Absolute path to the root of BABS project.
        For example, '/path/to/my_BABS_project/'.
    job_test: bool
        Whether to submit and run a test job.
    """

    # Get arguments:
    args = babs_check_setup_cli().parse_args()

    project_root = args.project_root

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, input_ds = get_existing_babs_proj(project_root)

    # Call method `babs_check_setup()`:
    babs_proj.babs_check_setup(input_ds, args.job_test)

def babs_submit_cli():
    """
    Submit jobs.

    Can choose one of these flags:
    --count <number of jobs to submit>  # should be larger than # of `--job`
    --all   # if specified, will submit all remaining jobs that haven't been submitted.
    --job sub-id ses-id   # can repeat

    If none of these flags are specified, will only submit one job.

    Example command:
    # TODO: to add an example command here!
    """

    parser = argparse.ArgumentParser(
        description="Submit jobs that will be run on cluster compute nodes.")
    parser.add_argument(
        "--project_root", "--project-root",
        help="Absolute path to the root of BABS project."
        " For example, '/path/to/my_BABS_project/'.",
        required=True)

    # --count, --job: can only request one of them
    # and none of them are required.
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--count",
        type=int,
        help="Number of jobs to submit. It should be a positive integer.")
    group.add_argument(
        "--all",
        action='store_true',
        # ^^ if `--all` is specified, args.all = True; otherwise, False
        help="Request to run all jobs that haven't been submitted.")
    group.add_argument(
        "--job",
        action='append',   # append each `--job` as a list;
        nargs='+',
        help="The subject ID (and session ID) whose job to be submitted."
        " Can repeat to submit more than one job."
        " Format would be `--job sub-xx` for single-session dataset,"
        " and `--job sub-xx ses-yy` for multiple-session dataset.")

    return parser

    # args = parser.parse_args()

    # babs_submit(args.project_root,
    #             args.count,  # if not provided, will be `None`
    #             args.job)

def babs_submit_main():
    # def babs_submit(project_root, count=None, job=None):
    """
    This is the core function of `babs-submit`.

    Parameters:
    --------------
    project_root: str
        absolute path to the directory of BABS project
    all: bool
        whether to submit all remaining jobs
    count: int or None
        number of jobs to be submitted
        default: None (did not specify in cli)
            if `--job` is not requested, it will be changed to `1` before going into `babs_submit()`
        any negative int will be treated as submitting all jobs that haven't been submitted.
    job: nested list or None
        For each sub-list, the length should be 1 (for single-ses) or 2 (for multi-ses)
    """

    # Get arguments:
    args = babs_submit_cli().parse_args()

    project_root = args.project_root
    count = args.count
    all = args.all
    job = args.job

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Check if this csv file has been created, if not, create it:
    create_job_status_csv(babs_proj)
    # ^^ this is required by the sanity check `check_df_job_specific`

    # Actions on `count`:
    if all:   # if True:
        count = -1  # so that to submit all remaining jobs
    if count is None:
        count = 1   # if not to specify `--count`, change to 1
    # sanity check:
    if count == 0:
        raise Exception("`--count 0` is not valid! Please specify a positive integer. "
                        + "To submit all jobs, please do not specify `--count`.")

    # Actions on `job`:
    if job is not None:
        count = -1    # just in case; make sure all specified jobs will be submitted

        # sanity check:
        if babs_proj.type_session == "single-ses":
            expected_len = 1
        elif babs_proj.type_session == "multi-ses":
            expected_len = 2
        for i_job in range(0, len(job)):
            # expected length in each sub-list:
            assert len(job[i_job]) == expected_len, \
                "There should be " + str(expected_len) + " arguments in `--job`," \
                + " as input dataset(s) is " + babs_proj.type_session + "!"
            # 1st argument:
            assert job[i_job][0][0:4] == "sub-", \
                "The 1st argument of `--job`" + " should be 'sub-*'!"
            if babs_proj.type_session == "multi-ses":
                # 2nd argument:
                assert job[i_job][1][0:4] == "ses-", \
                    "The 2nd argument of `--job`" + " should be 'ses-*'!"

        # turn into a pandas DataFrame:
        if babs_proj.type_session == "single-ses":
            df_job_specified = pd.DataFrame(None,
                                            index=list(range(0, len(job))),
                                            columns=['sub_id'])
        elif babs_proj.type_session == "multi-ses":
            df_job_specified = pd.DataFrame(None,
                                            index=list(range(0, len(job))),
                                            columns=['sub_id', 'ses_id'])
        for i_job in range(0, len(job)):
            df_job_specified.at[i_job, "sub_id"] = job[i_job][0]
            if babs_proj.type_session == "multi-ses":
                df_job_specified.at[i_job, "ses_id"] = job[i_job][1]

        # sanity check:
        df_job_specified = \
            check_df_job_specific(df_job_specified, babs_proj.job_status_path_abs,
                                  babs_proj.type_session, "babs-submit")
    else:  # `job` is None:
        df_job_specified = None

    # Call method `babs_submit()`:
    babs_proj.babs_submit(count, df_job_specified)

def babs_status_cli():
    """
    Check job status.

    Example command:
    # TODO: to add an example command here!
    """

    parser = argparse.ArgumentParser(
        description="Check job status in a BABS project.")
    parser.add_argument(
        "--project_root", "--project-root",
        help="Absolute path to the root of BABS project."
        " For example, '/path/to/my_BABS_project/'.",
        required=True)
    parser.add_argument(
        '--resubmit',
        action='append',   # append each `--resubmit` as a list;
        # ref: https://docs.python.org/3/library/argparse.html
        nargs=1,   # expect 1 argument per `--resubmit` from the command line;
        choices=['failed', 'pending', 'stalled'],
        metavar=('condition to resubmit'),
        help="Under what condition to perform job resubmit. "
             "'failed': the previous submitted job failed "
             "('is_failed' = True in 'job_status.csv'); "
             "'pending': the previous submitted job is pending (without error) in the queue "
             "(example qstat code: 'qw'); "
             "'stalled': the previous submitted job is pending with error in the queue "
             "(example qstat code: 'eqw')."
        )
    parser.add_argument(
        '--resubmit-job',
        action="append",   # append each `--resubmit-job` as a list;
        nargs="+",
        help="The subject ID (and session ID) whose job to be resubmitted."
        " Can repeat to submit more than one job."
        " Currently, this can only resubmit pending, failed, or stalled jobs.")
    # ^^ NOTE: ROADMAP: improve the strategy to deal with `eqw` (stalled) is not to resubmit,
    #                   but fix the issue - Bergman 12/20/22 email
    parser.add_argument(
        '--reckless',
        action='store_true',
        # ^^ if `--reckless` is specified, args.reckless = True; otherwise, False
        help="Whether to resubmit jobs listed in `--resubmit-job`, even they're done or running."
        " WARNING: This hasn't been tested yet!!!")
    parser.add_argument(
        '--container_config_yaml_file', '--container-config-yaml-file',
        help="Path to a YAML file that contains the configurations"
        " of how to run the BIDS App container. It may include 'alert_log_messages' section"
        " to be used by babs-status.")
    parser.add_argument(
        '--job_account', '--job-account',
        action='store_true',
        # ^^ if `--job-account` is specified, args.job_account = True; otherwise, False
        help="Whether to account failed jobs, which may take some time."
             " If `--resubmit failed` or `--resubmit-job` for this failed job is also requested,"
             " this `--job-account` will be skipped.")

    return parser

    # args = parser.parse_args()

    # babs_status(args.project_root,
    #             args.resubmit,
    #             args.resubmit_job, args.reckless,
    #             args.container_config_yaml_file,
    #             args.job_account)

def babs_status_main():
    # def babs_status(project_root, resubmit=None,
    #                 resubmit_job=None, reckless=False,
    #                 container_config_yaml_file=None,
    #                 job_account=False):
    """
    This is the core function of `babs-status`.

    Parameters:
    --------------
    project_root: str
        absolute path to the directory of BABS project
    resubmit: nested list or None
        each sub-list: one of 'failed', 'pending', 'stalled'
    resubmit_job: nested list or None
        For each sub-list, the length should be 1 (for single-ses) or 2 (for multi-ses)
    reckless: bool
        Whether to resubmit jobs listed in `--resubmit-job`, even they're done or running
        This is used when `--resubmit-job`
    container_config_yaml_file: str or None
        Path to a YAML file that contains the configurations
        of how to run the BIDS App container.
        It may include 'alert_log_messages' section
        to be used by babs-status.
    job_account: bool
        Whether to account failed jobs (e.g., using `qacct` for SGE),
        which may take some time.
    """

    # Get arguments:
    args = babs_status_cli().parse_args()

    project_root = args.project_root
    resubmit = args.resubmit
    resubmit_job = args.resubmit_job
    reckless = args.reckless
    container_config_yaml_file = args.container_config_yaml_file
    job_account = args.job_account

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Check if this csv file has been created, if not, create it:
    create_job_status_csv(babs_proj)
    # ^^ this is required by the sanity check `check_df_job_specific`

    # Get the list of resubmit conditions:
    if resubmit is not None:   # user specified --resubmit
        # e.g., [['pending'], ['failed']]
        # change nested list to a simple list:
        flags_resubmit = []
        for i in range(0, len(resubmit)):
            flags_resubmit.append(resubmit[i][0])

        # remove duplicated elements:
        flags_resubmit = list(set(flags_resubmit))   # `list(set())`: acts like "unique"

        # print message:
        print(
            "Will resubmit jobs if "
            + " or ".join(flags_resubmit) + ".")   # e.g., `failed`; `failed or pending`

    else:   # `resubmit` is None:
        print("Did not request resubmit based on job states (no `--resubmit`).")
        flags_resubmit = []   # empty list

    # If `--job-account` is requested:
    if job_account:
        if "failed" not in flags_resubmit:
            print("`--job-account` was requested; `babs-status` may take longer time...")
        else:
            # this is meaningless to run `job-account` if resubmitting anyway:
            print(
                "Although `--job-account` was requested,"
                + " as `--resubmit failed` was also requested,"
                + " it's meaningless to run job account on previous failed jobs,"
                + " so will skip `--job-account`")

    # If `resubmit-job` is requested:
    if resubmit_job is not None:
        # sanity check:
        if babs_proj.type_session == "single-ses":
            expected_len = 1
        elif babs_proj.type_session == "multi-ses":
            expected_len = 2

        for i_job in range(0, len(resubmit_job)):
            # expected length in each sub-list:
            assert len(resubmit_job[i_job]) == expected_len, \
                "There should be " + str(expected_len) + " arguments in `--resubmit-job`," \
                + " as input dataset(s) is " + babs_proj.type_session + "!"
            # 1st argument:
            assert resubmit_job[i_job][0][0:4] == "sub-", \
                "The 1st argument of `--resubmit-job`" + " should be 'sub-*'!"
            if babs_proj.type_session == "multi-ses":
                # 2nd argument:
                assert resubmit_job[i_job][1][0:4] == "ses-", \
                    "The 2nd argument of `--resubmit-job`" + " should be 'ses-*'!"

        # turn into a pandas DataFrame:
        if babs_proj.type_session == "single-ses":
            df_resubmit_job_specific = \
                pd.DataFrame(None,
                             index=list(range(0, len(resubmit_job))),
                             columns=['sub_id'])
        elif babs_proj.type_session == "multi-ses":
            df_resubmit_job_specific = \
                pd.DataFrame(None,
                             index=list(range(0, len(resubmit_job))),
                             columns=['sub_id', 'ses_id'])

        for i_job in range(0, len(resubmit_job)):
            df_resubmit_job_specific.at[i_job, "sub_id"] = resubmit_job[i_job][0]
            if babs_proj.type_session == "multi-ses":
                df_resubmit_job_specific.at[i_job, "ses_id"] = resubmit_job[i_job][1]

        # sanity check:
        df_resubmit_job_specific = \
            check_df_job_specific(df_resubmit_job_specific, babs_proj.job_status_path_abs,
                                  babs_proj.type_session, "babs-status")

        if len(df_resubmit_job_specific) > 0:
            if reckless:    # if `--reckless`:
                print("Will resubmit all the job(s) listed in `--resubmit-job`,"
                      + " even if they're done or running.")
            else:
                print("Will resubmit the job(s) listed in `--resubmit-job`,"
                      + " if they're pending, failed or stalled.")
        else:    # in theory should not happen, but just in case:
            raise Exception("There is no valid job in --resubmit-job!")

    else:   # `--resubmit-job` is None:
        df_resubmit_job_specific = None

    # Call method `babs_status()`:
    babs_proj.babs_status(flags_resubmit, df_resubmit_job_specific, reckless,
                          container_config_yaml_file, job_account)


def babs_merge_cli():
    """
    CLI for merging results.
    """
    parser = argparse.ArgumentParser(
        description="``babs-merge`` merges results and provenance"
        " from all successfully finished jobs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--project_root", "--project-root",
        help="Absolute path to the root of BABS project."
        " For example, '/path/to/my_BABS_project/'.",
        required=True)
    parser.add_argument(
        "--chunk-size", "--chunk_size",
        type=int,
        default=2000,
        help="Number of branches in a chunk when merging at a time."
             " We recommend using default value.")
    # Matt: 5000 is not good, 2000 is appropriate.
    #   Smaller chunk is, more merging commits which is fine.
    parser.add_argument(
        "--trial-run", "--trial_run",
        action='store_true',
        # ^^ if `--trial-run` is specified, args.trial_run = True; otherwise, False
        help="Whether to run as a trial run which won't push the merge back to output RIA."
             " This option should only be used by developers for testing purpose."
             " Users: please don't turn this on!")

    return parser

def babs_merge_main():
    """
    To merge results and provenance from all successfully finished jobs.

    Parameters:
    ----------------
    project_root: str
        Absolute path to the root of BABS project.
    chunk_size: int
        Number of branches in a chunk when merging at a time.
    trial_run: bool
        Whether to run as a trial run which won't push the merging actions back to output RIA.
        This option should only be used by developers for testing purpose.
    """
    # Get arguments:
    args = babs_merge_cli().parse_args()
    project_root = args.project_root

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Call method `babs_merge()`:
    babs_proj.babs_merge(args.chunk_size, args.trial_run)


def babs_unzip_cli():
    """ CLI for babs-unzip """

    parser = argparse.ArgumentParser(
        description="``babs-unzip`` unzips results zip files and extracts desired files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--project_root", "--project-root",
        help="Absolute path to the root of BABS project."
        " For example, '/path/to/my_BABS_project/'.",
        required=True)
    parser.add_argument(
        '--container_config_yaml_file', '--container-config-yaml-file',
        help="Path to a YAML file of the BIDS App container that contains information of"
        " what files to unzip etc.")
    
    return parser


def babs_unzip_main():
    """
    This is the core function of babs-unzip, which unzip results zip files
    and extracts desired files.

    project_root: str
        Absolute path to the root of BABS project.
        For example, '/path/to/my_BABS_project/'.
    container_config_yaml_file: str
        path to container's configuration YAML file.
        These two sections will be used:
        1. 'unzip_desired_filenames' - must be included
        2. 'rename_conflict_files' - optional
    """

    # Get arguments:
    args = babs_unzip_cli().parse_args()
    project_root = args.project_root
    container_config_yaml_file = args.container_config_yaml_file

    # container config:
    config = read_yaml(container_config_yaml_file)
    # ^^ not to use filelock here - otherwise will create `*.lock` file in user's folder

    # Sanity checks:
    if "unzip_desired_filenames" not in config:
        raise Exception("Section 'unzip_desired_filenames' is not included"
                        " in `--container_config_yaml_file`. This section is required."
                        " Path to this YAML file: '" + container_config_yaml_file + "'.")

    # Get class `BABS` based on saved `analysis/code/babs_proj_config.yaml`:
    babs_proj, _ = get_existing_babs_proj(project_root)

    # Call method `babs_unzip()`:
    babs_proj.babs_unzip(config)


def get_existing_babs_proj(project_root):
    """
    This is to get `babs_proj` (class `BABS`) and `input_ds` (class `Input_ds`)
    based on existing yaml file `babs_proj_config.yaml`.
    This should be used by `babs_submit()` and `babs_status`.

    Parameters:
    --------------
    project_root: str
        absolute path to the directory of BABS project
        TODO: accept relative path too, like datalad's `-d`

    Returns:
    --------------
    babs_proj: class `BABS`
        information about a BABS project
    input_ds: class `Input_ds`
        information about input dataset(s)
    """

    # Sanity check: the path `project_root` exists:
    if op.exists(project_root) is False:
        raise Exception("`--project-root` does not exist! Requested `--project-root` was: "
                        + project_root)

    # Read configurations of BABS project from saved yaml file:
    babs_proj_config_yaml = op.join(project_root,
                                    "analysis/code/babs_proj_config.yaml")
    if op.exists(babs_proj_config_yaml) is False:
        raise Exception(
            "`babs-init` was not successful;"
            + " there is no 'analysis/code/babs_proj_config.yaml' file!"
            + " Please rerun `babs-init` to finish the setup.")

    babs_proj_config = read_yaml(babs_proj_config_yaml, if_filelock=True)

    # make sure the YAML file has necessary sections:
    list_sections = ["type_session", "type_system", "input_ds", "container"]
    for i in range(0, len(list_sections)):
        the_section = list_sections[i]
        if the_section not in babs_proj_config:
            raise Exception(
                "There is no section '" + the_section + "'"
                + " in 'babs_proj_config.yaml' file in 'analysis/code' folder!"
                + " Please rerun `babs-init` to finish the setup.")

    type_session = babs_proj_config["type_session"]
    type_system = babs_proj_config["type_system"]

    # Get the class `BABS`:
    babs_proj = BABS(project_root, type_session, type_system)

    # update key information including `output_ria_data_dir`:
    babs_proj.wtf_key_info(flag_output_ria_only=True)

    # Get information for input dataset:
    input_ds_yaml = babs_proj_config["input_ds"]
    # sanity check:
    if len(input_ds_yaml) == 0:   # there was no input ds:
        raise Exception("Section 'input_ds' in `analysis/code/babs_proj_config.yaml`"
                        + "does not include any input dataset!"
                        + " Something was wrong during `babs-init`...")

    input_cli = []   # to be a nested list
    for i_ds in range(0, len(input_ds_yaml)):
        ds_index_str = "$INPUT_DATASET_#" + str(i_ds+1)
        input_cli.append([input_ds_yaml[ds_index_str]["name"],
                          input_ds_yaml[ds_index_str]["path_in"]])

    # Get the class `Input_ds`:
    input_ds = Input_ds(input_cli)
    # update information based on current babs project:
    # 1. `path_now_abs`:
    input_ds.assign_path_now_abs(babs_proj.analysis_path)
    # 2. `path_data_rel` and `is_zipped`:
    for i_ds in range(0, input_ds.num_ds):
        ds_index_str = "$INPUT_DATASET_#" + str(i_ds+1)
        # `path_data_rel`:
        input_ds.df["path_data_rel"][i_ds] = \
            babs_proj_config["input_ds"][ds_index_str]["path_data_rel"]
        # `is_zipped`:
        input_ds.df["is_zipped"][i_ds] = \
            babs_proj_config["input_ds"][ds_index_str]["is_zipped"]

    return babs_proj, input_ds

def check_df_job_specific(df, job_status_path_abs,
                          type_session, which_function):
    """
    This is to perform sanity check on the pd.DataFrame `df`
    which is used by `babs-submit --job` and `babs-status --resubmit-job`.
    Sanity checks include:
    1. Remove any duplicated jobs in requests
    2. Check if requested jobs are part of the inclusion jobs to run

    Parameters:
    ------------------
    df: pd.DataFrame
        i.e., `df_job_specific`
        list of sub_id (and ses_id, if multi-ses) that the user requests to submit or resubmit
    job_status_path_abs: str
        absolute path to the `job_status.csv`
    type_session: str
        'single-ses' or 'multi-ses'
    which_function: str
        'babs-status' or 'babs-submit'
        The warning message will be tailored based on this.

    Returns:
    ----------------
    df: pd.DataFrame
        after removing duplications, if there is

    Notes:
    --------------
    The `job_status.csv` file must present before running this function!
    Please use `create_job_status_csv()` from `utils.py` to create

    TODO:
    -------------
    if `--job-csv` is added in `babs-submit`, update the `which_function`
    so that warnings/error messages are up-to-date (using `--job or --job-csv`)
    """

    # 1. Sanity check: there should not be duplications in `df`:
    df_unique = df.drop_duplicates(keep='first')   # default: keep='first'
    if df_unique.shape[0] != df.shape[0]:
        to_print = "There are duplications in requested "
        if which_function == "babs-submit":
            to_print += "`--job`"
        elif which_function == "babs-status":
            to_print += "`--resubmit-job`"
        else:
            raise Exception("Invalid `which_function`: " + which_function)
        to_print += " . Only the first occuration(s) will be kept..."
        warnings.warn(to_print)

        df = df_unique   # update with the unique one

    # 2. Sanity check: `df` should be a sub-set of all jobs:
    # read the `job_status.csv`:
    lock_path = job_status_path_abs + ".lock"
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
                to_print = "Some of the subjects (and sessions) requested in "
                if which_function == "babs-submit":
                    to_print += "`--job`"
                elif which_function == "babs-status":
                    to_print += "`--resubmit-job`"
                else:
                    raise Exception("Invalid `which_function`: " + which_function)
                to_print += " are not in the final list of included subjects (and sessions)." \
                    + " Path to this final inclusion list is at: " \
                    + job_status_path_abs
                raise Exception(to_print)

    except Timeout:   # after waiting for time defined in `timeout`:
        # if another instance also uses locks, and is currently running,
        #   there will be a timeout error
        print("Another instance of this application currently holds the lock.")

    return df


# if __name__ == "__main__":
#     babs_check_setup_main()
