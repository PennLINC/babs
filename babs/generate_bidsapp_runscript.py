"""Create scripts for a BABS project"""

import os.path as op
import warnings

from jinja2 import Environment, PackageLoader, StrictUndefined

from babs.utils import RUNNING_PYTEST, replace_placeholder_from_config


def generate_bidsapp_runscript(
    input_datasets,
    processing_level,
    container_name,
    relative_container_path,
    bids_app_output_dir,
    dict_zip_foldernames,
    bids_app_args=None,
    singularity_args=None,
    templateflow_home=None,
):
    """
    Generate a bash script that runs the BIDS App singularity image.

    Parameters
    ----------
    input_datasets: list of dicts
        each dict contains information of an input dataset
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    bids_app_args: list
        list of arguments to be passed to the BIDS App
    singularity_args: list
        list of arguments to be passed to the singularity image
    templateflow_home: str
        path to the templateflow home directory on local disk
    output_directory: str
        path to the output directory

    Returns
    -------
    bidsapp_run_script: str
        The contents of the bash script that runs the BIDS App singularity image.
    """

    from .constants import OUTPUT_MAIN_FOLDERNAME, PATH_FS_LICENSE_IN_CONTAINER

    # 1. check `bids_app_args` section:
    if bids_app_args is None:
        assert len(input_datasets) == 1, (
            "Section 'bids_app_args' is missing in the provided"
            ' `container_config`. As there are more than one'
            ' input dataset, you must include this section to specify'
            ' to which argument that each input dataset will go.'
        )
        # if there is only one input ds, fine:
        print("Section 'bids_app_args' was not included in the `container_config`. ")
        bids_app_args = ''  # should be empty
        flag_fs_license = False
        path_fs_license = None
        bids_app_input_dir = input_datasets[0]['unzipped_path_containing_subject_dirs']
        subject_selection_flag = '--participant-label'  # default value
    else:
        # read config from the yaml file:
        (
            bids_app_args,
            subject_selection_flag,
            flag_fs_license,
            path_fs_license,
            bids_app_input_dir,
        ) = bids_app_args_from_config(bids_app_args, input_datasets)

    # Get unzip commands for any zipped input datasets
    cmd_unzip_inputds = get_input_unzipping_cmds(input_datasets)

    # Generate zip command
    cmd_zip = get_output_zipping_cmds(dict_zip_foldernames, processing_level)

    # Render the template
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )

    template = env.get_template('bidsapp_run.sh.jinja2')
    return template.render(
        processing_level=processing_level,
        input_datasets=input_datasets,
        container_name=container_name,
        flag_filterfile=processing_level == 'session' and 'prep' in container_name.lower(),
        cmd_unzip_inputds=cmd_unzip_inputds,
        templateflow_home_on_disk=templateflow_home,
        templateflow_in_container='/SGLR/TEMPLATEFLOW_HOME',
        flag_fs_license=flag_fs_license,
        path_fs_license=path_fs_license,
        PATH_FS_LICENSE_IN_CONTAINER=PATH_FS_LICENSE_IN_CONTAINER,
        container_path_relToAnalysis=relative_container_path,
        bids_app_input_dir=bids_app_input_dir,
        bids_app_output_dir=bids_app_output_dir,
        bids_app_args=bids_app_args,
        cmd_zip=cmd_zip,
        OUTPUT_MAIN_FOLDERNAME=OUTPUT_MAIN_FOLDERNAME,
        singularity_flags=singularity_args,
        subject_selection_flag=subject_selection_flag,
    )


