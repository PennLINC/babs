"""This provides command-line interfaces of babs functions"""

import argparse
import os
import os.path as op

from babs import babs, core_functions

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
        help="The name of the babs project; this folder will be automatically created in the directory `where_project`.",
        required=True)
    parser.add_argument(
        '--input',
        action='append', nargs=2,   # expect 2 arguments from the command line; they will be gathered as one list
        metavar=('is_zipped', 'path_input_dataset'),
        help='Input datalad dataset. First argument is whether the input dataset is zipped [True] or not [False]. Default is False. Second argument is the path to this input dataset.',
        required=True)
    # TODO: ^^ should be able to accept multiple input datasets!
    parser.add_argument(
        '--container_ds', '--container-ds',
        help="Path to the container datalad dataset",
        required=True)
    parser.add_argument(
        "type_session", "type-session",
        choices=['single-ses', 'single_ses', 'single-session', 'single_session',
                'multi-ses', 'multi_ses', 'multiple-ses', 'multiple_ses',
                'multi-session', 'multi_session','multiple-session', 'multiple_session'], 
        help="Whether the input dataset is single-session ['single-ses'] or multiple-session ['multi-ses']",
        required=True)
    parser.add_argument(
        "--system",
        choices=["sge", "slurm"],
        help="The name of the job scheduling system that you will use. Choices are sge and slurm.",
        required=True)

    args = parser.parse_args()


    if args.type_session in ['single-ses', 'single_ses', 'single-session', 'single_session']:
        type_session = "single-ses"
    elif args.type_session in ['multi-ses', 'multi_ses', 'multiple-ses', 'multiple_ses', 
                'multi-session', 'multi_session','multiple-session', 'multiple_session']:
        type_session = "multi-ses"

    
    babs_init(args.where_project, args.project_name,
            args.input, args.container_ds,
            type_session, args.system)