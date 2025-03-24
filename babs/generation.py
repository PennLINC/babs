"""Functions for generating scripts."""

import os
import warnings

from jinja2 import Environment, PackageLoader

from babs.dataset import to_datalad_run_string
from babs.utils import replace_placeholder_from_config


def generate_cmd_singularityRun_from_config(config, input_ds):
    """
    This is to generate command (in strings) of singularity run
    from config read from container config yaml file.

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`
    input_ds: class `InputDatasets`
        input dataset(s) information
    Returns:
    ---------
    cmd: str
        It's part of the singularity run command; it is generated
        based on section `bids_app_args` in the yaml file.
    subject_selection_flag: str
        It's part of the singularity run command; it's the command-line flag
        used to specify the subject(s) to be processed by the BIDS app.
    flag_fs_license: True or False
        Whether FreeSurfer's license will be used.
        This is determined by checking if there is argument called `--fs-license-file`
        If so, the license file will be bound into and used by the container
    path_fs_license: None or str
        Path to the FreeSurfer license. This is provided by the user in `--fs-license-file`.
    singuRun_input_dir: None or str
        The positional argument of input dataset path in `singularity run`
    """
    from .constants import PATH_FS_LICENSE_IN_CONTAINER

    cmd = ''
    # is_first_flag = True
    flag_fs_license = False
    path_fs_license = None
    singuRun_input_dir = None

    # re: positional argu `$INPUT_PATH`:
    if input_ds.num_ds > 1:  # more than 1 input dataset:
        # check if `$INPUT_PATH` is one of the keys (must):
        if '$INPUT_PATH' not in config['bids_app_args']:
            raise Exception(
                "The key '$INPUT_PATH' is expected in section `bids_app_args`"
                ' in `container_config`, because there are more than'
                ' one input dataset!'
            )
    else:  # only 1 input dataset:
        # check if the path is consistent with the name of the only input ds's name:
        if '$INPUT_PATH' in config['bids_app_args']:
            expected_temp = 'inputs/data/' + input_ds.df['name'][0]
            if config['bids_app_args']['$INPUT_PATH'] != expected_temp:
                raise Exception(
                    "As there is only one input dataset, the value of '$INPUT_PATH'"
                    ' in section `bids_app_args`'
                    ' in `container_config` should be'
                    " '" + expected_temp + "'; You can also choose"
                    " not to specify '$INPUT_PATH'."
                )

    # example key: "-w", "--n_cpus"
    # example value: "", "xxx", Null (placeholder)
    subject_selection_flag = None
    for key, value in config['bids_app_args'].items():
        # print(key + ": " + str(value))

        if key == '$INPUT_PATH':  # placeholder
            #   if not, warning....
            if value[-1] == '/':
                value = value[:-1]  # remove the unnecessary forward slash at the end

            # sanity check that `value` should match with one of input ds's `path_data_rel`
            if value not in list(input_ds.df['path_data_rel']):  # after unzip, if needed
                warnings.warn(
                    "'" + value + "' specified after $INPUT_PATH"
                    ' (in section `bids_app_args`'
                    ' in `container_config`), does not'
                    " match with any dataset's current path."
                    ' This may cause error when running the BIDS App.',
                    stacklevel=2,
                )

            singuRun_input_dir = value
            # ^^ no matter one or more input dataset(s)
            # and not add to the flag cmd

        # Check if FreeSurfer license will be used:
        elif key == '--fs-license-file':
            flag_fs_license = True
            path_fs_license = value  # the provided value is the path to the FS license
            # sanity check: `path_fs_license` exists:
            if os.path.exists(path_fs_license) is False:
                # raise a warning, instead of an error
                #   so that pytest using example yaml files will always pass
                #   regardless of the path provided in the yaml file
                warnings.warn(
                    'Path to FreeSurfer license provided in `--fs-license-file`'
                    " in container's configuration YAML file"
                    " does NOT exist! The path provided: '" + path_fs_license + "'.",
                    stacklevel=2,
                )

            # if alright: Now use the path within the container:
            cmd += ' \\' + '\n\t' + str(key) + ' ' + PATH_FS_LICENSE_IN_CONTAINER
            # ^^ the 'license.txt' will be bound to above path.

        elif key == '$SUBJECT_SELECTION_FLAG':
            subject_selection_flag = value

        else:  # check on values:
            if value == '':  # a flag, without value
                cmd += ' \\' + '\n\t' + str(key)
            else:  # a flag with value
                # check if it is a placeholder which needs to be replaced:
                # e.g., `$BABS_TMPDIR`
                if str(value)[:6] == '$BABS_':
                    replaced = replace_placeholder_from_config(value)
                    cmd += ' \\' + '\n\t' + str(key) + ' ' + str(replaced)

                elif value is None:  # if entered `Null` or `NULL` without quotes
                    cmd += ' \\' + '\n\t' + str(key)
                elif value in [
                    'Null',
                    'NULL',
                ]:  # "Null" or "NULL" w/ quotes, i.e., as strings
                    cmd += ' \\' + '\n\t' + str(key)

                # there is no placeholder to deal with:
                else:
                    cmd += ' \\' + '\n\t' + str(key) + ' ' + str(value)

    # Ensure that subject_selection_flag is not None before returning
    if subject_selection_flag is None:
        subject_selection_flag = '--participant-label'
        print(
            "'$SUBJECT_SELECTION_FLAG' not found in `bids_app_args` section of the YAML file. "
            'Using `--participant-label` as the default subject selection flag.'
        )

    # Finalize `singuRun_input_dir`:
    if singuRun_input_dir is None:
        # now, it must be only one input dataset, and user did not provide `$INPUT_PATH` key:
        assert input_ds.num_ds == 1
        singuRun_input_dir = input_ds.df['path_data_rel'][0]
        # ^^ path to data (if zipped ds: after unzipping)

    return (
        cmd,
        subject_selection_flag,
        flag_fs_license,
        path_fs_license,
        singuRun_input_dir,
    )


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
    env_var_value: str
        The value of the env variable `env_var_name`
    env_var_value_in_container: str
        The env var value used in container;
        e.g., "/SGLR/TEMPLATEFLOW_HOME"
    """

    # Generate argument `--env` in `singularity run`:
    env_var_value_in_container = '/SGLR/' + env_var_name

    # Get env var's value, to be used for binding `-B` in `singularity run`:
    env_var_value = os.getenv(env_var_name)

    # If it's templateflow:
    if env_var_name == 'TEMPLATEFLOW_HOME':
        if env_var_value is None:
            warnings.warn(
                'Usually BIDS App depends on TemplateFlow,'
                ' but environment variable `TEMPLATEFLOW_HOME` was not set up.'
                ' Therefore, BABS will not bind its directory'
                ' or inject this environment variable into the container'
                ' when running the container. This may cause errors.',
                stacklevel=2,
            )

    return env_var_value, env_var_value_in_container


def generate_cmd_zipping_from_config(dict_zip_foldernames, processing_level):
    """
    This is to generate bash command to zip BIDS App outputs.

    Parameters:
    ------------
    dict_zip_foldernames: dictionary
        `config["zip_foldernames"]` w/ placeholder key/value pair removed.
        got from `get_info_zip_foldernames()`.
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis

    Returns:
    ---------
    cmd: str
        It's part of the `<containerName_zip.sh>`; it is generated
        based on section `zip_foldernames` in the yaml file.
    """

    from .constants import OUTPUT_MAIN_FOLDERNAME

    # cd to output folder:
    cmd = 'cd ' + OUTPUT_MAIN_FOLDERNAME + '\n'

    # 7z:
    if processing_level == 'session':
        str_sesid = '_${sesid}'
    else:
        str_sesid = ''

    # start to generate 7z commands:
    value_temp = ''
    temp = 0
    for key, value in dict_zip_foldernames.items():
        # each key is a foldername to be zipped;
        # each value is the version string;
        temp = temp + 1
        if (temp != 1) & (value_temp != value):  # not matching last value
            warnings.warn(
                'In section `zip_foldernames` in `container_config`: \n'
                "The version string of '" + key + "': '" + value + "'"
                ' does not match with the last version string; '
                'we suggest using the same version string across all foldernames.',
                stacklevel=2,
            )
        value_temp = value

        cmd += '7z a ../${subid}' + str_sesid + '_' + key + '-' + value + '.zip' + ' ' + key + '\n'
        # e.g., 7z a ../${subid}_${sesid}_fmriprep-0-0-0.zip fmriprep  # this is session

    # return to original dir:
    cmd += 'cd ..\n'

    return cmd


def generate_cmd_filterfile(container_name):
    """
    Generate the command to create a filter file for BIDS App.

    Parameters:
    ------------
    container_name: str
        Name of the container (e.g., 'fmriprep', 'qsiprep')

    Returns:
    ------------
    str
        Command to create the filter file
    """
    from jinja2 import Environment, PackageLoader

    # Create Jinja environment
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )

    # Load the template
    template = env.get_template('filter_file.sh.jinja2')

    # Render the template
    return template.render(container_name=container_name)


def generate_cmd_unzip_inputds(input_ds, processing_level):
    """
    This is to generate command in `<containerName>_zip.sh` to unzip
    a specific input dataset if needed.

    Parameters
    ----------
    input_ds: class `InputDatasets`
        information about input dataset(s)
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis

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

    cmd = ''

    if True in list(input_ds.df['is_zipped']):
        # print("there is zipped dataset to be unzipped.")
        cmd += '\nwd=${PWD}'

    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df['is_zipped'][i_ds] is True:  # zipped ds
            cmd += '\ncd ' + input_ds.df['path_now_rel'][i_ds]

            # Way #1: directly use the argument in `<container>_zip.sh`, e.g., ${FREESURFER_ZIP}
            # -----------------------------------------------------------------------------------
            #   basically getting the zipfilename will be done in `participant_job.sh` by bash
            cmd += '\n7z x `basename ${' + input_ds.df['name'][i_ds].upper() + '_ZIP}`'
            #   ^^ ${FREESURFER_ZIP} includes `path_now_rel` of input_ds
            #   so needs to get the basename

            cmd += '\ncd $wd\n'

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

    Notes:
    ---------
    For interpreting shell, regardless of system type,
    it will be '#!' + the value user provided.
    """
    if key == 'interpreting_shell':
        cmd = ''  # directly use the format provided in the dict
    else:
        cmd = '#'
        if system.type == 'sge':
            cmd += '$ '  # e.g., `#$ -l h_vmem=xxx`
        elif system.type == 'slurm':
            cmd += 'SBATCH '  # e.g., `#SBATCH --xxx=yyy`

    # find the key in the `system.dict`:
    if key not in system.dict:
        raise Exception(
            f"Invalid key '{key}' in section `cluster_resources`"
            ' in `container_config`; This key has not been defined'
            " in file 'dict_cluster_systems.yaml'."
        )

    # get the format:
    the_format = system.dict[key]
    # replace the placeholder "$VALUE" in the format with the real value defined by user:
    cmd += the_format.replace('$VALUE', str(value))

    return cmd


def generate_bashhead_resources(system, config):
    """
    This is to generate the directives ("head of the bash file")
    for requesting cluster resources, specifying interpreting shell, etc.

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

    cmd = ''

    # sanity check: `cluster_resources` exists:
    if 'cluster_resources' not in config:
        raise Exception('There is no section `cluster_resources` in `container_config`!')

    # generate the command for interpreting shell first:
    if 'interpreting_shell' not in config['cluster_resources']:
        warnings.warn(
            "The interpreting shell was not specified for 'participant_job.sh'."
            " This should be specified using 'interpreting_shell'"
            " under section 'cluster_resources' in container's"
            ' configuration YAML file.',
            stacklevel=2,
        )
    else:
        key = 'interpreting_shell'
        value = config['cluster_resources'][key]
        one_cmd = generate_one_bashhead_resources(system, key, value)
        cmd += one_cmd + '\n'

    # loop for other keys:
    #   for each key, call `generate_one_bashhead_resources()`:
    for key, value in config['cluster_resources'].items():
        if key == 'customized_text':
            pass  # handle this below
        elif key == 'interpreting_shell':
            pass  # has been handled - see above
        else:
            one_cmd = generate_one_bashhead_resources(system, key, value)
            cmd += one_cmd + '\n'

    if 'customized_text' in config['cluster_resources']:
        cmd += config['cluster_resources']['customized_text']
        cmd += '\n'

    return cmd