def get_output_zipping_cmds(dict_zip_foldernames, processing_level):
    """
    This is to generate bash command to zip BIDS App outputs.

    Parameters:
    ------------
    dict_zip_foldernames: dictionary
        `config["zip_foldernames"]` w/ placeholder key/value pair removed.
        got from `app_output_settings_from_config()`.
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis

    Returns:
    ---------
    cmd: str
        It's part of the `<containerName_zip.sh>`; it is generated
        based on section `zip_foldernames` in the yaml file.
    """
    from .constants import OUTPUT_MAIN_FOLDERNAME

    # Check for version mismatches and issue warnings
    value_temp = ''
    for i, (key, value) in enumerate(dict_zip_foldernames.items()):
        if i > 0 and value != value_temp:
            warnings.warn(
                'In section `zip_foldernames` in `container_config`: \n'
                f"The version string of '{key}': '{value}'"
                ' does not match with the last version string; '
                'we suggest using the same version string across all foldernames.',
                stacklevel=2,
            )
        value_temp = value

    # Create Jinja environment
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )

    # Load the template
    template = env.get_template('zipping.sh.jinja2')

    # Render the template
    cmd = template.render(
        output_main_folder=OUTPUT_MAIN_FOLDERNAME,
        processing_level=processing_level,
        dict_zip_foldernames=dict_zip_foldernames,
    )

    return cmd


def bids_app_args_from_config(bids_app_args, input_datasets):
    """
    This is to generate command (in strings) of singularity run
    from config read from container config yaml file.

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;
    input_datasets: list of dicts
        each dict contains information of an input dataset

    Returns:
    ---------
    cmds : list of str
        Commands (without trailing backslash) for the bids app
    subject_selection_flag: str
        It's part of the singularity run command; it's the command-line flag
        used to specify the subject(s) to be processed by the BIDS app.
    flag_fs_license: True or False
        Whether FreeSurfer's license will be used.
        This is determined by checking if there is argument called `--fs-license-file`
        If so, the license file will be bound into and used by the container
    path_fs_license: None or str
        Path to the FreeSurfer license. This is provided by the user in `--fs-license-file`.
    bids_app_input_dir: None or str
        The positional argument of input dataset path in `singularity run`
    """
    from .constants import PATH_FS_LICENSE_IN_CONTAINER

    cmds = []
    flag_fs_license = False
    path_fs_license = None
    bids_app_input_dir = None
    subject_selection_flag = None
    for key, value in bids_app_args.items():
        # Check if FreeSurfer license will be used:
        if key == '--fs-license-file':
            flag_fs_license = True
            path_fs_license = value
            if not op.exists(path_fs_license) and not RUNNING_PYTEST:
                # raise a warning, instead of an error
                #   so that pytest using example yaml files will always pass
                #   regardless of the path provided in the yaml file
                warnings.warn(
                    'Path to FreeSurfer license provided in `--fs-license-file`'
                    " in container's configuration YAML file"
                    " does NOT exist! The path provided: '" + path_fs_license + "'.",
                    stacklevel=2,
                )

            cmds.append(f'{key} {PATH_FS_LICENSE_IN_CONTAINER}')

        elif key == '$SUBJECT_SELECTION_FLAG':
            subject_selection_flag = value
        elif key == '$SESSION_SELECTION_FLAG':
            cmds.append(f'{value} $sesid')

        else:  # check on values:
            if value in ('', None, 'Null', 'NULL'):  # a flag, without value
                cmds.append(str(key))
            else:  # a flag with value
                # check if it is a placeholder which needs to be replaced:
                # e.g., `$BABS_TMPDIR`
                if value.startswith('$BABS_'):
                    value = replace_placeholder_from_config(value)

                cmds.append(f'{key} {value}')

    # Ensure that subject_selection_flag is not None before returning
    if subject_selection_flag is None:
        subject_selection_flag = '--participant-label'
        print(
            "'$SUBJECT_SELECTION_FLAG' not found in `bids_app_args` section of the YAML file. "
            'Using `--participant-label` as the default subject selection flag.'
        )

    # The input dataset is always the first one in the list
    bids_app_input_dir = input_datasets[0]['unzipped_path_containing_subject_dirs']

    return (
        cmds,
        subject_selection_flag,
        flag_fs_license,
        path_fs_license,
        bids_app_input_dir,
    )


