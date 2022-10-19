""" Utils and helper functions """

import os
import os.path as op
import warnings
import pkg_resources
# from ruamel.yaml import YAML
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
    elif value == "$FREESURFER_LICENSE":
        replaced = "code/license.txt"
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
    flag_fs_license: True or False
        Whether FreeSurfer's license will be used; if so, BABS needs to copy it to workspace.
    """

    # human readable: (just like appearance in a yaml file;
    # print(yaml.dump(config["babs_singularity_run"], sort_keys=False))

    # not very human readable way, if nested structure:
    # for key, value in config.items():
    #     print(key + " : " + str(value))

    cmd = ""
    is_first_flag = True
    flag_fs_license = False

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
            elif str(value) == "$FREESURFER_LICENSE":
                replaced = replace_placeholder_from_config(value)
                flag_fs_license = True
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
    return cmd, flag_fs_license


# adding zip filename:
    # if value != '':
    #     raise Exception("Invalid element under `one_dash`: " + str(key) + ": " + str(value) +
    #                     "\n" + "The value should be empty '', instead of " + str(value))
    #     # tested: '' or "" is the same to pyyaml


def generate_cmd_envvar(config, container_name):
    """
    This is to generate bash command to export necessary environment variables.
    Currently this only supports `templateflow_home`.
    Roadmap: customize env var (original one, and SINGULARITYENV_*) in yaml file.

    Parameters:
    ------------
    config: dictionary
        got from `read_container_config_yaml()`.
    container_name: str
        The name of the container when adding to datalad dataset.
        e.g., fmriprep-0-0-0.
        See class `Container` for more.

    Returns:
    ---------
    cmd: str
        It's part of the singularity run command; it is generated
        based on section `environment_variable` in the yaml file.
    templateflow_home: None or str
        The environment variable `TEMPLATEFLOW_HOME`.
    singularityenv_templateflow_home: None or str
        The environment variable `SINGULARITYENV_TEMPLATEFLOW_HOME`.
        Its value will be used within the container.
        Only set when `templateflow_home` is not None.
    """
    cmd = ""

    templateflow_home = None
    singularityenv_templateflow_home = None

    # Set up `templateflow_home`:
    # Why: QSIPrep, fMRIPrep, and XCP-D all need it; therefore BABS will automatically set it up.
    # How: We get it from environment variable `TEMPLATEFLOW_HOME` below.
    #      If we get it, do two actions below:
    # action 1: export;
    # action 2: bind the directory when `singularity run`
    #           ^^ this will ask `generate_bash_run_bidsapp()` to achieve

    # get `templateflow_home`:
    # check if it's set up:
    if templateflow_home is None:  # not set up yet:
        # get it from env var `TEMPLATEFLOW_HOME`:
        templateflow_home = os.getenv("TEMPLATEFLOW_HOME")

    if templateflow_home is not None:
        # action #1: add to the cmd to export:
        singularityenv_templateflow_home = "/TEMPLATEFLOW_HOME"  # within container
        # ^^ hard code it for now. ROADMAP.
        cmd += "\nexport SINGULARITYENV_TEMPLATEFLOW_HOME=" + singularityenv_templateflow_home
    else:
        # we have checked existing env var;
        # if it still does not exist, warning:
        warnings.warn("Usually BIDS App depends on TemplateFlow," +
                      " but environment variable `TEMPLATEFLOW_HOME` was not set up." +
                      " Therefore, BABS will not export it or bind its directory" +
                      " when running the container. This may cause errors.")

    cmd += "\n"
    return cmd, templateflow_home, singularityenv_templateflow_home


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

    if "babs_zip_foldername" in config:
        value_temp = ""
        temp = 0

        for key, value in config["babs_zip_foldername"].items():
            # each key is a foldername to be zipped;
            # each value is the version string;
            temp = temp + 1
            if (temp != 1) & (value_temp != value):    # not matching last value
                warnings.warn("In section `babs_zip_foldername` in `container_config_yaml_file`: \n"
                              "The version string of '" + key + "': '" + value + "'" +
                              " does not match with the last version string; " +
                              "we suggest using the same version string across all foldernames.")
            value_temp = value

            cmd += "7z a ../${subid}" + str_sesid + "_" + \
                key + "-" + value + ".zip" + " " + key + "\n"
            # e.g., 7z a ../${subid}_${sesid}_fmriprep-0-0-0.zip fmriprep  # this is multi-ses

    else:    # the yaml file does not have the section `babs_zip_foldername`:
        raise Exception("The `container_config_yaml_file` does not contain" +
                        " the section `babs_zip_foldername`. Please add this section!")

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

    cmd += "\n\n"

    return cmd