def generate_cmd_script_preamble(config):
    """
    This is to generate bash cmd based on `script_preamble`
    from the `container_config`

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`

    Returns:
    --------
    cmd: str
        It's part of the `participant_job.sh`; it is generated
        based on config yaml file.
    """

    cmd = ''

    if 'script_preamble' not in config:
        warnings.warn(
            "Did not find the section 'script_preamble'"
            ' in `container_config`.'
            ' Not to generate script preamble.',
            stacklevel=2,
        )
        # TODO: ^^ this should be changed to an error!
    else:  # there is `script_preamble`:
        # directly grab the commands in the section:
        cmd += config['script_preamble']

    return cmd


def generate_cmd_job_compute_space(config):
    """
    This is to generate bash cmd based on `job_compute_space`
    from the `container_config`

    Parameters
    ----------
    config: dictionary
        attribute `config` in class Container;
        got from `read_container_config_yaml()`

    Returns
    -------
    cmd: str
        It's part of the `participant_job.sh`; it is generated
        based on config yaml file.
    """

    cmd = ''
    # sanity check:
    if 'job_compute_space' not in config:
        raise Exception("Did not find the section 'job_compute_space'" + ' in `container_config`!')

    cmd += '\n# Change path to an ephemeral (temporary) job compute workspace:\n'
    cmd += (
        "# The path is specified according to 'job_compute_space'"
        " in container's configuration YAML file.\n"
    )
    cmd += 'cd ' + config['job_compute_space'] + '\n'

    return cmd