def bids_app_args_from_config_pipeline(bids_app_args, input_datasets, processing_level):
    """
    Pipeline-specific version of bids_app_args_from_config.
    """
    from .constants import PATH_FS_LICENSE_IN_CONTAINER

    cmds = []
    flag_fs_license = False
    path_fs_license = None

    bids_app_input_dir = None
    subject_selection_flag = None
    for key, value in bids_app_args.items():
        # Check if FreeSurfer license will be used:
        if key == '--fs-license-file':
            flag_fs_license = True
            path_fs_license = value
            if not op.exists(path_fs_license) and not RUNNING_PYTEST:
                # raise a warning, instead of an error
                #   so that pytest using example yaml files will always pass
                #   regardless of the path provided in the yaml file
                warnings.warn(
                    'Path to FreeSurfer license provided in `--fs-license-file`'
                    " in container's configuration YAML file"
                    " does NOT exist! The path provided: '" + path_fs_license + "'.",
                    stacklevel=2,
                )

            cmds.append(f'{key} {PATH_FS_LICENSE_IN_CONTAINER}')

        elif key == '$SUBJECT_SELECTION_FLAG':
            subject_selection_flag = value
        elif key == '$SESSION_SELECTION_FLAG':
            # Only include session flag when processing at session level
            if processing_level == 'session':
                cmds.append(f'{value} "$sesid"')

        else:  # check on values:
            if value in ('', None, 'Null', 'NULL'):  # a flag, without value
                cmds.append(str(key))
            else:  # a flag with value
                # check if it is a placeholder which needs to be replaced:
                # e.g., `$BABS_TMPDIR`
                if value.startswith('$BABS_'):
                    value = replace_placeholder_from_config(value)

                cmds.append(f'{key} {value}')

    # Ensure that subject_selection_flag is not None before returning
    if subject_selection_flag is None:
        subject_selection_flag = '--participant-label'
        print(
            "'$SUBJECT_SELECTION_FLAG' not found in `bids_app_args` section of the YAML file. "
            'Using `--participant-label` as the default subject selection flag.'
        )

    # The input dataset is always the first one in the list
    bids_app_input_dir = input_datasets[0]['unzipped_path_containing_subject_dirs']

    return (
        cmds,
        subject_selection_flag,
        flag_fs_license,
        path_fs_license,
        bids_app_input_dir,
    )


