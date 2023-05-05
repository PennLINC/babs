""" Utils and helper functions """

import os
import os.path as op
import sys
import warnings   # built-in, no need to install
import pkg_resources
# from ruamel.yaml import YAML
import yaml
import pprint
import glob
import regex
import copy
import pandas as pd
import numpy as np
from filelock import Timeout, FileLock
import subprocess
from qstat import qstat  # https://github.com/relleums/qstat
from datetime import datetime
import re

# Disable the behavior of printing messages:
def blockPrint():
    sys.stdout = open(os.devnull, 'w')

# Restore the behavior of printing messages:
def enablePrint():
    sys.stdout = sys.__stdout__

def get_datalad_version():
    return pkg_resources.get_distribution("datalad").version


def get_immediate_subdirectories(a_dir):
    return [
        name for name in os.listdir(a_dir) if os.path.isdir(os.path.join(a_dir, name))
    ]


def check_validity_unzipped_input_dataset(input_ds, type_session):
    """
    Check if each of the unzipped input datasets is valid.
    Here we only check the "unzipped" datasets;
    the "zipped" dataset will be checked in `generate_cmd_unzip_inputds()`.

    * if it's multi-ses: subject + session should both appear
    * if it's single-ses: there should be sub folder, but no ses folder

    Parameters:
    ------------------
    input_ds: class `Input_ds`
        info on input dataset(s)
    type_session: str
        multi-ses or single-ses

    Notes:
    -----------
    Tested with multi-ses and single-ses data;
        made sure that only single-ses data + type_session = "multi-ses" raise error.
    TODO: add above tests to pytests
    """

    if type_session not in ["multi-ses", "single-ses"]:
        raise Exception("invalid `type_session`!")

    if False in list(input_ds.df["is_zipped"]):  # there is at least one dataset is unzipped
        print("Performing sanity check for any unzipped input dataset...")

    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df["is_zipped"][i_ds] is False:   # unzipped ds:
            is_valid_sublevel = False

            input_ds_path = input_ds.df["path_now_abs"][i_ds]
            list_subs = get_immediate_subdirectories(input_ds_path)
            for sub_temp in list_subs:   # if one of the folder starts with "sub-", then it's fine
                if sub_temp[0:4] == "sub-":
                    is_valid_sublevel = True
                    break
            if not is_valid_sublevel:
                raise Exception(
                    "There is no `sub-*` folder in input dataset #" + str(i_ds+1)
                    + " '" + input_ds.df["name"][i_ds] + "'!"
                )

            if type_session == "multi-ses":
                for sub_temp in list_subs:  # every sub- folder should contain a session folder
                    if sub_temp[0] == ".":  # hidden folder
                        continue  # skip it
                    is_valid_seslevel = False
                    list_sess = get_immediate_subdirectories(op.join(input_ds_path, sub_temp))
                    for ses_temp in list_sess:
                        if ses_temp[0:4] == "ses-":
                            # if one of the folder starts with "ses-", then it's fine
                            is_valid_seslevel = True
                            break

                    if not is_valid_seslevel:
                        raise Exception(
                            "In input dataset #" + str(i_ds+1)
                            + " '" + input_ds.df["name"][i_ds] + "',"
                            + " there is no `ses-*` folder in subject folder '" + sub_temp
                            + "'!"
                        )


def if_input_ds_from_osf(path_in):
    """
    This is to check if the input datalad dataset is from OSF.
    Checking is based on the pattern of the path's string. Might not be robust!

    Parameters:
    -----------
    path_in: str
        path to the input dataset

    Returns:
    --------
    if_osf: bool
        the input dataset is from OSF (True) or not (False)
    """

    if_osf = False
    if path_in[0:6] == "osf://":
        if_osf = True
    if path_in[0:14] == "https://osf.io":
        if_osf = True

    return if_osf


def validate_type_session(type_session):
    """
    This is to validate variable `type_session`'s value
    If it's one of supported string, change to the standard string
    if not, raise error message.
    """
    if type_session in ["single-ses", "single_ses", "single-session", "single_session"]:
        type_session = "single-ses"
    elif type_session in [
        "multi-ses",
        "multi_ses",
        "multiple-ses",
        "multiple_ses",
        "multi-session",
        "multi_session",
        "multiple-session",
        "multiple_session",
    ]:
        type_session = "multi-ses"
    else:
        raise Exception("`type_session = " + type_session + "` is not allowed!")

    return type_session

def validate_type_system(type_system):
    """
    To validate if the type of the cluster system is valid.
    For valid ones, the type string will be changed to lower case.
    If not valid, raise error message.
    """
    list_supported = ['sge']  # TODO: add 'slurm'
    if type_system.lower() in list_supported:
        type_system = type_system.lower()   # change to lower case, if needed
    else:
        raise Exception("Invalid cluster system type: '" + type_system + "'!"
                        + " Currently BABS only support one of these: "
                        + ', '.join(list_supported))   # names separated by ', '
    return type_system