def generate_cmd_determine_zipfilename(input_ds, processing_level):
    """
    This is to generate bash cmd that determines the path to the zipfile of a specific
    subject (or session). This command will be used in `participant_job.sh`.
    This command should be generated after `datalad get -n <input_ds>`,
    i.e., after there is list of data in <input_ds> folder

    Parameters
    ----------
    input_ds: class InputDatasets
        information about input dataset(s)
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis

    Returns:
    --------
    cmd: str
        the bash command used in `participant_job.sh`

    Notes:
    ------
    ref: `bootstrap-fmriprep-ingressed-fs.sh`
    """

    cmd = ''

    if True in list(input_ds.df['is_zipped']):  # there is at least one dataset is zipped
        cmd += '\n# Get the zip filename of current subject (or session):\n'

    for i_ds in range(0, input_ds.num_ds):
        if input_ds.df['is_zipped'][i_ds] is True:  # is zipped:
            variable_name_zip = input_ds.df['name'][i_ds] + '_ZIP'
            variable_name_zip = variable_name_zip.upper()  # change to upper case
            cmd += f'{variable_name_zip}=$(ls ' + input_ds.df['path_now_rel'][i_ds] + '/${subid}_'
            cmd += f'{variable_name_zip}=$(ls ' + input_ds.df['path_now_rel'][i_ds] + '/${subid}_'

            if processing_level == 'session':
                cmd += '${sesid}_'

            cmd += '*' + input_ds.df['name'][i_ds] + '*.zip' + " | cut -d '@' -f 1 || true)" + '\n'
            # `cut -d '@' -f 1` means:
            #   field separator (or delimiter) is @ (`-d '@'`), and get the 1st field (`-f 1`)
            # `<command> || true` means:
            #   the bash script won't abort even if <command> fails
            #   useful when `set -e` (where any error would cause the shell to exit)

            cmd += "echo 'found " + input_ds.df['name'][i_ds] + " zipfile:'" + '\n'
            cmd += 'echo ${' + variable_name_zip + '}' + '\n'

            # check if it exists:
            cmd += 'if [ -z "${' + variable_name_zip + '}" ]; then' + '\n'
            cmd += (
                "\techo 'No input zipfile of " + input_ds.df['name'][i_ds] + ' found for ${subid}'
            )
            if processing_level == 'session':
                cmd += ' ${sesid}'
            cmd += "'" + '\n'
            cmd += '\t' + 'exit 99' + '\n'
            cmd += 'fi' + '\n'

            # sanity check: there should be only 1 matched file:
            # change into array: e.g., array=($FREESURFER_ZIP)
            cmd += 'array=($' + variable_name_zip + ')' + '\n'
            # if [ "$a" -gt "$b" ]; then
            cmd += 'if [ "${#array[@]}" -gt "1" ]; then' + '\n'
            cmd += (
                "\techo 'There is more than one input zipfile of "
                + input_ds.df['name'][i_ds]
                + ' found for ${subid}'
            )
            if processing_level == 'session':
                cmd += ' ${sesid}'
            cmd += "'" + '\n'
            cmd += '\t' + 'exit 98' + '\n'
            cmd += 'fi' + '\n'

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


def generate_cmd_datalad_run(container, input_ds, processing_level):
    """
    This is to generate the command of `datalad run`
    included in `participant_job.sh`.

    Parameters
    ----------
    container: class `Container`
        Information about the container
    input_ds: class `InputDatasets`
        Information about input dataset(s)
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis

    Returns
    -------
    cmd: str
        `datalad run`, part of the `participant_job.sh`.

    Notes:
    ----------
    Needs to quote any globs (`*`) in `-i` (or `-o`)!!
        Otherwise, after expansion by DataLad, some values might miss `-i` (or `-o`)!
    """

    # Create Jinja environment
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )

    # Load the template
    template = env.get_template('datalad_run.sh.jinja2')

    # Determine if we need to expand inputs
    flag_expand_inputs = any(not input_ds.df['is_zipped'][i_ds] for i_ds in range(input_ds.num_ds))

    # Render the template
    cmd = template.render(
        container=container,
        input_ds_string=to_datalad_run_string(input_ds.df, processing_level),
        processing_level=processing_level,
        flag_expand_inputs=flag_expand_inputs,
    )

    return cmd
