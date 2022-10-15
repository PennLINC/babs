""" Utils and helper functions """

import os
import os.path as op
import pkg_resources
#from ruamel.yaml import YAML
import yaml


def get_datalad_version():
    return pkg_resources.get_distribution("datalad").version


def get_immediate_subdirectories(a_dir):
    return [
        name for name in os.listdir(a_dir) if os.path.isdir(os.path.join(a_dir, name))
    ]


def check_validity_input_dataset(input_ds_path, type_session="single-ses"):
    """
    Check if the input dataset is valid.
    * if it's multi-ses: subject + session should both appear
    * if it's single-ses: there should be sub folder, but no ses folder

    Parameters:
    ------------------
    input_ds_path: str
        path to the input dataset. It should be the one after it's cloned to `analysis` folder
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

    is_valid_sublevel = False

    list_subs = get_immediate_subdirectories(input_ds_path)
    for sub_temp in list_subs:   # if one of the folder starts with "sub-", then it's fine
        if sub_temp[0:4] == "sub-":
            is_valid_sublevel = True
            break
    if not is_valid_sublevel:
        raise Exception(
            "There is no `sub-*` folder in this input dataset: " + input_ds_path
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
                    "There is no `ses-*` folder in subject folder " + sub_temp
                )


def validate_type_session(type_session):

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
        print("`type_session = " + type_session + "` is not allowed!")

    return type_session


def read_container_config_yaml(container_config_yaml_file):

    with open(container_config_yaml_file) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        # ^^ config is a dict; elements can be accessed by `config["key"]["sub-key"]`
    f.close()

    return config


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


def generate_cmd_singularityRun_from_config(config):
    """
    This is to generate command (in strings) of singularity run
    from config read from container config yaml file.

    Parameters:
    ------------
    config: dictionary
        got from `read_container_config_yaml()`

    Returns:
    ---------
    cmd: str
        It's part of the singularity run command; it is generated
        based on section `babs_singularity_run` in the yaml file.
    """

    # human readable: (just like appearance in a yaml file;
    # print(yaml.dump(config["babs_singularity_run"], sort_keys=False))

    # not very human readable way, if nested structure:
    # for key, value in config.items():
    #     print(key + " : " + str(value))

    cmd = ""
    is_first_flag = True

    # example key: "-w", "--n_cpus"
    # example value: "", "xxx", Null (placeholder)
    for key, value in config["babs_singularity_run"].items():
        # print(key + ": " + str(value))

        if not is_first_flag:
            # if it's not the first flag, not to add "\"
            cmd += " \ "

        if value == "":   # a flag, without value
            cmd += "\n\t" + str(key)
        else:  # a flag with value
            # check if it is a placeholder which needs to be replaced:
            if str(value)[:6] == "$BABS_":
                replaced = replace_placeholder_from_config(value)
                cmd += "\n\t" + str(key) + " " + str(replaced)

            elif value is None:    # if entered `Null` or `NULL` without quotes
                cmd += "\n\t" + str(key)
            elif value in ["Null", "NULL"]:  # "Null" or "NULL" w/ quotes, i.e., as strings
                cmd += "\n\t" + str(key)

            # there is no placeholder to deal with:
            else:
                cmd += "\n\t" + str(key) + " " + str(value)

        is_first_flag = False

        # print(cmd)

    # example of access one slot:
    # config["babs_singularity_run"]["n_cpus"]

    # print(cmd)
    return (cmd)


# adding zip filename:
    # if value != '':
    #     raise Exception("Invalid element under `one_dash`: " + str(key) + ": " + str(value) +
    #                     "\n" + "The value should be empty '', instead of " + str(value))
    #     # tested: '' or "" is the same to pyyaml


def generate_cmd_zipping_from_config(config, type_session, output_foldername="outputs"):
    """
    This is to generate bash command to zip BIDS App outputs.
    Parameters:
    ------------
    config: dictionary
        got from `read_container_config_yaml()`.
    type_session: str
        "multi-ses" or "single-ses"
    output_foldername: str
        the foldername of the outputs of BIDS App; default is "outputs".

    Returns:
    ---------
    cmd: str
        It's part of the `<containerName_zip.sh>`; it is generated
        based on section `babs_zip_foldername` in the yaml file.
    """

    # cd to output folder:
    cmd = "cd " + output_foldername + "\n"

    # 7z:
    if type_session == "multi-ses":
        str_sesid = "_${sesid}"
    else:
        str_sesid = ""

    for zipname in config["babs_zip_foldername"]:  # each element is a foldername to be zipped
        cmd += "7z a ../${subid}" + str_sesid + "_" + zipname + ".zip" + " " + zipname + "\n"
        # e.g., 7z a ../${subid}_${sesid}_fmriprep.zip fmriprep  # this is multi-ses

    # return to original dir:
    cmd += "cd ..\n"

    return cmd