def read_yaml(fn, if_filelock=False):
    """
    This is to read yaml file.

    Parameters:
    ---------------
    fn: str
        path to the yaml file
    if_filelock: bool
        whether to use filelock

    Returns:
    ------------
    config: dict
        content of the yaml file
    """

    if if_filelock:
        lock_path = fn + ".lock"
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                with open(fn) as f:
                    config = yaml.load(f, Loader=yaml.FullLoader)
                    # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`
                f.close()
        except Timeout:   # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print("Another instance of this application currently holds the lock.")
    else:
        with open(fn) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`
        f.close()

    return config

def write_yaml(config, fn, if_filelock=False):
    """
    This is to write contents into yaml file.

    Parameters:
    ---------------
    config: dict
        the content to write into yaml file
    fn: str
        path to the yaml file
    if_filelock: bool
        whether to use filelock
    """
    if if_filelock:
        lock_path = fn + ".lock"
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                with open(fn, "w") as f:
                    _ = yaml.dump(config, f,
                                  sort_keys=False,   # not to sort by keys
                                  default_flow_style=False)  # keep the format of nested contents
                f.close()
        except Timeout:   # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print("Another instance of this application currently holds the lock.")
    else:
        with open(fn, "w") as f:
            _ = yaml.dump(config, f,
                          sort_keys=False,   # not to sort by keys
                          default_flow_style=False)  # keep the format of nested contents
        f.close()


def replace_placeholder_from_config(value):
    """
    Replace the placeholder in values in container config yaml file

    Parameters:
    -------------
    value: str (or number)
        the value (v.s. key) in the input container config yaml file. Read in by babs.
        Okay to be a number; we will change it to str.

    """
    value = str(value)
    if value == "$BABS_TMPDIR":
        replaced = "${PWD}/.git/tmp/wkdir"

    return replaced


def generate_cmd_singularityRun_from_config(config, input_ds):
    """
    This is to generate command (in strings) of singularity run
    from config read from container config yaml file.

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`
    input_ds: class `Input_ds`
        input dataset(s) information
    Returns:
    ---------
    cmd: str
        It's part of the singularity run command; it is generated
        based on section `singularity_run` in the yaml file.
    flag_fs_license: True or False
        Whether FreeSurfer's license will be used.
        This is determined by checking if there is argument called `--fs-license-file`
        If so, the license file will be bound into and used by the container
    path_fs_license: None or str
        Path to the FreeSurfer license. This is provided by the user in `--fs-license-file`.
    singuRun_input_dir: None or str
        The positional argument of input dataset path in `singularity run`
    """
    # human readable: (just like appearance in a yaml file;
    # print(yaml.dump(config["singularity_run"], sort_keys=False))

    # not very human readable way, if nested structure:
    # for key, value in config.items():
    #     print(key + " : " + str(value))

    from .constants import PATH_FS_LICENSE_IN_CONTAINER

    cmd = ""
    # is_first_flag = True
    flag_fs_license = False
    path_fs_license = None
    singuRun_input_dir = None

    # re: positional argu `$INPUT_PATH`:
    if input_ds.num_ds > 1:   # more than 1 input dataset:
        # check if `$INPUT_PATH` is one of the keys (must):
        if "$INPUT_PATH" not in config["singularity_run"]:
            raise Exception("The key '$INPUT_PATH' is expected in section `singularity_run`"
                            + " in `container_config_yaml_file`, because there are more than"
                            + " one input dataset!")
    else:   # only 1 input dataset:
        # check if the path is consistent with the name of the only input ds's name:
        if "$INPUT_PATH" in config["singularity_run"]:
            expected_temp = "inputs/data/" + input_ds.df["name"][0]
            if config["singularity_run"]["$INPUT_PATH"] != expected_temp:
                raise Exception("As there is only one input dataset, the value of '$INPUT_PATH'"
                                + " in section `singularity_run`"
                                + " in `container_config_yaml_file` should be"
                                + " '" + expected_temp + "'; You can also choose"
                                + " not to specify '$INPUT_PATH'.")

    # example key: "-w", "--n_cpus"
    # example value: "", "xxx", Null (placeholder)
    for key, value in config["singularity_run"].items():
        # print(key + ": " + str(value))

        if key == "$INPUT_PATH":  # placeholder
            #   if not, warning....
            if value[-1] == "/":
                value = value[:-1]   # remove the unnecessary forward slash at the end

            # sanity check that `value` should match with one of input ds's `path_data_rel`
            if value not in list(input_ds.df["path_data_rel"]):  # after unzip, if needed
                warnings.warn("'" + value + "' specified after $INPUT_PATH"
                              + " (in section `singularity_run`"
                              + " in `container_config_yaml_file`), does not"
                                + " match with any dataset's current path."
                                + " This may cause error when running the BIDS App.")

            singuRun_input_dir = value
            # ^^ no matter one or more input dataset(s)
            # and not add to the flag cmd

        # Check if FreeSurfer license will be used:
        elif key == "--fs-license-file":
            flag_fs_license = True
            path_fs_license = value   # the provided value is the path to the FS license
            # sanity check: `path_fs_license` exists:
            if op.exists(path_fs_license) is False:
                # raise a warning, instead of an error
                #   so that pytest using example yaml files will always pass
                #   regardless of the path provided in the yaml file
                warnings.warn(
                    "Path to FreeSurfer license provided in `--fs-license-file`"
                    + " in container's configuration YAML file"
                    + " does NOT exist! The path provided: '"
                    + path_fs_license + "'.")

            # if alright: Now use the path within the container:
            cmd += " \\" + "\n\t" + str(key) + " " + PATH_FS_LICENSE_IN_CONTAINER
            # ^^ the 'license.txt' will be bound to above path.

        else:   # check on values:
            if value == "":   # a flag, without value
                cmd += " \\" + "\n\t" + str(key)
            else:  # a flag with value
                # check if it is a placeholder which needs to be replaced:
                # e.g., `$BABS_TMPDIR`
                if str(value)[:6] == "$BABS_":
                    replaced = replace_placeholder_from_config(value)
                    cmd += " \\" + "\n\t" + str(key) + " " + str(replaced)

                elif value is None:    # if entered `Null` or `NULL` without quotes
                    cmd += " \\" + "\n\t" + str(key)
                elif value in ["Null", "NULL"]:  # "Null" or "NULL" w/ quotes, i.e., as strings
                    cmd += " \\" + "\n\t" + str(key)

                # there is no placeholder to deal with:
                else:
                    cmd += " \\" + "\n\t" + str(key) + " " + str(value)

    # Finalize `singuRun_input_dir`:
    if singuRun_input_dir is None:
        # now, it must be only one input dataset, and user did not provide `$INPUT_PATH` key:
        assert input_ds.num_ds == 1
        singuRun_input_dir = input_ds.df["path_data_rel"][0]
        # ^^ path to data (if zipped ds: after unzipping)

    # example of access one slot:
    # config["singularity_run"]["n_cpus"]

    # print(cmd)
    return cmd, flag_fs_license, path_fs_license, singuRun_input_dir

# adding zip filename:
    # if value != '':
    #     raise Exception("Invalid element under `one_dash`: " + str(key) + ": " + str(value) +
    #                     "\n" + "The value should be empty '', instead of " + str(value))
    #     # tested: '' or "" is the same to pyyaml


def generate_cmd_set_envvar(env_var_name):
    """
    This is to generate argument `--env` in `singularity run`,
    and to get the env var value for later use: binding the path (env var value).
    Call this function for `TEMPLATEFLOW_HOME`.

    Parameters:
    ----------------
    env_var_name: str
        The name of the environment variable to be injected into the container
        e.g., "TEMPLATEFLOW_HOME"

    Returns:
    ------------
    cmd: str
        argument `--env` of `singularity run`
        e.g., `--env TEMPLATEFLOW_HOME=/TEMPLATEFLOW_HOME`
    value: str
        The value of the env variable `env_var_name`
    env_var_value_in_container: str
        The env var value used in container;
        e.g., "/SGLR/TEMPLATEFLOW_HOME"
    """

    # Generate argument `--env` in `singularity run`:
    env_var_value_in_container = "/SGLR/" + env_var_name

    # cmd should be: `--env TEMPLATEFLOW_HOME=/SGLR/TEMPLATEFLOW_HOME`
    cmd = "--env "
    cmd += env_var_name + "=" + env_var_value_in_container

    # Get env var's value, to be used for binding `-B` in `singularity run`:
    env_var_value = os.getenv(env_var_name)

    # If it's templateflow:
    if env_var_name == "TEMPLATEFLOW_HOME":
        if env_var_value is None:
            warnings.warn("Usually BIDS App depends on TemplateFlow,"
                          + " but environment variable `TEMPLATEFLOW_HOME` was not set up."
                          + " Therefore, BABS will not bind its directory"
                          + " or inject this environment variable into the container"
                          + " when running the container. This may cause errors.")

    return cmd, env_var_value, env_var_value_in_container


def generate_cmd_zipping_from_config(config, type_session, output_foldername="outputs"):
    """
    This is to generate bash command to zip BIDS App outputs.

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`
    type_session: str
        "multi-ses" or "single-ses"
    output_foldername: str
        the foldername of the outputs of BIDS App; default is "outputs".

    Returns:
    ---------
    cmd: str
        It's part of the `<containerName_zip.sh>`; it is generated
        based on section `zip_foldernames` in the yaml file.
    """

    # cd to output folder:
    cmd = "cd " + output_foldername + "\n"

    # 7z:
    if type_session == "multi-ses":
        str_sesid = "_${sesid}"
    else:
        str_sesid = ""

    if "zip_foldernames" in config:
        value_temp = ""
        temp = 0

        for key, value in config["zip_foldernames"].items():
            # each key is a foldername to be zipped;
            # each value is the version string;
            temp = temp + 1
            if (temp != 1) & (value_temp != value):    # not matching last value
                warnings.warn("In section `zip_foldernames` in `container_config_yaml_file`: \n"
                              "The version string of '" + key + "': '" + value + "'"
                              + " does not match with the last version string; "
                              + "we suggest using the same version string across all foldernames.")
            value_temp = value

            cmd += "7z a ../${subid}" + str_sesid + "_" + \
                key + "-" + value + ".zip" + " " + key + "\n"
            # e.g., 7z a ../${subid}_${sesid}_fmriprep-0-0-0.zip fmriprep  # this is multi-ses

    else:    # the yaml file does not have the section `zip_foldernames`:
        raise Exception("The `container_config_yaml_file` does not contain"
                        + " the section `zip_foldernames`. Please add this section!")

    # return to original dir:
    cmd += "cd ..\n"

    return cmd


def generate_cmd_filterfile(container_name):
    """
    This is to generate the command for generating the filter file (.json)
    which is used by BIDS App e.g., fMRIPrep and QSIPrep's argument
    `--bids-filter-file $filterfile`.
    This command will be part of `<containerName_zip.sh>`.
    """

    cmd = ""

    cmd += """# Create a filter file that only allows this session
filterfile=${PWD}/${sesid}_filter.json
echo "{" > ${filterfile}"""

    cmd += """\necho "'fmap': {'datatype': 'fmap'}," >> ${filterfile}"""

    if "fmriprep" in container_name.lower():
        cmd += """\necho "'bold': {'datatype': 'func', 'session': '$sesid', 'suffix': 'bold'}," >> ${filterfile}"""  # noqa: E731,E123

    elif "qsiprep" in container_name.lower():
        cmd += """\necho "'dwi': {'datatype': 'dwi', 'session': '$sesid', 'suffix': 'dwi'}," >> ${filterfile}"""  # noqa: E731,E123

    cmd += """
echo "'sbref': {'datatype': 'func', 'session': '$sesid', 'suffix': 'sbref'}," >> ${filterfile}
echo "'flair': {'datatype': 'anat', 'session': '$sesid', 'suffix': 'FLAIR'}," >> ${filterfile}
echo "'t2w': {'datatype': 'anat', 'session': '$sesid', 'suffix': 'T2w'}," >> ${filterfile}
echo "'t1w': {'datatype': 'anat', 'session': '$sesid', 'suffix': 'T1w'}," >> ${filterfile}
echo "'roi': {'datatype': 'anat', 'session': '$sesid', 'suffix': 'roi'}" >> ${filterfile}
echo "}" >> ${filterfile}

# remove ses and get valid json"""

    # below is one command but has to be cut into several pieces to print:
    cmd += """\nsed -i "s/'/"""
    cmd += """\\"""     # this is to print out "\";
    cmd += '"/g" ${filterfile}'

    cmd += """\nsed -i "s/ses-//g" ${filterfile}"""

    cmd += "\n"

    return cmd


def generate_cmd_unzip_inputds(input_ds, type_session):
    """
    This is to generate command in `<containerName>_zip.sh` to unzip
    a specific input dataset if needed.

    Parameters:
    -------------
    input_ds: class `Input_ds`
        information about input dataset(s)
    type_session: str
        "multi-ses" or "single-ses"

    Returns:
    ---------
    cmd: str
        It's part of the `<containerName_zip.sh>`.
        Example of Way #1:
            wd=${PWD}
            cd inputs/data/freesurfer
            7z x `basename ${FREESURFER_ZIP}`
            cd $wd
        Examples of Way #2: (now commented out)
            wd=${PWD}
            cd inputs/data/fmriprep
            7z x ${subid}_${sesid}_fmriprep-20.2.3.zip
            cd $wd


    """

    cmd = ""

    if True in list(input_ds.df["is_zipped"]):
        # print("there is zipped dataset to be unzipped.")
        cmd += "\nwd=${PWD}"

    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df["is_zipped"][i_ds] is True:  # zipped ds
            cmd += "\ncd " + input_ds.df["path_now_rel"][i_ds]

            # Way #1: directly use the argument in `<container>_zip.sh`, e.g., ${FREESURFER_ZIP}
            # -----------------------------------------------------------------------------------
            #   basically getting the zipfilename will be done in `participant_job.sh` by bash
            cmd += "\n7z x `basename ${" + input_ds.df["name"][i_ds].upper() + "_ZIP}`"
            #   ^^ ${FREESURFER_ZIP} includes `path_now_rel` of input_ds
            #   so needs to get the basename

            # Way #2: get the tag in the zipfilename ---------------------------------------------
            #   but need to assume it's consistent across all zipfilename...
            # # get the zip filename:
            # if type_session == "multi-ses":
            #     list_zipfiles = \
            #         glob.glob(op.join(input_ds.df["path_now_abs"][i_ds],
            #                           "sub-*_ses-*_" + input_ds.df["name"][i_ds] + "*.zip"))
            #     if len(list_zipfiles) == 0:
            #         raise Exception("In zipped input dataset '" + input_ds.df["name"][i_ds] + "',"
            #                         + " the zip file(s) does not follow the pattern of "
            #                         + "'sub-*_ses-*_'" + input_ds.df["name"][i_ds] + "*.zip")
            # elif type_session == "single-ses":
            #     list_zipfiles = \
            #         glob.glob(op.join(input_ds.df["path_now_abs"][i_ds],
            #                           "sub-*_" + input_ds.df["name"][i_ds] + "*.zip"))
            #     if len(list_zipfiles) == 0:
            #         raise Exception("In zipped input dataset '" + input_ds.df["name"][i_ds] + "',"
            #                         + " the zip file(s) does not follow the pattern of "
            #                         + "'sub-*_'" + input_ds.df["name"][i_ds] + "*.zip")
            # else:
            #     raise Exception("invalid `type_session`: " + type_session)

            # # assume all the zip filenames are regular, so only check out the first one:

            # temp_filename = op.basename(list_zipfiles[0])
            # temp_regex = regex.search(input_ds.df["name"][i_ds] + '(.*)' + '.zip',
            #                           temp_filename)
            # temp_pattern = temp_regex.group(0)   # e.g., "fmriprep-0.0.0.zip"
            # # ^^ .group(1) will be "-0.0.0"
            # if type_session == "multi-ses":
            #     cmd += "\n7z x ${subid}_${sesid}_" + \
            #         temp_pattern
            # elif type_session == "single-ses":
            #     cmd += "\n7z x ${subid}_" + temp_pattern

            cmd += "\ncd $wd\n"

    return cmd


def generate_one_bashhead_resources(system, key, value):
    """
    This is to generate one command in the head of the bash file
    for requesting cluster resources.

    Parameters:
    ------------
    system: class `System`
        information about cluster management system
    value: str or number
        value of a key in section `cluster_resources` container's config yaml
        if it's number, will be changed to a string.

    Returns:
    -----------
    cmd: str
        one command of requesting cluster resource.
        This does not include "\n" at the end.
        e.g., "#$ -S /bin/bash".

    """
    cmd = "#"
    if system.type == "sge":
        cmd += "$ "
    # TODO: add slurm's

    # find the key in the `system.dict`:
    if key not in system.dict:
        raise Exception("Invalid key '" + key + "' in section `cluster_resources`"
                        + " in `container_config_yaml_file`; This key has not been defined"
                        + " in file 'dict_cluster_systems.yaml'.")

    # get the format:
    the_format = system.dict[key]
    # replace the placeholder "$VALUE" in the format with the real value defined by user:
    cmd += the_format.replace("$VALUE", str(value))

    return cmd

def generate_bashhead_resources(system, config):
    """
    This is to generate the head of the bash file
    for requesting cluster resources.

    Parameters:
    ------------
    system: class `System`
        information about cluster management system
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`

    Returns:
    ------------
    cmd: str
        It's part of the `participant_job.sh`; it is generated
        based on config yaml file and the system's dict.
    """

    cmd = ""

    # sanity check: `cluster_resources` exists:
    if "cluster_resources" not in config:
        raise Exception("There is no section `cluster_resources`"
                        + " in `container_config_yaml_file`!")

    # loop: for each key, call `generate_one_bashhead_resources()`:
    for key, value in config["cluster_resources"].items():
        if key == "customized_text":
            pass   # handle this below
        else:
            one_cmd = generate_one_bashhead_resources(system, key, value)
            cmd += one_cmd + "\n"

    if "customized_text" in config["cluster_resources"]:
        cmd += config["cluster_resources"]["customized_text"]
        cmd += "\n"

    return cmd

def generate_cmd_script_preamble(config):
    """
    This is to generate bash cmd based on `script_preamble`
    from the `container_config_yaml_file`

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`

    Returns:
    ------------
    cmd: str
        It's part of the `participant_job.sh`; it is generated
        based on config yaml file.
    """

    cmd = ""

    if "script_preamble" not in config:
        warnings.warn("Did not find the section 'script_preamble'"
                      + " in `container_config_yaml_file`."
                        + " Not to generate script preamble.")
        # TODO: ^^ this should be changed to an error!
    else:   # there is `script_preamble`:
        # directly grab the commands in the section:
        cmd += "\n# Script preambles:\n"
        cmd += config["script_preamble"]

    cmd += "\necho I" + "\\" + "\'" + "m in $PWD using `which python`\n"

    return cmd

def generate_cmd_job_compute_space(config):
    """
    This is to generate bash cmd based on `job_compute_space`
    from the `container_config_yaml_file`

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`

    Returns:
    ------------
    cmd: str
        It's part of the `participant_job.sh`; it is generated
        based on config yaml file.
    """

    cmd = ""
    # sanity check:
    if "job_compute_space" not in config:
        raise Exception("Did not find the section 'job_compute_space'"
                        + " in `container_config_yaml_file`!")

    cmd += "\n# Change path to an ephemeral (temporary) job compute workspace:\n"
    cmd += "# The path is specified according to 'job_compute_space'" \
        + " in container's configuration YAML file.\n"
    cmd += "cd " + config["job_compute_space"] + "\n"

    return cmd

def generate_cmd_determine_zipfilename(input_ds, type_session):
    """
    This is to generate bash cmd that determines the path to the zipfile of a specific
    subject (or session). This command will be used in `participant_job.sh`.
    This command should be generated after `datalad get -n <input_ds>`,
    i.e., after there is list of data in <input_ds> folder

    Parameters:
    -----------
    input_ds: class Input_ds
        information about input dataset(s)
    type_session: str
        "multi-ses" or "single-ses"

    Returns:
    -----------
    cmd: str
        the bash command used in `participant_job.sh`

    Notes:
    -----------
    ref: `bootstrap-fmriprep-ingressed-fs.sh`
    """

    cmd = ""

    if True in list(input_ds.df["is_zipped"]):  # there is at least one dataset is zipped
        cmd += "\n# Get the zip filename of current subject (or session):\n"

    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df["is_zipped"][i_ds] is True:   # is zipped:
            variable_name_zip = input_ds.df["name"][i_ds] + "_ZIP"
            variable_name_zip = variable_name_zip.upper()   # change to upper case
            cmd += variable_name_zip + "=" + "$(ls " \
                + input_ds.df["path_now_rel"][i_ds] + "/${subid}_"

            if type_session == "multi-ses":
                cmd += "${sesid}_"

            cmd += "*" + input_ds.df["name"][i_ds] + "*.zip" \
                + " | cut -d '@' -f 1 || true)" + "\n"
            # `cut -d '@' -f 1` means:
            #   field separator (or delimiter) is @ (`-d '@'`), and get the 1st field (`-f 1`)
            # `<command> || true` means:
            #   the bash script won't abort even if <command> fails
            #   useful when `set -e` (where any error would cause the shell to exit)

            cmd += "echo 'found " + input_ds.df["name"][i_ds] + " zipfile:'" + "\n"
            cmd += "echo ${" + variable_name_zip + "}" + "\n"

            # check if it exists:
            cmd += 'if [ -z "${' + variable_name_zip + '}" ]; then' + "\n"
            cmd += "\t" + "echo 'No input zipfile of " + input_ds.df["name"][i_ds] \
                + " found for ${subid}"
            if type_session == "multi-ses":
                cmd += " ${sesid}"
            cmd += "'" + "\n"
            cmd += "\t" + "exit 99" + "\n"
            cmd += "fi" + "\n"

            # sanity check: there should be only 1 matched file:
            # change into array: e.g., array=($FREESURFER_ZIP)
            cmd += 'array=($' + variable_name_zip + ')' + "\n"
            # if [ "$a" -gt "$b" ]; then
            cmd += 'if [ "${#array[@]}" -gt "1" ]; then' + "\n"
            cmd += "\t" + "echo 'There is more than one input zipfile of " \
                + input_ds.df["name"][i_ds] \
                + " found for ${subid}"
            if type_session == "multi-ses":
                cmd += " ${sesid}"
            cmd += "'" + "\n"
            cmd += "\t" + "exit 98" + "\n"
            cmd += "fi" + "\n"

    """
    example:
    FREESURFER_ZIP=$(ls inputs/data/freesurfer/${subid}_free*.zip | cut -d '@' -f 1 || true)

    echo Freesurfer Zipfile
    echo ${FREESURFER_ZIP}

    if [ -z "${FREESURFER_ZIP}" ]; then
        echo "No freesurfer results found for ${subid}"
        exit 99
    fi
    """

    return cmd


def generate_cmd_datalad_run(container, input_ds, type_session):
    """
    This is to generate the command of `datalad run`
    included in `participant_job.sh`.

    Parameters:
    ------------
    container: class `Container`
        Information about the container
    input_ds: class `Input_ds`
        Information about input dataset(s)
    type_session: str
        "multi-ses" or "single-ses"

    Returns:
    ------------
    cmd: str
        `datalad run`, part of the `participant_job.sh`.
    
    Notes:
    ----------
    Needs to quote any globs (`*`) in `-i` (or `-o`)!!
        Otherwise, after expansion by DataLad, some values might miss `-i` (or `-o`)!
    """

    cmd = ""
    cmd += "datalad run \\" + "\n"

    # input: `<containerName>_zip.sh`:
    bash_bidsapp_zip_path_rel = op.join("code", container.container_name + "_zip.sh")
    cmd += "\t" + "-i " + bash_bidsapp_zip_path_rel + " \\" + "\n"

    # input: each input dataset (depending on zipped or not)
    flag_expand_inputs = False
    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df["is_zipped"][i_ds] is False:  # not zipped
            # input: a subject or session folder
            if type_session == "multi-ses":
                cmd += "\t" + "-i " + input_ds.df["path_now_rel"][i_ds] + "/" \
                    + '${subid}/${sesid}' + " \\" + "\n"
            elif type_session == "single-ses":
                cmd += "\t" + "-i " + input_ds.df["path_now_rel"][i_ds] + "/" \
                    + '${subid}' + " \\" + "\n"

            # input: also the json file:
            # as using globs `*`, need to be quoted (`''`)!
            cmd += "\t" + "-i '" + input_ds.df["path_now_rel"][i_ds] + "/" \
                + "*json" + "' \\" + "\n"
            flag_expand_inputs = True    # `--expand inputs`

        else:   # zipped:
            cmd += "\t" + "-i ${" + input_ds.df["name"][i_ds].upper() + "_ZIP}" \
                + " \\" + "\n"

    # input: container image
    cmd += "\t" + "-i " + container.container_path_relToAnalysis + " \\" + "\n"

    # --expand:
    # ^^ Expand globs when storing inputs and/or outputs in the commit message.
    # might be needed when `*` in --inputs or --outputs?
    # NOTE: why `bootstrap-fmriprep-ingressed-fs.sh` has `--expand outputs`???
    if flag_expand_inputs is True:
        cmd += "\t" + "--expand inputs" + " \\" + "\n"

    # --explicit
    cmd += "\t" + "--explicit" + " \\" + "\n"

    # output: each zipped file
    fixed_cmd = "\t" + "-o ${subid}_"
    if type_session == 'multi-ses':
        fixed_cmd += "${sesid}_"

    for key, value in container.config["zip_foldernames"].items():
        cmd += fixed_cmd + key + "-" + value + ".zip" + " \\" + "\n"

    # message:
    cmd += "\t" + '-m "' + container.container_name \
        + " ${subid}"
    if type_session == "multi-ses":
        cmd += " ${sesid}"
    cmd += '"' + " \\" + "\n"

    # the real command:
    cmd += "\t" + '"' + "bash ./code/" + container.container_name \
        + "_zip.sh" + " ${subid}"
    if type_session == "multi-ses":
        cmd += " ${sesid}"
    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df["is_zipped"][i_ds] is True:   # is zipped:
            cmd += " ${" + input_ds.df["name"][i_ds].upper() + "_ZIP}"
    cmd += '"' + "\n"

    return cmd

def get_list_sub_ses(input_ds, config, babs):
    """
    This is to get the list of subjects (and sessions) to analyze.

    Parameters:
    ------------
    input_ds: class `Input_ds`
        information about input dataset(s)
    config: config from class `Container`
        container's yaml file that's read into python
    babs: class `BABS`
        information about the BABS project.

    Returns:
    -----------
    single-ses project: a list of subjects
    multi-ses project: a dict of subjects and their sessions
    """

    # Get the initial list of subjects (and sessions): -------------------------------
    #   This depends on flag `list_sub_file`
    #       If it is None: get the initial list from input dataset
    #       If it's a csv file, use it as initial list
    if input_ds.initial_inclu_df is not None:   # there is initial including list
        # no need to sort (as already done when validating)
        print("Using the subjects (sessions) list provided in `list_sub_file`"
              + " as the initial inclusion list.")
        if babs.type_session == "single-ses":
            subs = list(input_ds.initial_inclu_df["sub_id"])
            # ^^ turn into a list
        elif babs.type_session == "multi-ses":
            dict_sub_ses = \
                input_ds.initial_inclu_df.groupby('sub_id')['ses_id'].apply(list).to_dict()
            # ^^ group based on 'sub_id', apply list to every group,
            #   then turn into a dict.
            #   above won't change `input_ds.initial_inclu_df`

    else:   # no initial list:
        # TODO: ROADMAP: for each input dataset, get a list, then get the overlapped list
        # for now, only check the first dataset
        print("Did not provide `list_sub_file`."
              + " Will look into the first input dataset"
              + " to get the initial inclusion list.")
        i_ds = 0
        if input_ds.df["is_zipped"][i_ds] is False:   # not zipped:
            full_paths = sorted(glob.glob(input_ds.df["path_now_abs"][i_ds]
                                          + "/sub-*"))
            # no need to check if there is `sub-*` in this dataset
            #   have been checked in `check_validity_unzipped_input_dataset()`
            # only get the sub's foldername, if it's a directory:
            subs = [op.basename(temp) for temp in full_paths if op.isdir(temp)]
        else:    # zipped:
            # full paths to the zip files:
            if babs.type_session == "single-ses":
                full_paths = glob.glob(input_ds.df["path_now_abs"][i_ds]
                                       + "/sub-*_" + input_ds.df["name"][i_ds] + "*.zip")
            elif babs.type_session == "multi-ses":
                full_paths = glob.glob(input_ds.df["path_now_abs"][i_ds]
                                       + "/sub-*_ses-*" + input_ds.df["name"][i_ds] + "*.zip")
                # ^^ above pattern makes sure only gets subs who have more than one ses
            full_paths = sorted(full_paths)
            zipfilenames = [op.basename(temp) for temp in full_paths]
            subs = [temp.split('_', 3)[0] for temp in zipfilenames]
            # ^^ str.split("delimiter", <maxsplit>)[i-th_field]
            # <maxsplit> means max number of "cuts"; # of total fields = <maxsplit> + 1
            subs = sorted(list(set(subs)))   # `list(set())`: acts like "unique"

        # if it's multi-ses, get list of sessions for each subject:
        if babs.type_session == "multi-ses":
            # a nested list of sub and ses:
            #   first level is sub; second level is sess of a sub
            list_sub_ses = [None] * len(subs)   # predefine a list
            if input_ds.df["is_zipped"][i_ds] is False:   # not zipped:
                for i_sub, sub in enumerate(subs):
                    # get the list of sess:
                    full_paths = glob.glob(
                        op.join(input_ds.df["path_now_abs"][i_ds],
                                sub, "ses-*"))
                    full_paths = sorted(full_paths)
                    sess = [op.basename(temp) for temp in full_paths if op.isdir(temp)]
                    # no need to validate again that session exists
                    # -  have been done in `check_validity_unzipped_input_dataset()`

                    list_sub_ses[i_sub] = sess

            else:    # zipped:
                for i_sub, sub in enumerate(subs):
                    # get the list of sess:
                    full_paths = glob.glob(
                        op.join(input_ds.df["path_now_abs"][i_ds],
                                sub + "_ses-*_" + input_ds.df["name"][i_ds] + "*.zip"))
                    full_paths = sorted(full_paths)
                    zipfilenames = [op.basename(temp) for temp in full_paths]
                    sess = [temp.split('_', 3)[1] for temp in zipfilenames]
                    # ^^ field #1, i.e., 2nd field which is `ses-*`
                    # no need to validate if sess exists; as it's done when getting `subs`

                    list_sub_ses[i_sub] = sess

            # then turn `subs` and `list_sub_ses` into a dict:
            dict_sub_ses = dict(zip(subs, list_sub_ses))

    # Remove the subjects (or sessions) which does not have the required files:
    #   ------------------------------------------------------------------------
    # remove existing csv files first:
    temp_files = glob.glob(op.join(
        babs.analysis_path, "code/sub_*missing_required_file.csv"))
    # ^^ single-ses: `sub_missing*`; multi-ses: `sub_ses_missing*`
    if len(temp_files) > 0:
        for temp_file in temp_files:
            os.remove(temp_file)
    temp_files = []   # clear
    # for multi-ses:
    fn_csv_sub_delete = op.join(
        babs.analysis_path, "code/sub_missing_any_ses_required_file.csv")
    if op.exists(fn_csv_sub_delete):
        os.remove(fn_csv_sub_delete)

    # read `required_files` section from yaml file, if there is:
    if "required_files" in config:
        print("Filtering out subjects (and sessions) based on `required files`"
              + " designated in `container_config_yaml_file`...")

        # sanity check on the target input dataset(s):
        if len(config["required_files"]) > input_ds.num_ds:
            raise Exception("Number of input datasets designated in `required_files`"
                            + " in `container_config_yaml_file`"
                            + " is more than actual number of input datasets!")
        for i in range(0, len(config["required_files"])):
            i_ds_str = list(config["required_files"].keys())[i]  # $INPUT_DATASET_#?
            i_ds = int(i_ds_str.split('#', 1)[1]) - 1
            # ^^ split the str, get the 2nd field, i.e., '?'; then `-1` to start with 0
            if (i_ds + 1) > input_ds.num_ds:   # if '?' > actual # of input ds:
                raise Exception("'" + i_ds_str + "' does not exist!"
                                + " There is only " + str(input_ds.num_ds)
                                + " input dataset(s)!")

        # for the designated ds, iterate all subjects (or sessions),
        #   remove if does not have the required files, and save to a list -> a csv
        if babs.type_session == "single-ses":
            subs_missing = []
            which_dataset_missing = []
            which_file_missing = []
            # iter across designated input ds in `required_files`:
            for i in range(0, len(config["required_files"])):
                i_ds_str = list(config["required_files"].keys())[i]  # $INPUT_DATASET_#?
                i_ds = int(i_ds_str.split('#', 1)[1]) - 1
                # ^^ split the str, get the 2nd field, i.e., '?'; then `-1` to start with 0
                if input_ds.df["is_zipped"][i_ds] is True:
                    print(i_ds_str + ": '" + input_ds.df["name"][i_ds] + "'"
                          + " is a zipped input dataset; Currently BABS does not support"
                          + " checking if there is missing file in a zipped dataset."
                          + " Skip checking this input dataset...")
                    continue   # skip
                list_required_files = config["required_files"][i_ds_str]

                # iter across subs:
                updated_subs = copy.copy(subs)   # not to reference `subs`, but copy!
                # ^^ only update this list, not `subs` (as it's used in for loop)
                for sub in subs:
                    # iter of list of required files:
                    for required_file in list_required_files:
                        temp_files = glob.glob(
                            op.join(
                                input_ds.df["path_now_abs"][i_ds],
                                sub,
                                required_file))
                        temp_files_2 = glob.glob(
                            op.join(
                                input_ds.df["path_now_abs"][i_ds],
                                sub,
                                "**",   # consider potential `ses-*` folder
                                required_file))
                        #  ^^ "**" means checking "all folders" in a subject
                        #  ^^ "**" does not work if there is no `ses-*` folder,
                        #       so also needs to check `temp_files`
                        if (len(temp_files) == 0) & (len(temp_files_2) == 0):   # didn't find any:
                            # remove from the `subs` list:
                            #   it shouldn't be removed by earlier datasets,
                            #   as we're iter across updated list `sub`
                            updated_subs.remove(sub)
                            # add to missing list:
                            subs_missing.append(sub)
                            which_dataset_missing.append(input_ds.df["name"][i_ds])
                            which_file_missing.append(required_file)
                            # no need to check other required files:
                            break
                # after getting out of for loops of `subs`, update `subs`:
                subs = copy.copy(updated_subs)

            # TODO: when having two unzipped input datasets, test if above works as expected!
            #   esp: removing missing subs (esp missing lists in two input ds are different)
            #   for both 1) single-ses; 2) multi-ses data!

            # save `subs_missing` into a csv file:
            if len(subs_missing) > 0:   # there is missing one
                df_missing = pd.DataFrame(
                    list(zip(
                        subs_missing, which_dataset_missing, which_file_missing)),
                    columns=['sub_id', 'input_dataset_name', 'missing_required_file'])
                fn_csv_missing = op.join(babs.analysis_path, "code/sub_missing_required_file.csv")
                df_missing.to_csv(fn_csv_missing, index=False)
                print("There are " + str(len(subs_missing)) + " subject(s)"
                      + " who don't have required files."
                      + " Please refer to this CSV file for full list and information: "
                      + fn_csv_missing)
                print("BABS will not run the BIDS App on these subjects' data.")
                print("Note for this file: For each reported subject, only"
                      + " one missing required file"
                      + " in one input dataset is recorded,"
                      + " even if there are multiple.")

            else:
                print("All subjects have required files.")

        elif babs.type_session == "multi-ses":
            subs_missing = []  # elements can repeat if more than one ses in a sub has missing file
            sess_missing = []
            which_dataset_missing = []
            which_file_missing = []
            # iter across designated input ds in `required_files`:
            for i in range(0, len(config["required_files"])):
                i_ds_str = list(config["required_files"].keys())[i]  # $INPUT_DATASET_#?
                i_ds = int(i_ds_str.split('#', 1)[1]) - 1
                # ^^ split the str, get the 2nd field, i.e., '?'; then `-1` to start with 0
                if input_ds.df["is_zipped"][i_ds] is True:
                    print(i_ds_str + ": '" + input_ds.df["name"][i_ds] + "'"
                          + " is a zipped input dataset; Currently BABS does not support"
                          + " checking if there is missing file in a zipped dataset."
                          + " Skip checking this input dataset...")
                    continue   # skip
                list_required_files = config["required_files"][i_ds_str]

                # iter across subs: (not to update subs for now)
                for sub in list(dict_sub_ses.keys()):
                    # iter across sess:
                    # make sure there is at least one ses in this sub to loop:
                    if len(dict_sub_ses[sub]) > 0:  # deal with len=0 later
                        updated_sess = copy.deepcopy(dict_sub_ses[sub])
                        for ses in dict_sub_ses[sub]:
                            # iter across list of required files:
                            for required_file in list_required_files:
                                temp_files = glob.glob(
                                    op.join(
                                        input_ds.df["path_now_abs"][i_ds],
                                        sub,
                                        ses,
                                        required_file))
                                if len(temp_files) == 0:  # did not find any:
                                    # remove this ses from dict:
                                    updated_sess.remove(ses)
                                    # add to missing list:
                                    subs_missing.append(sub)
                                    sess_missing.append(ses)
                                    which_dataset_missing.append(input_ds.df["name"][i_ds])
                                    which_file_missing.append(required_file)
                                    # no need to check other required files:
                                    break

                        # after getting out of loops of `sess`, update `sess`:
                        dict_sub_ses[sub] = copy.deepcopy(updated_sess)

            # after getting out of loops of `subs` and list of required files,
            #   go thru the list of subs, and see if the list of ses is empty:
            subs_delete = []
            subs_forloop = copy.deepcopy(list(dict_sub_ses.keys()))
            for sub in subs_forloop:
                # if the list of ses is empty:
                if len(dict_sub_ses[sub]) == 0:
                    # remove this key from the dict:
                    dict_sub_ses.pop(sub)
                    # add to missing sub list:
                    subs_delete.append(sub)

            # save missing ones into a csv file:
            if len(subs_missing) > 0:   # there is missing one:
                df_missing = pd.DataFrame(
                    list(zip(
                        subs_missing, sess_missing,
                        which_dataset_missing, which_file_missing)),
                    columns=['sub_id', 'ses_id',
                             'input_dataset_name', 'missing_required_file'])
                fn_csv_missing = op.join(
                    babs.analysis_path, "code/sub_ses_missing_required_file.csv")
                df_missing.to_csv(fn_csv_missing, index=False)
                print("There are " + str(len(sess_missing)) + " session(s)"
                      + " which don't have required files."
                      + " Please refer to this CSV file for full list and information: "
                      + fn_csv_missing)
                print("BABS will not run the BIDS App on these sessions' data.")
                print("Note for this file: For each reported session, only"
                      + " one missing required file"
                      + " in one input dataset is recorded,"
                      + " even if there are multiple.")
            else:
                print("All sessions from all subjects have required files.")
            # save deleted subjects into a list:
            if len(subs_delete) > 0:
                df_sub_delete = pd.DataFrame(
                    list(zip(
                        subs_delete)),
                    columns=['sub_id'])
                fn_csv_sub_delete = op.join(
                    babs.analysis_path, "code/sub_missing_any_ses_required_file.csv")
                df_sub_delete.to_csv(fn_csv_sub_delete, index=False)
                print("Regarding subjects, " + str(len(subs_delete)) + " subject(s)"
                      + " don't have any session that includes required files."
                      + " Please refer to this CSV file for the full list: "
                      + fn_csv_sub_delete)

    else:
        print("Did not provide `required files` in `container_config_yaml_file`."
              + " Not to filter subjects (or sessions)...")

    # Save the final list of sub/ses in a CSV file:
    if babs.type_session == "single-ses":
        fn_csv_final = op.join(
            babs.analysis_path, babs.list_sub_path_rel)  # "code/sub_final_inclu.csv"
        df_final = pd.DataFrame(
            list(zip(subs)),
            columns=['sub_id'])
        df_final.to_csv(fn_csv_final, index=False)
        print("The final list of included subjects has been saved to this CSV file: "
              + fn_csv_final)
    elif babs.type_session == "multi-ses":
        fn_csv_final = op.join(
            babs.analysis_path, babs.list_sub_path_rel)  # "code/sub_ses_final_inclu.csv"
        subs_final = []
        sess_final = []
        for sub in list(dict_sub_ses.keys()):
            for ses in dict_sub_ses[sub]:
                subs_final.append(sub)
                sess_final.append(ses)
        df_final = pd.DataFrame(
            list(zip(
                subs_final, sess_final)),
            columns=['sub_id', 'ses_id'])
        df_final.to_csv(fn_csv_final, index=False)
        print("The final list of included subjects and sessions has been saved to this CSV file: "
              + fn_csv_final)

    # Return: -------------------------------------------------------
    if babs.type_session == "single-ses":
        return subs
    elif babs.type_session == "multi-ses":
        return dict_sub_ses

def submit_one_job(analysis_path, type_session, sub, ses=None,
                   flag_print_message=True):
    """
    This is to submit one job.

    Parameters:
    ----------------
    analysis_path: str
        path to the `analysis` folder. One attribute in class `BABS`
    type_session: str
        multi-ses or single-ses
    sub: str
        subject id
    ses: str or None
        session id. For type-session == "single-ses", this is None
    flag_print_message: bool
        to print a message (True) or not (False)

    Returns:
    ------------------
    job_id: int
        the int version of ID of the submitted job.
    job_id_str: str
        the string version of ID of the submitted job.
    log_filename: str
        log filename of this job.
        Example: 'qsi_sub-01_ses-A.*<jobid>'; user needs to replace '*' with 'o', 'e', etc

    Notes:
    -----------------
    see `Container.generate_job_submit_template()`
    for details about template yaml file.
    """

    # Load the job submission template:
    #   details of this template yaml file: see `Container.generate_job_submit_template()`
    template_yaml_path = op.join(analysis_path, "code", "submit_job_template.yaml")
    with open(template_yaml_path, "r") as f:
        templates = yaml.load(f, Loader=yaml.FullLoader)
    f.close()
    # sections in this template yaml file:
    cmd_template = templates["cmd_template"]
    job_name_template = templates["job_name_template"]

    if type_session == "single-ses":
        cmd = cmd_template.replace("${sub_id}", sub)
        to_print = "Job for " + sub
        job_name = job_name_template.replace("${sub_id}", sub)
    else:   # multi-ses
        cmd = cmd_template.replace("${sub_id}", sub).replace("${ses_id}", ses)
        to_print = "Job for " + sub + ", " + ses
        job_name = job_name_template.replace("${sub_id}", sub).replace("${ses_id}", ses)
    # print(cmd)

    # run the command, get the job id:
    proc_cmd = subprocess.run(cmd.split(),   # separate by space
                              cwd=analysis_path,
                              stdout=subprocess.PIPE)
    proc_cmd.check_returncode()
    msg = proc_cmd.stdout.decode('utf-8')
    # ^^ e.g., on cubic: Your job 2275903 ("test.sh") has been submitted
    job_id_str = msg.split()[2]   # <- NOTE: this is HARD-CODED!
    job_id = int(job_id_str)

    # log filename:
    log_filename = job_name + ".*" + job_id_str

    to_print += " has been submitted (job ID: " + job_id_str + ")."
    if flag_print_message:
        print(to_print)

    return job_id, job_id_str, log_filename


def submit_one_test_job(analysis_path, flag_print_message=True):
    """
    This is to submit one *test* job.
    This is used by `babs-check-setup`.

    Parameters:
    ----------------
    analysis_path: str
        path to the `analysis` folder. One attribute in class `BABS`
    flag_print_message: bool
        to print a message (True) or not (False)

    Returns:
    -----------
    job_id: int
        the int version of ID of the submitted job.
    job_id_str: str
        the string version of ID of the submitted job.
    log_filename: str
        log filename of this job.
        Example: 'qsi_sub-01_ses-A.*<jobid>'; user needs to replace '*' with 'o', 'e', etc

    Notes:
    -----------------
    see `Container.generate_test_job_submit_template()`
    for details about template yaml file.
    """
    # Load the job submission template:
    #   details of this template yaml file: see `Container.generate_test_job_submit_template()`
    template_yaml_path = op.join(analysis_path, "code/check_setup",
                                 "submit_test_job_template.yaml")
    with open(template_yaml_path, "r") as f:
        templates = yaml.load(f, Loader=yaml.FullLoader)
    f.close()
    # sections in this template yaml file:
    cmd = templates["cmd_template"]
    job_name = templates["job_name_template"]

    to_print = "Test job"

    # run the command, get the job id:
    proc_cmd = subprocess.run(cmd.split(),   # separate by space
                              cwd=analysis_path,
                              stdout=subprocess.PIPE)

    proc_cmd.check_returncode()
    msg = proc_cmd.stdout.decode('utf-8')
    # ^^ e.g., on cubic: Your job 2275903 ("test.sh") has been submitted
    job_id_str = msg.split()[2]   # <- NOTE: this is HARD-CODED!
    job_id = int(job_id_str)

    # log filename:
    log_filename = job_name + ".*" + job_id_str

    to_print += " has been submitted (job ID: " + job_id_str + ")."
    if flag_print_message:
        print(to_print)

    return job_id, job_id_str, log_filename


def create_job_status_csv(babs):
    """
    This is to create a CSV file of `job_status`.
    This should be used by `babs-submit` and `babs-status`.

    Parameters:
    ------------
    babs: class `BABS`
        information about a BABS project.
    """

    if op.exists(babs.job_status_path_abs) is False:
        # Generate the table:
        # read the subject list as a panda df:
        df_sub = pd.read_csv(babs.list_sub_path_abs)
        df_job = df_sub.copy()    # deep copy of pandas df

        # add columns:
        df_job["has_submitted"] = False
        df_job["job_id"] = -1    # int
        df_job["job_state_category"] = np.nan
        df_job["job_state_code"] = np.nan
        df_job["duration"] = np.nan
        df_job["is_done"] = False   # = has branch in output_ria
        # df_job["echo_success"] = np.nan   # echoed success in log file; # TODO
        # # if ^^ is False, but `is_done` is True, did not successfully clean the space
        df_job["is_failed"] = np.nan
        df_job["log_filename"] = np.nan
        df_job["last_line_stdout_file"] = np.nan
        df_job["alert_message"] = np.nan
        df_job["job_account"] = np.nan

        # TODO: add different kinds of error

        # These `NaN` will be saved as empty strings (i.e., nothing between two ",")
        #   but when pandas read this csv, the NaN will show up in the df

        # Save the df as csv file, using lock:
        lock_path = babs.job_status_path_abs + ".lock"
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):
                df_job.to_csv(babs.job_status_path_abs, index=False)
        except Timeout:   # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print("Another instance of this application currently holds the lock.")


def read_job_status_csv(csv_path):
    """
    This is to read the CSV file of `job_status`.

    Parameters:
    ------------
    csv_path: str
        path to the `job_status.csv`

    Returns:
    -----------
    df: pandas dataframe
        loaded dataframe
    """
    df = pd.read_csv(csv_path,
                     dtype={"job_id": 'int',
                            'has_submitted': 'bool',
                            'is_done': 'bool'
                            })
    return df

def report_job_status(df, analysis_path, config_msg_alert):
    """
    This is to report the job status
    based on the dataframe loaded from `job_status.csv`.

    Parameters:
    -------------
    df: pandas dataframe
        loaded dataframe from `job_status.csv`
    analysis_path: str
        Path to the analysis folder.
        This is used to generate the folder of log files
    config_msg_alert: dict or None
        From `get_config_msg_alert()`
        This is used to determine if to report `alert_message` column
    """

    from .constants import MSG_NO_ALERT_IN_LOGS

    print('\nJob status:')

    total_jobs = df.shape[0]
    print('There are in total of ' + str(total_jobs) + ' jobs to complete.')

    total_has_submitted = int(df["has_submitted"].sum())
    print(str(total_has_submitted) + " job(s) have been submitted; "
          + str(total_jobs - total_has_submitted) + " job(s) haven't been submitted.")

    if total_has_submitted > 0:    # there is at least one job submitted
        total_is_done = int(df["is_done"].sum())
        print("Among submitted jobs,")
        print(str(total_is_done) + ' job(s) are successfully finished;')

        if total_is_done == total_jobs:
            print("All jobs are completed!")
        else:
            total_pending = int((df['job_state_category'] == 'pending').sum())
            print(str(total_pending) + ' job(s) are pending;')

            total_pending = int((df['job_state_category'] == 'running').sum())
            print(str(total_pending) + ' job(s) are running;')

            # TODO: add stalled one

            total_is_failed = int(df["is_failed"].sum())
            print(str(total_is_failed) + ' job(s) are failed.')

            # if there is job failed: print more info by categorizing msg:
            if total_is_failed > 0:
                if config_msg_alert is not None:
                    print("\nAmong all failed job(s):")
                # get the list of jobs that 'is_failed=True':
                list_index_job_failed = df.index[df["is_failed"] == True].tolist()
                # ^^ notice that df["is_failed"] contains np.nan, so can only get in this way

                # summarize based on `alert_message` column:

                all_alert_message = df["alert_message"][list_index_job_failed].tolist()
                unique_list_alert_message = list(set(all_alert_message))
                # unique_list_alert_message.sort()   # sort and update the list itself
                # TODO: before `.sort()` ^^, change `np.nan` to string 'nan'!

                if config_msg_alert is not None:
                    for unique_alert_msg in unique_list_alert_message:
                        # count:
                        temp_count = all_alert_message.count(unique_alert_msg)
                        print(str(temp_count) + " job(s) have alert message: '"
                              + str(unique_alert_msg) + "';")

                # if there is 'no_alert' in 'alert_message', check 'job_account' column:
                if MSG_NO_ALERT_IN_LOGS in unique_list_alert_message:
                    list_index_job_failed_no_alert = \
                        (df["is_failed"] == True) & (df["alert_message"] == MSG_NO_ALERT_IN_LOGS)

                    # because there could be 'np.nan' in the df, and pd.series -> tolist()
                    #   becomes [nan] which is not str(np.nan) or np.nan..., i.e., not detectable,
                    #   so we need to check that first...
                    pdseries = df["job_account"][list_index_job_failed_no_alert]
                    # check if all selected are np.nan:
                    if all(pd.isna(pdseries)):
                        # if so, 'job_account' was not applied yet:
                        print("\nFor the failed job(s) that don't have alert message in log files,"
                              + " you may use `--job-account` to get more information"
                              + " about why they are failed."
                              + " Note that with `--job-account`, `babs-status` may take longer time.")
                    else:
                        all_job_account = pdseries.tolist()
                        # ^^ only limit to jobs failed & no alert message in log files
                        unique_list_job_account = list(set(all_job_account))
                        # unique_list_job_account.sort()   # sort and update the list itself
                        # TODO: before `.sort()` ^^, change `np.nan` to string 'nan'!

                        print("\nAmong job(s) that are failed"
                              + " and don't have alert message in log files:")
                        for unique_job_account in unique_list_job_account:
                            # count:
                            temp_count = all_job_account.count(unique_job_account)
                            print(str(temp_count) + " job(s) have job account of: '"
                                  + str(unique_job_account) + "';")
                            # ^^ str(unique_job_account) is in case it is `np.nan`,
                            #   though should not be possible to be `np.nan`

        print("\nAll log files are located in folder: "
              + op.join(analysis_path, "logs"))

def request_all_job_status():
    """
    This is to get all jobs' status
    using e.g., `qstat` (for SGE clusters)

    Parameters:
    --------------
    TODO: add type_system!

    Returns:
    --------------
    df: pd.DataFrame
        All jobs' status, including running and pending (waiting) jobs'.
        If there is no job in the queue, df will be an empty DataFrame
        (i.e., Columns: [], Index: [])

    Notes:
    ----------------
    SGE: using package [`qstat`](https://github.com/relleums/qstat)
    """
    queue_info, job_info = qstat()
    # ^^ queue_info: dict of jobs that are running
    # ^^ job_info: dict of jobs that are pending

    # turn all jobs into a dataframe:
    df = pd.DataFrame(queue_info + job_info)

    # check if there is no job in the queue:
    if (not queue_info) & (not job_info):   # both are `[]`
        pass  # don't set the index
    else:
        df = df.set_index('JB_job_number')   # set a column as index
        # index `JB_job_number`: job ID (data type: str)
        # column `@state`: 'running' or 'pending'
        # column `state`: 'r', 'qw', etc
        # column `JAT_start_time`: start time of running
        #   e.g., '2022-12-06T14:28:43'

    return df

def request_job_status(job_id):
    """
    This is to determine the job status
    using e.g., `qstat` (for SGE clusters)
    THIS IS DEPRECATED.

    Parameters:
    --------------
    job_id: int
        The job ID.
        The data type is fixed when reading in the pd.dataframe of job status.
    TODO: add type_system!
    """
    proc_qstat = subprocess.run(
        ["qstat", "-xml"],
        stdout=subprocess.PIPE
    )
    proc_qstat.check_returncode()
    msg = proc_qstat.stdout.decode('utf-8')
    print(msg)

def calcu_runtime(start_time_str):
    """
    This is to calculate the duration time of running.

    Parameters:
    -----------------
    start_time_str: str
        The value in column 'JAT_start_time' for a specific job.
        Can be got via `df.at['2820901', 'JAT_start_time']`
        Example on CUBIC: ''

    TODO: add type_system

    Returns:
    -----------------
    duration_time_str: str
        Duration time of running.
        Format: '0:00:05.050744' (i.e., ~5sec), '2 days, 0:00:00'
    """
    # format of time in the job status requested:
    format_job_status = '%Y-%m-%dT%H:%M:%S'  # format in `qstat`
    # # format of returned duration time:
    # format_duration_time = "%Hh%Mm%Ss"  # '0h0m0s'

    d_now = datetime.now()
    duration_time = d_now - datetime.strptime(start_time_str, format_job_status)
    # ^^ str(duration_time): format: '0:08:40.158985'  # first is hour
    duration_time_str = str(duration_time)
    # ^^ 'datetime.timedelta' object (`duration_time`) has no attribute 'strftime'
    #   so cannot be directly printed into desired format...

    return duration_time_str

def get_last_line(fn):
    """
    This is to get the last line of a text file, e.g., `stdout` file

    Parameters:
    --------------------
    fn: str
        path to the text file.

    Returns:
    --------------------
    last_line: str or np.nan (if the log file haven't existed yet, or no valid line yet)
        last line of the text file.
    """

    if op.exists(fn):
        with open(fn, 'r') as f:
            all_lines = f.readlines()
            if len(all_lines) > 0:    # at least one line in the file:
                last_line = all_lines[-1]
                # remove spaces at the beginning or the end; remove '\n':
                last_line = last_line.strip().replace("\n", "")
            else:
                last_line = np.nan
    else:   # e.g., `qw` pending
        last_line = np.nan

    return last_line

def get_config_msg_alert(container_config_yaml_file):
    """
    To extract the configs of alert msgs in log files.

    Parameters:
    --------------
    container_config_yaml_file: str or None
        path to the config yaml file of containers, which might includes
        a section of `alert_log_messages`

    Returns:
    ---------------
    config_msg_alert: dict or None
    """

    if container_config_yaml_file is not None:  # yaml file is provided
        with open(container_config_yaml_file) as f:
            container_config = yaml.load(f, Loader=yaml.FullLoader)

        # Check if there is section 'alert_log_messages':
        if "alert_log_messages" in container_config:
            config_msg_alert = container_config["alert_log_messages"]
            # ^^ if it's empty under `alert_log_messages`: config_msg_alert=None

            # Check if there is either 'stdout' or 'stderr' in "alert_log_messages":
            if config_msg_alert is not None:  # there is sth under "alert_log_messages":
                if ("stdout" not in config_msg_alert) & \
                   ("stderr" not in config_msg_alert):
                    # neither is included:
                    warnings.warn(
                        "Section 'alert_log_messages' is provided in `container_config_yaml_file`, but"
                        " neither 'stdout' nor 'stderr' is included in this section."
                        " So BABS won't check if there is"
                        " any alerting message in log files.")
                    config_msg_alert = None   # not useful anymore, set to None then.
            else:  # nothing under "alert_log_messages":
                warnings.warn(
                    "Section 'alert_log_messages' is provided in `container_config_yaml_file`, but"
                    " neither 'stdout' nor 'stderr' is included in this section."
                    " So BABS won't check if there is"
                    " any alerting message in log files.")
                # `config_msg_alert` is already `None`, no need to set to None
        else:
            config_msg_alert = None
            warnings.warn(
                "There is no section called 'alert_log_messages' in the provided"
                " `container_config_yaml_file`. So BABS won't check if there is"
                " any alerting message in log files.")
    else:
        config_msg_alert = None

    return config_msg_alert

def get_alert_message_in_log_files(config_msg_alert, log_fn):
    """
    This is to get any alert message in log files of a job.

    Parameters:
    -----------------
    config_msg_alert: dict or None
        section 'alert_log_messages' in container config yaml file
        that includes what alert messages to look for in log files.
    log_fn: str
        Absolute path to a job's log files. It should have `*` to be replaced with `o` or `e`
        Example: /path/to/analysis/logs/toy_sub-0000.*11111

    Returns:
    ----------------
    alert_message: str or np.nan
        If config_msg_alert is None, or log file does not exist yet,
            `alert_message` will be `np.nan`;
        if not None, `alert_message` will be a str.
            Examples:
            - if did not find: see `MSG_NO_ALERT_MESSAGE_IN_LOGS`
            - if found: "stdout file: <message>"
    if_no_alert_in_log: bool
        There is no alert message in the log files.
        When `alert_message` is `msg_no_alert`,
        or is `np.nan` (`if_valid_alert_msg=False`), this is True;
        Otherwise, any other message, this is False

    Notes:
    -----------------
    An edge case (not a bug): On cubic cluster, some info will be printed to 'stderr' file
    before 'stdout' file have any printed messages. So 'alert_message' column may say 'BABS: No alert'
    but 'last_line_stdout_file' is still 'NaN'
    """

    from .constants import MSG_NO_ALERT_IN_LOGS
    msg_no_alert = MSG_NO_ALERT_IN_LOGS
    if_valid_alert_msg = True    # by default, `alert_message` is valid (i.e., not np.nan)
    # this is to avoid check `np.isnan(alert_message)`, as `np.isnan(str)` causes error.

    if config_msg_alert is None:
        alert_message = np.nan
        if_valid_alert_msg = False
    else:
        o_fn = log_fn.replace("*", 'o')
        e_fn = log_fn.replace("*", 'e')

        if op.exists(o_fn) or op.exists(e_fn):   # either exists:
            found_message = False
            alert_message = msg_no_alert

            for key in config_msg_alert:  # as it's dict, keys cannot be duplicated
                if key == "stdout" or "stderr":
                    one_char = key[3]   # 'o' or 'e'
                    # the log file to look into:
                    fn = log_fn.replace("*", one_char)

                    if op.exists(fn):
                        with open(fn) as f:
                            # Loop across lines, from the beginning of the file:
                            for line in f:
                                # Loop across the messages for this kind of log file:
                                for message in config_msg_alert[key]:
                                    if message in line:   # found:
                                        found_message = True
                                        alert_message = key + " file: " + message
                                        # e.g., 'stdout file: <message>'
                                        break  # no need to search next message

                                if found_message:
                                    break    # no need to go to next line
                    # if the log file does not exist, probably due to pending
                    #   not to do anything

                if found_message:
                    break   # no need to go to next log file

        else:    # neither o_fn nor e_fn exists yet:
            alert_message = np.nan
            if_valid_alert_msg = False

    if (alert_message == msg_no_alert) or (not if_valid_alert_msg):
        # either no alert, or `np.nan`
        if_no_alert_in_log = True
    else:   # `alert_message`: np.nan or any other message:
        if_no_alert_in_log = False

    return alert_message, if_no_alert_in_log

def get_username():
    """
    This is to get the current username.
    This will be used for job accounting, e.g., `qacct`.

    Returns:
    -----------
    username_lowercase: str

    NOTE: only support SGE now.
    """
    proc_username = subprocess.run(
        ["whoami"],
        stdout=subprocess.PIPE
    )
    proc_username.check_returncode()
    username_lowercase = proc_username.stdout.decode('utf-8')
    username_lowercase = username_lowercase.replace("\n", "")  # remove \n

    return username_lowercase

def check_job_account(job_id_str, job_name, username_lowercase):
    """
    This is to get information for a finished job
    by calling job account command, e.g., `qacct` for SGE

    Parameters:
    ------------
    job_id_str: str
        string version of ID of the job
    job_name: str
        Name of the job
    username_lowercase: str
        username that this job was requested to run

    Returns:
    ------------
    msg_toreturn: str
        The message got from `qacct` field `failed`, if that's not 0
        - If `qacct` was successful:
            - If field 'failed' in `qacct` was not 0: use string from that field
            - If it's 0 (no error): use `msg_no_alert_qacct_failed`
        - If `qacct` was NOT successful:
            - use `msg_failed_to_call_qacct`

    Notes:
    ----------
    This can only apply to jobs that are out of the queue; but not
    jobs under qw, r, etc, or does not exist (not submitted);
    Also, the current username should be the same one as that used for job submission.
    """
    msg_no_alert_qacct_failed = "qacct: no alert message in field 'failed'"
    msg_failed_to_call_qacct = "BABS: failed to call 'qacct'"

    if_valid_qacct_failed = True   # by default, it is valid, i.e., not np.nan
    # this is to avoid check `np.isnan(<variable_name>)`, as `np.isnan(str)` causes error.

    proc_qacct = subprocess.run(
        ["qacct", "-o", username_lowercase,
         "-j", job_id_str],
        stdout=subprocess.PIPE
    )
    try:
        proc_qacct.check_returncode()
        msg = proc_qacct.stdout.decode('utf-8')
        list_qacct_failed = re.findall(r'(?:failed)(.*?)(?:\n)', msg)  # find all, return a list
        # ^^ between `failed` and `\n`
        # example output: ['      xcpsub-00000   ', '      fpsub-0000  ']
        if len(list_qacct_failed) > 1:   # more than one job were found:
            # determine which is the job we want:
            list_jobnames = re.findall(r'(?:jobname)(.*?)(?:\n)', msg)
            for i_temp, temp_jobname in enumerate(list_jobnames):
                if job_name == temp_jobname.replace(" ", ""):  # remove spaces:
                    # ^^ the job name we want to find:
                    qacct_failed = list_qacct_failed[i_temp]
                    break
        elif len(list_qacct_failed) == 1:
            qacct_failed = list_qacct_failed[0]
        else:
            warnings.warn("Error when `qacct` for job " + job_id_str
                          + ", " + job_name)
            qacct_failed = np.nan
            if_valid_qacct_failed = False
            msg_toreturn = msg_failed_to_call_qacct

        if if_valid_qacct_failed:
            # example: '       0    '
            qacct_failed = qacct_failed.strip()    # remove the spaces at the beginning and the end

            if qacct_failed != "0":   # field `failed` is not '0', i.e., was not success:
                msg_toreturn = "qacct: failed: " + qacct_failed
            else:
                msg_toreturn = msg_no_alert_qacct_failed

    except subprocess.CalledProcessError:   # if `proc_qacct.check_returncode()` failed:
        # if the job is still in queue (qw or r etc), this will throw out an error:
        #   '.... returned non-zero exit status 1.'
        warnings.warn("Error when `qacct` for job " + job_id_str
                      + ", " + job_name)
        print("Hint: check if the job is still in the queue, e.g., in state of qw, r, etc")
        print("Hint: check if the username used for submitting this job"
              + " was not current username '" + username_lowercase + "'")
        msg_toreturn = msg_failed_to_call_qacct

    return msg_toreturn

def print_versions_from_yaml(fn_yaml):
    """
    This is to go thru information in `code/check_setup/check_env.yaml` saved by `test_job.py`.
    1. check if there is anything required but not installed
    2. print out the versions for user to visually check
    This is used by `babs-check-setup`.

    Parameters:
    ----------------
    fn_yaml: str
        path to the yaml file (usually is `code/check_setup/check_env.yaml`)

    Returns:
    ------------
    flag_writable: bool
        if the workspace is writable
    flag_all_installed: bool
        if all necessary packages are installed
    """
    # Read the yaml file and print the content:
    config = read_yaml(fn_yaml)
    print("Below is the information of designated environment and temporary workspace:\n")
    # print the yaml file:
    f = open(fn_yaml, 'r')
    file_contents = f.read()
    print(file_contents)
    f.close()

    # Check if everything is as satisfied:
    if config["workspace_writable"]:   # bool; if writable:
        flag_writable = True
    else:
        flag_writable = False

    # Check all dependent packages are installed:
    flag_all_installed = True
    for key in config["version"]:
        if config["version"][key] == "not_installed":   # see `babs/template_test_job.py`
            flag_all_installed = False
            warnings.warn("This required package is not installed: " + key)

    return flag_writable, flag_all_installed

def get_git_show_ref_shasum(branch_name, the_path):
    """
    This is to get current commit's shasum by calling `git show-ref`.
    This can be used by `babs-merge`.

    Parameters:
    --------------
    branch_name: str
        string name of the branch where you want to run `git show-ref` for
    the_path: str
        path to the git (or datalad) repository

    Returns:
    -------------
    git_ref: str
        current commit's shasum of this branch in this git repo
    msg: str
        the string got by `git show-ref`, before split by space and '\n'.
    Notes:
    -------
    bash version would be:
    `git show-ref ${git_default_branchname} | cut -d ' ' -f1 | head -n 1`
    Here, `cut` means split, `-f1` is to get the first split in each element in the list;
    `head -n 1` is to get the first element in the list
    """

    proc_git_show_ref = subprocess.run(
        ["git", "show-ref", branch_name],
        cwd=the_path,
        stdout=subprocess.PIPE)
    proc_git_show_ref.check_returncode()
    msg = proc_git_show_ref.stdout.decode('utf-8')
    # `msg.split()`:    # split by space and '\n'
    #   e.g. for default branch (main or master):
    #   ['xxxxxx', 'refs/heads/master', 'xxxxx', 'refs/remotes/origin/master']
    #   usually first 'xxxxx' and second 'xxxxx' are the same
    #   for job's branch: usually there is only one line in msg, i.e.,:
    #   ['xxxx', 'refs/remotes/origin/job-0000-sub-xxxx']
    git_ref = msg.split()[0]   # take the first element

    return git_ref, msg


def ceildiv(a, b):
    """
    This is to calculate the ceiling of division of a/b.
    ref: https://stackoverflow.com/questions/14822184/...
      ...is-there-a-ceiling-equivalent-of-operator-in-python
    """
    return -(a // -b)
