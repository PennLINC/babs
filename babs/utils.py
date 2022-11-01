""" Utils and helper functions """

import os
import os.path as op
import sys
import warnings   # built-in, no need to install
import pkg_resources
# from ruamel.yaml import YAML
import yaml
import glob
import regex

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
        based on section `babs_singularity_run` in the yaml file.
    flag_fs_license: True or False
        Whether FreeSurfer's license will be used; if so, BABS needs to copy it to workspace.
    singuRun_input_dir: None or str
        The positional argument of input dataset path in `singularity run`
    """

    # human readable: (just like appearance in a yaml file;
    # print(yaml.dump(config["babs_singularity_run"], sort_keys=False))

    # not very human readable way, if nested structure:
    # for key, value in config.items():
    #     print(key + " : " + str(value))

    cmd = ""
    # is_first_flag = True
    flag_fs_license = False
    singuRun_input_dir = None

    # re: positional argu `$INPUT_PATH`:
    if input_ds.num_ds > 1:   # more than 1 input dataset:
        # check if `$INPUT_PATH` is one of the keys (must):
        if "$INPUT_PATH" not in config["babs_singularity_run"]:
            raise Exception("The key '$INPUT_PATH' is expected in section `babs_singularity_run`"
                            + " in `container_config_yaml_file`, because there are more than"
                            + " one input dataset!")
    else:   # only 1 input dataset:
        # check if the path is consistent with the name of the only input ds's name:
        if "$INPUT_PATH" in config["babs_singularity_run"]:
            expected_temp = "inputs/data/" + input_ds.df["name"][0]
            if config["babs_singularity_run"]["$INPUT_PATH"] != expected_temp:
                raise Exception("As there is only one input dataset, the value of '$INPUT_PATH'"
                                + " in section `babs_singularity_run`"
                                + " in `container_config_yaml_file` should be"
                                + " '" + expected_temp + "'; You can also choose"
                                + " not to specify '$INPUT_PATH'.")

    # example key: "-w", "--n_cpus"
    # example value: "", "xxx", Null (placeholder)
    for key, value in config["babs_singularity_run"].items():
        # print(key + ": " + str(value))

        if key == "$INPUT_PATH":  # placeholder

            #   if not, warning....
            if value[-1] == "/":
                value = value[:-1]   # remove the unnecessary forward slash at the end

            # sanity check that `value` should match with one of input ds's `path_data_rel`
            if value not in list(input_ds.df["path_data_rel"]):  # after unzip, if needed
                warnings.warn("'" + value + "' specified after $INPUT_PATH"
                              + " (in section `babs_singularity_run`"
                              + " in `container_config_yaml_file`), does not"
                                + " match with any dataset's current path."
                                + " This may cause error when running the BIDS App.")

            singuRun_input_dir = value
            # ^^ no matter one or more input dataset(s)
            # and not add to the flag cmd

        else:   # check on values:
            if value == "":   # a flag, without value
                cmd += " \\" + "\n\t" + str(key)
            else:  # a flag with value
                # check if it is a placeholder which needs to be replaced:
                if str(value)[:6] == "$BABS_":
                    replaced = replace_placeholder_from_config(value)
                    cmd += " \\" + "\n\t" + str(key) + " " + str(replaced)
                elif str(value) == "$FREESURFER_LICENSE":
                    replaced = replace_placeholder_from_config(value)
                    flag_fs_license = True
                    cmd += " \\" + "\n\t" + str(key) + " " + str(replaced)

                elif value is None:    # if entered `Null` or `NULL` without quotes
                    cmd += " \\" + "\n\t" + str(key)
                elif value in ["Null", "NULL"]:  # "Null" or "NULL" w/ quotes, i.e., as strings
                    cmd += " \\" + "\n\t" + str(key)

                # there is no placeholder to deal with:
                else:
                    cmd += " \\" + "\n\t" + str(key) + " " + str(value)

        # is_first_flag = False

        # print(cmd)

    if singuRun_input_dir is None:
        # now, it must be only one input dataset, and user did not provide `$INPUT_PATH` key:
        assert input_ds.num_ds == 1
        singuRun_input_dir = input_ds.df["path_data_rel"][0]
        # ^^ path to data (if zipped ds: after unzipping)

    # example of access one slot:
    # config["babs_singularity_run"]["n_cpus"]

    # print(cmd)
    return cmd, flag_fs_license, singuRun_input_dir


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
        attribute `config` in class Container;
        got from `read_container_config_yaml()`
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
        warnings.warn("Usually BIDS App depends on TemplateFlow,"
                      + " but environment variable `TEMPLATEFLOW_HOME` was not set up."
                      + " Therefore, BABS will not export it or bind its directory"
                      + " when running the container. This may cause errors.")

    cmd += "\n"
    return cmd, templateflow_home, singularityenv_templateflow_home


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
                              "The version string of '" + key + "': '" + value + "'"
                              + " does not match with the last version string; "
                              + "we suggest using the same version string across all foldernames.")
            value_temp = value

            cmd += "7z a ../${subid}" + str_sesid + "_" + \
                key + "-" + value + ".zip" + " " + key + "\n"
            # e.g., 7z a ../${subid}_${sesid}_fmriprep-0-0-0.zip fmriprep  # this is multi-ses

    else:    # the yaml file does not have the section `babs_zip_foldername`:
        raise Exception("The `container_config_yaml_file` does not contain"
                        + " the section `babs_zip_foldername`. Please add this section!")

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
    i_ds: int
        the i-th dataset (starting from 0) that needs to be unzipped

    Returns:
    ---------
    cmd: str
        It's part of the `<containerName_zip.sh>`.
        Examples #1:
            wd=${PWD}
            cd inputs/data
            7z x ${subid}_${sesid}_fmriprep-20.2.3.zip
            cd $wd
        Example #2:
            wd=${PWD}
            cd inputs/data/freesurfer
            7z x `basename ${freesurfer_zip}`
            cd $wd

    """

    cmd = ""

    if True in list(input_ds.df["is_zipped"]):
        # print("there is zipped dataset to be unzipped.")
        cmd += "\nwd=${PWD}"

    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df["is_zipped"][i_ds] is True:  # zipped ds
            cmd += "\ncd " + input_ds.df["path_now_rel"][i_ds]

            # get the zip filename:
            if type_session == "multi-ses":
                list_zipfiles = \
                    glob.glob(op.join(input_ds.df["path_now_abs"][i_ds],
                                      "sub-*_ses-*_" + input_ds.df["name"][i_ds] + "*.zip"))
                if len(list_zipfiles) == 0:
                    raise Exception("In zipped input dataset '" + input_ds.df["name"][i_ds] + "',"
                                    + " the zip file(s) does not follow the pattern of "
                                    + "'sub-*_ses-*_'" + input_ds.df["name"][i_ds] + "*.zip")
            elif type_session == "single-ses":
                list_zipfiles = \
                    glob.glob(op.join(input_ds.df["path_now_abs"][i_ds],
                                      "sub-*_" + input_ds.df["name"][i_ds] + "*.zip"))
                if len(list_zipfiles) == 0:
                    raise Exception("In zipped input dataset '" + input_ds.df["name"][i_ds] + "',"
                                    + " the zip file(s) does not follow the pattern of "
                                    + "'sub-*_'" + input_ds.df["name"][i_ds] + "*.zip")
            else:
                raise Exception("invalid `type_session`: " + type_session)

            # assume all the zip filenames are regular, so only check out the first one:

            temp_filename = op.basename(list_zipfiles[0])
            temp_regex = regex.search(input_ds.df["name"][i_ds] + '(.*)' + '.zip',
                                      temp_filename)
            temp_pattern = temp_regex.group(0)   # e.g., "fmriprep-0.0.0.zip"
            # ^^ .group(1) will be "-0.0.0"
            if type_session == "multi-ses":
                cmd += "\n7z x ${subid}_${sesid}_" + \
                    temp_pattern
            elif type_session == "single-ses":
                cmd += "\n7z x ${subid}_" + temp_pattern

            cmd += "\ncd $wd\n"

    return cmd


