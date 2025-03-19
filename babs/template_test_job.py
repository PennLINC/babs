# This python script will be copied to `analysis/code/check_setup` folder
# and will be used during `babs check-setup`

import argparse
import os
import os.path as op
import subprocess
import sys


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--path-workspace',
        '--path_workspace',
        help='The path of ephemeral compute workspace',
        required=True,
    )
    parser.add_argument(
        '--path-check-setup',
        '--path_check_setup',
        help='The path to analysis/code/check_setup folder',
        required=True,
    )

    return parser


def main():
    # Get arguments:
    args = cli().parse_args()

    # Prepare the yaml file:
    fn_yaml = op.join(args.path_check_setup, 'check_env.yaml')
    if op.exists(fn_yaml):
        os.remove(fn_yaml)  # remove it
    yaml_file = open(fn_yaml, 'w')

    # Initialize the dict:
    config = {}

    # If the path of ephemeral compute workspace is writable:
    flag_writable = os.access(args.path_workspace, os.W_OK)
    config['workspace_writable'] = flag_writable
    # change to the version that `read_yaml()` from babs/utils.py can read:
    if flag_writable:  # True
        str_writable = 'true'
    else:
        str_writable = 'false'
    yaml_file.write('workspace_writable: ' + str_writable + '\n')

    # Which python in current env:
    # assume the python is installed; otherwise this script cannot be run:
    config['which_python'] = sys.executable
    yaml_file.write("which_python: '" + sys.executable + "'\n")

    # Check each dependent packages' versions:
    config['version'] = {}
    yaml_file.write('version:\n')
    # What packages' versions to check:
    what_versions = {
        'datalad': 'datalad --version',
        'git': 'git --version',
        'git-annex': 'git-annex version',
        'datalad_containers': 'datalad containers-add --version',
    }
    for key in what_versions:
        the_command = what_versions[key]
        try:
            proc = subprocess.run(the_command.split(' '), stdout=subprocess.PIPE)
            proc.check_returncode()
            if key == 'git-annex':
                temp = proc.stdout.decode('utf-8').split('\n')[0]
                config['version'][key] = temp
            else:
                config['version'][key] = proc.stdout.decode('utf-8').replace('\n', '')
        except Exception:
            config['version'][key] = 'not_installed'

        yaml_file.write('  ' + key + ": '" + config['version'][key] + "'\n")

    yaml_file.close()


if __name__ == '__main__':
    main()
