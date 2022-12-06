"""This provides command-line interfaces of babs functions"""

import argparse
# import os
# import os.path as op
# import sys

from babs.core_functions import babs_init, babs_submit, babs_status
from babs.utils import validate_type_session


def babs_init_cli():
    """
    Initialize a babs project and bootstrap scripts that will be used later.

    Example command:
    # TODO: to add an example command here!

    """

    parser = argparse.ArgumentParser(
        description="Initialize a babs project and bootstrap scripts that will be used later")
    parser.add_argument(
        "--where_project", "--where-project",
        help="Absolute path to the directory where the babs project will locate",
        required=True)
    parser.add_argument(
        "--project_name", "--project-name",
        help="The name of the babs project; "
             "this folder will be automatically created in the directory `where_project`.",
        required=True)
    parser.add_argument(
        '--input',
        action='append',   # append each `--input` as a list;
        # will get a nested list: [[<ds_name_1>, <ds_path_1>], [<ds_name_2>, <ds_path_2>]]
        # ref: https://docs.python.org/3/library/argparse.html
        nargs=2,   # expect 2 arguments per `--input` from the command line;
        #            they will be gathered as one list
        metavar=('input_dataset_name', 'input_dataset_path'),
        help="Input datalad dataset. "
             "First argument is a name of this input dataset. "
             "Second argument is the path to this input dataset.",
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
        help="Path to the container datalad dataset",
        required=True)
    parser.add_argument(
        '--container_name', '--container-name',
        help="The name of the BIDS App container, the `NAME` in `datalad containers-add NAME`."
        + " Importantly, this should include the BIDS App's name"
        + " to make sure the bootstrap scripts are set up correctly;"
        + " Also, the version number should be added, too. "
        + " `babs-init` is not case sensitive to this `--container_name`"
        + " Example: `QSIPrep-0-0-0`",
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
        "--type_system",
        choices=["sge", "slurm"],
        help="The name of the job scheduling type_system that you will use. Choices are sge and slurm.",
        required=True)

    args = parser.parse_args()
    # print(args.input)

    babs_init(args.where_project, args.project_name,
              args.input, args.list_sub_file,
              args.container_ds,
              args.container_name, args.container_config_yaml_file,
              args.type_session, args.type_system)


def babs_submit_cli():
    """
    Submit jobs.

    --count <number of jobs to submit>  # should be larger than # of `--job`
    --job sub-id ses-id   # can repeat

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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--count",
        type=int,
        help="Number of jobs to submit. It should be a positive integer.")
    group.add_argument(
        "--job",
        action='append',   # append each `--job` as a list;
        nargs='+',
        help="The subject ID (and session ID) whose job to be submitted."
        " Can repeat to submit more than one job.")

    args = parser.parse_args()

    babs_submit(args.project_root,
                args.count,  # if not provided, will be `None`
                args.job)

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
        '--rerun',
        action='append',   # append each `--rerun` as a list;
        # ref: https://docs.python.org/3/library/argparse.html
        nargs=1,   # expect 1 argument per `--rerun` from the command line;
        choices=['failed', 'pending', 'stalled'],
        metavar=('condition to rerun'),
        help="Under what condition to perform job rerun. "
             "'failed': the previous submitted job has some error "
             "('has_error' = True in 'job_status.csv'); "
             "'pending': the previous submitted job is pending (without error) in the queue "
             "(example qstat code: 'qw'); "
             "'stalled': the previous submitted job is pending with error in the queue "
             "(example qstat code: 'eqw')."
        )
    # TODO: to add `--rerun-job <specific sub and ses>`

    args = parser.parse_args()

    babs_status(args.project_root,
                args.rerun)

# if __name__ == "__main__":
#     babs_init_cli()
