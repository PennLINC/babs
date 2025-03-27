"""Create participant_job.sh"""

import warnings
from importlib import resources

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined

# Multiple scheduler system handling
DIRECTIVE_PREFIX = {
    'sge': '#$',
    'slurm': '#SBATCH',
}

# Load scheduler system lookup table from YAML
with resources.files('babs').joinpath('dict_cluster_systems.yaml').open() as f:
    SCHEDULER_SYSTEM_LUT = yaml.safe_load(f)


def generate_submit_script(
    queue_system,
    cluster_resources_config,
    script_preamble,
    job_scratch_directory,
    input_datasets,
    processing_level,
    container_name,
    zip_foldernames,
):
    """
    Generate a bash script that runs the BIDS App singularity image.

    Parameters
    ----------


    Returns
    -------
    bidsapp_run_script: str
        The contents of the bash script that runs the BIDS App singularity image.
    """
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    participant_job_template = env.get_template('participant_job.sh.jinja2')

    # Get the setup for the scheduler directives:
    interpreting_shell, scheduler_directives = generate_scheduler_directives(
        queue_system, cluster_resources_config
    )

    if queue_system == 'sge':
        varname_jobid = 'JOB_ID'
    elif queue_system == 'slurm':
        varname_jobid = 'SLURM_ARRAY_TASK_ID'

    # If any input dataset is zipped, get the setup for the zipfile locator:
    zip_locator_template = env.get_template('determine_zipfilename.sh.jinja2')
    zip_locator_text = zip_locator_template.render(
        input_datasets=input_datasets,
        processing_level=processing_level,
        has_a_zipped_input_dataset=any(
            input_dataset['is_zipped'] for input_dataset in input_datasets
        ),
    )

    return participant_job_template.render(
        interpreting_shell=interpreting_shell,
        processing_level=processing_level,
        scheduler_directives=scheduler_directives,
        script_preamble=script_preamble,
        job_scratch_directory=job_scratch_directory,
        zip_locator_text=zip_locator_text,
        container_name=container_name,
        zip_foldernames=zip_foldernames,
        varname_jobid=varname_jobid,
        input_datasets=input_datasets,
        datalad_expand_inputs=any(
            not input_dataset['is_zipped'] for input_dataset in input_datasets
        ),
    )


def generate_test_submit_script(
    queue_system,
    cluster_resources_config,
    script_preamble,
    job_scratch_directory,
    check_setup_directory,
    check_setup_python_script,
):
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    template = env.get_template('test_job.sh.jinja2')

    # Get the setup for the scheduler directives:
    interpreting_shell, scheduler_directives = generate_scheduler_directives(
        queue_system, cluster_resources_config
    )
    return template.render(
        interpreting_shell=interpreting_shell,
        scheduler_directives=scheduler_directives,
        script_preamble=script_preamble,
        job_scratch_directory=job_scratch_directory,
        check_setup_directory=check_setup_directory,
        check_setup_python_script=check_setup_python_script,
    )


def generate_scheduler_directives(queue_system, cluster_resources_config):
    """
    This is to generate the directives ("head of the bash file")
    for requesting cluster resources, specifying interpreting shell, etc.

    Parameters:
    ------------
    queue_system: str
        queue system type
    cluster_resources_config: dictionary
        the section `cluster_resources` in container's config yaml

    Returns:
    ------------
    lines: list of str
        It's part of the `participant_job.sh`; it is generated
        based on config yaml file and the system's dict.
    """

    queue_system_lut = SCHEDULER_SYSTEM_LUT[queue_system]
    queue_system_directive_prefix = DIRECTIVE_PREFIX[queue_system]

    # copy cluster_resources_config to a new variable
    cluster_resources_config = cluster_resources_config.copy()
    lines = []

    interpreting_shell = cluster_resources_config.pop('interpreting_shell', None)
    if interpreting_shell is None:
        warnings.warn(
            "The interpreting shell was not specified for 'participant_job.sh'."
            " This should be specified using 'interpreting_shell'"
            " under section 'cluster_resources' in container's"
            ' configuration YAML file.',
            stacklevel=2,
        )
        interpreting_shell = '/bin/bash'

    if customized_text := cluster_resources_config.pop('customized_text', None):
        lines.append(customized_text)

    for generic_resource_name, value in cluster_resources_config.items():
        if generic_resource_name not in queue_system_lut:
            warnings.warn(
                f"Invalid key '{generic_resource_name}' in section `cluster_resources`"
                ' in `container_config`; This key has not been defined'
                f" in file 'dict_cluster_systems.yaml' for system '{queue_system}'.",
                stacklevel=2,
            )
            return ''
        formatted_arg = queue_system_lut[generic_resource_name].replace('$VALUE', str(value))
        lines.append(f'{queue_system_directive_prefix} {formatted_arg}')

    return interpreting_shell, lines