def generate_pipeline_runscript(
    pipeline_config,
    processing_level,
    input_datasets,
    templateflow_home=None,
    final_zip_foldernames=None,
):
    """Generate a bash script that runs an ordered pipeline of BIDS Apps.

    Parameters
    ----------
    pipeline_config: list of dicts
        Ordered list of pipeline step configurations. Each step must include:
          - container_name: str
          - config: dict containing:
            - zip_foldernames: dict (optional for individual steps, handled at pipeline level)
            - bids_app_args: dict (same format as single bidsapp)
            - singularity_args: list
          - inter_step_cmds: Optional[str] bash snippet executed after step

    processing_level: {'subject', 'session'}
        Whether processing is done on a subject-wise or session-wise basis

    input_datasets: InputDatasets or list of dicts
        InputDatasets object or list of dicts containing information of input datasets

    templateflow_home: str, optional
        TEMPLATEFLOW_HOME on disk, if any, to add a bind mount

    final_zip_foldernames: dict, optional
        Top-level zip_foldernames configuration for final output zipping.
        If None, falls back to last step's config for backward compatibility.

    Returns
    -------
    str
        The rendered bash script content
    """

    from .constants import OUTPUT_MAIN_FOLDERNAME, PATH_FS_LICENSE_IN_CONTAINER
    from .utils import app_output_settings_from_config

    # Handle both InputDatasets objects and lists of dicts for consistency
    if hasattr(input_datasets, 'as_records'):
        # It's an InputDatasets object, convert to records
        input_datasets = input_datasets.as_records()

    # Process each step similar to how generate_bidsapp_runscript processes single steps
    processed_steps = []
    for i, step in enumerate(pipeline_config):
        container_name = step['container_name']
        step_config = step['config']

        # Process bids_app_args similar to generate_bidsapp_runscript
        bids_app_args = step_config.get('bids_app_args')
        if bids_app_args is None:
            assert len(input_datasets) == 1, (
                "Section 'bids_app_args' is missing in the provided"
                ' pipeline step config. As there are more than one'
                ' input dataset, you must include this section to specify'
                ' to which argument that each input dataset will go.'
            )
            print(f"Section 'bids_app_args' was not included in step {i + 1} config. ")
            bids_app_args = ''  # should be empty
            flag_fs_license = False
            path_fs_license = None
            bids_app_input_dir = input_datasets[0]['unzipped_path_containing_subject_dirs']
            subject_selection_flag = '--participant-label'  # default value
        else:
            # read config from the yaml file:
            (
                bids_app_args,
                subject_selection_flag,
                flag_fs_license,
                path_fs_license,
                bids_app_input_dir,
            ) = bids_app_args_from_config_pipeline(bids_app_args, input_datasets, processing_level)

        # Determine if this step needs filter file (any 'prep' step for session-level processing)
        flag_filterfile = processing_level == 'session' and 'prep' in container_name.lower()

        # Determine output directory consistent with single-app behavior
        # Special handling: nordic modifies BIDS in-place
        if 'nordic' in container_name.lower():
            bids_app_output_dir = bids_app_input_dir
        else:
            # For non-nordic steps, check if step has zip_foldernames
            if 'zip_foldernames' in step_config:
                _, bids_app_output_dir = app_output_settings_from_config(step_config)
            else:
                # Step doesn't have zip_foldernames, use default
                bids_app_output_dir = OUTPUT_MAIN_FOLDERNAME

        # For step 0, use the original input; subsequent steps chain from previous output
        step_input_dir = (
            bids_app_input_dir if i == 0 else processed_steps[i - 1]['bids_app_output_dir']
        )

        processed_step = {
            'container_name': container_name,
            'container_path_relToAnalysis': (
                f'containers/.datalad/environments/{container_name}/image'
            ),
            'bids_app_input_dir': step_input_dir,
            'bids_app_output_dir': bids_app_output_dir,
            'bids_app_args': bids_app_args,
            'singularity_flags': step_config.get('singularity_args', []),
            'subject_selection_flag': subject_selection_flag,
            'flag_filterfile': flag_filterfile,
            'flag_fs_license': flag_fs_license,
            'path_fs_license': path_fs_license,
            'inter_step_cmds': step.get('inter_step_cmds', ''),
        }
        processed_steps.append(processed_step)

    # Use provided final zip foldernames or fall back to last step's config
    if final_zip_foldernames is None:
        # Fallback: get from last step's config (for backward compatibility)
        last_step_config = pipeline_config[-1].get('config', {})
        final_zip_foldernames, _ = app_output_settings_from_config(last_step_config)

    # Update the last step's output directory to match the final zip configuration
    if processed_steps and final_zip_foldernames:
        # Create a temporary config with the final zip_foldernames to get the correct output path
        temp_config = {'zip_foldernames': final_zip_foldernames, 'all_results_in_one_zip': True}
        _, final_output_dir = app_output_settings_from_config(temp_config)
        processed_steps[-1]['bids_app_output_dir'] = final_output_dir

    # Generate the final zip command using existing helper for consistency
    cmd_zip = get_output_zipping_cmds(final_zip_foldernames, processing_level)

    # Get unzip commands for any zipped input datasets
    cmd_unzip_inputds = get_input_unzipping_cmds(input_datasets)

    # Render the template
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )

    template = env.get_template('bidsapp_pipeline_run.sh.jinja2')
    return template.render(
        processing_level=processing_level,
        input_datasets=input_datasets,
        processed_steps=processed_steps,
        templateflow_home_on_disk=templateflow_home,
        templateflow_in_container='/SGLR/TEMPLATEFLOW_HOME',
        cmd_unzip_inputds=cmd_unzip_inputds,
        cmd_zip=cmd_zip,
        PATH_FS_LICENSE_IN_CONTAINER=PATH_FS_LICENSE_IN_CONTAINER,
        OUTPUT_MAIN_FOLDERNAME=OUTPUT_MAIN_FOLDERNAME,
    )


def get_input_unzipping_cmds(input_datasets):
    """
    This is to generate command in `<containerName>_zip.sh` to unzip
    a specific input dataset if needed.

    Parameters
    ----------
    input_datasets: list of dicts
        each dict contains information of an input dataset

    Returns:
    ---------
    cmd: str
        commands to unzip input datasets
    """
    if not any(ds['is_zipped'] for ds in input_datasets):
        return ''

    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    template = env.get_template('unzip_inputds.sh.jinja2')
    cmd = template.render(input_datasets=input_datasets)

    return cmd