def generate_one_bashhead_resources(system, key, value):
    """
    This is to generate one command in the head of the bash file
    for requesting cluster resources.

    Parameters:
    ------------
    system: class `System`
        information about cluster managemenet system
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
        information about cluster managemenet system
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

def generate_cmd_determine_zipfilename(input_ds, type_session):
    """
    This is to generate bash cmd that determines the path to the zipfile of a specific
    subject (or session). This command will be used in `participant_job.sh`

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
        cmd += "\n# Getting the zip filename of current subject (or session):\n"

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

            # TODO: test this out: multi-ses and singl-ses...

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
            cmd += "\t" + "-i " + input_ds.df["path_now_rel"][i_ds] + "/" \
                + "*json" + " \\" + "\n"
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

    for key, value in container.config["babs_zip_foldername"].items():
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

    # TODO: finish this function!
    # TODO: test on multi-ses and single-ses data!
    # TODO: test on 1) fmriprep; 2) xcpd; 3) fmriprep_ingressed_fs

    return cmd

def get_list_sub_ses(input_ds, type_session):
    """
    This is to get the list of subjects (and sessions).

    Parameters:
    ------------
    input_ds: class `Input_ds`
        information about input dataset(s)
    type_session: str
        "multi-ses" or "single-ses"

    Returns:
    -----------
    multi-ses project: a list of subjects
    single-ses project: a dict of subjects and their sessions
    """

    # TODO: ROADMAP: for each input dataset, get a list, then get the overlapped list
    # for now, only check the first dataset

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
        if type_session == "single-ses":
            full_paths = glob.glob(input_ds.df["path_now_abs"][i_ds]
                                   + "/sub-*_" + input_ds.df["name"][i_ds] + "*.zip")
        elif type_session == "multi-ses":
            full_paths = glob.glob(input_ds.df["path_now_abs"][i_ds]
                                   + "/sub-*_ses-*" + input_ds.df["name"][i_ds] + "*.zip")
            # ^^ above pattern makes sure only gets subs who have more than one ses
        full_paths = sorted(full_paths)
        zipfilenames = [op.basename(temp) for temp in full_paths]
        subs = [temp.split('_', 3)[0] for temp in zipfilenames]
        # ^^ str.split("delimiter", <maxsplit>)[i-th_field]
        # <maxsplit> means max number of "cuts"; # of total fields = <maxsplit> + 1
        subs = sorted(list(set(subs)))   # list(set()): acts like "unique"

    # if it's multi-ses, get list of sessions for each subject:
    if type_session == "multi-ses":
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

    if type_session == "single-ses":
        return subs
    elif type_session == "multi-ses":
        return dict_sub_ses
