# This python script will be copied to `analysis/code/check_setup` folder
# and will be used during `babs-check-setup`
# This requires `pandas` and `pyyaml >= 6.0` python packages to complete.

# NOTE: update this script so that it does not rely on `pandas` and `yaml`

import argparse
import os
import os.path as op
import sys
import subprocess
import pandas as pd
import yaml

def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path-workspace", "--path_workspace",
        help="The path of ephemeral compute workspace",
        required=True)
    parser.add_argument(
        "--path-check-setup", "--path_check_setup",
        help="The path to analysis/code/check_setup folder",
        required=True)

    return parser

def write_yaml(config, fn, if_filelock=False):
    """
    This is to write contents into yaml file.
    Ref: `write_yaml()` from `babs/utils.py` in BABS.
    Here we won't use FileLock

    Parameters:
    ---------------
    config: dict
        the content to write into yaml file
    fn: str
        path to the yaml file
    if_filelock: bool
        whether to use filelock
    """

    with open(fn, "w") as f:
        _ = yaml.dump(config, f,
                      sort_keys=False,   # not to sort by keys
                      default_flow_style=False)  # keep the format of nested contents
    f.close()


def main():
    # Get arguments:
    args = cli().parse_args()

    # Prepare the yaml file:
    fn_yaml = op.join(args.path_check_setup, "check_env.yaml")
    if op.exists(fn_yaml):
        os.remove(fn_yaml)   # remove it

    # Initialize the dict:
    config = {}

    # If the path of ephemeral compute workspace is writable:
    flag_writable = os.access(args.path_workspace, os.W_OK)
    config["workspace_writable"] = flag_writable

    # Which python in current env:
    # assume the python is installed; otherwise this script cannot be run:
    config["which_python"] = sys.executable

    # Check each dependent packages' versions:
    config["version"] = {}
    # What packages' versions to check:
    what_versions = [['datalad', 'datalad --version'],
                     ['git', 'git --version'],
                     ['git-annex', 'git-annex version'],
                     ['datalad_containers', 'datalad containers-add --version']]
    df = pd.DataFrame(what_versions, columns=['package', 'command'])
    for i in range(0, df.shape[0]):
        try:
            proc = subprocess.run(df.at[i, "command"].split(" "),
                                  stdout=subprocess.PIPE)
            proc.check_returncode()
            if df.at[i, "package"] == "git-annex":
                temp = proc.stdout.decode('utf-8').split("\n")[0]
                config["version"][df.at[i, "package"]] = temp
            else:
                config["version"][df.at[i, "package"]] = \
                    proc.stdout.decode('utf-8').replace("\n", "")
        except:
            config["version"][df.at[i, "package"]] = "not_installed"

    # Save to yaml file:
    write_yaml(config, fn_yaml)

    # Print success:
    print("SUCCESS")


if __name__ == "__main__":
    main()
