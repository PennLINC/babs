import subprocess
from pathlib import Path

import pytest

from jinja2 import Environment, PackageLoader, StrictUndefined

from babs.constants import OUTPUT_MAIN_FOLDERNAME
from babs.generate_bidsapp_runscript import (
    generate_bidsapp_runscript,
    generate_pipeline_runscript,
    get_input_unzipping_cmds,
    get_output_zipping_cmds,
)
from babs.utils import (
    app_output_settings_from_config,
    read_yaml,
)

input_datasets_prep = [
    {
        'name': 'bids',
        'path_in_babs': 'inputs/data/BIDS',
        'unzipped_path_containing_subject_dirs': 'inputs/data/BIDS',
        'is_zipped': False,
    },
]

input_datasets_fmriprep_ingressed_anat = [
    {
        'name': 'freesurfer',
        'path_in_babs': 'inputs/data',
        'unzipped_path_containing_subject_dirs': 'inputs/data/freesurfer',
        'is_zipped': True,
    },
    {
        'name': 'bids',
        'path_in_babs': 'inputs/data/BIDS',
        'unzipped_path_containing_subject_dirs': 'inputs/data/BIDS',
        'is_zipped': False,
    },
]

input_datasets_xcpd = [
    {
        'name': 'fmriprep',
        'path_in_babs': 'inputs/data',
        'unzipped_path_containing_subject_dirs': 'inputs/data/fmriprep',
        'is_zipped': True,
    },
]

input_datasets_qsirecon = [
    {
        'name': 'qsiprep',
        'path_in_babs': 'inputs/data',
        'unzipped_path_containing_subject_dirs': 'inputs/data/qsiprep',
        'is_zipped': True,
    },
]

input_datasets_qsirecon_ingressed_anat_zipped = [
    {
        'name': 'freesurfer',
        'path_in_babs': 'inputs/data',
        'unzipped_path_containing_subject_dirs': 'inputs/data/freesurfer',
        'is_zipped': True,
    },
    {
        'name': 'qsiprep',
        'path_in_babs': 'inputs/data',
        'unzipped_path_containing_subject_dirs': 'inputs/data/qsiprep',
        'is_zipped': True,
    },
]


# Get the path to the notebooks directory
NOTEBOOKS_DIR = Path(__file__).parent.parent / 'notebooks'

# match the inputs with their corresponding yaml files in notebooks/
testing_pairs = [
    (input_ds, config, level)
    for input_ds, config in [
        (input_datasets_prep, 'eg_toybidsapp-0-0-7_rawBIDS-walkthrough.yaml'),
        (input_datasets_prep, 'eg_aslprep-0-7-5.yaml'),
        (input_datasets_prep, 'eg_fmriprep-24-1-1_anatonly.yaml'),
        (input_datasets_prep, 'eg_fmriprep-24-1-1_regular.yaml'),
        (
            input_datasets_fmriprep_ingressed_anat,
            'eg_fmriprep-24-1-1_ingressed-fs.yaml',
        ),
        (input_datasets_prep, 'eg_qsiprep-1-0-0_regular.yaml'),
        (input_datasets_xcpd, 'eg_xcpd-0-10-6_linc.yaml'),
        (input_datasets_qsirecon, 'eg_qsirecon-1-0-1_custom_spec.yaml'),
        (input_datasets_qsirecon_ingressed_anat_zipped, 'eg_qsirecon-1-0-1_hsvs.yaml'),
    ]
    for level in ['subject', 'session']
]


def test_get_input_unipping_cmds():
    """Test that the input unzipping commands are generated correctly."""
    assert get_input_unzipping_cmds(input_datasets_prep) == ''

    assert len(get_input_unzipping_cmds(input_datasets_fmriprep_ingressed_anat)) > 0

    assert len(get_input_unzipping_cmds(input_datasets_xcpd)) > 0

    qsirecon_cmd = get_input_unzipping_cmds(input_datasets_qsirecon)
    assert len(qsirecon_cmd) > 0

    qsirecon_anat_cmd = get_input_unzipping_cmds(input_datasets_qsirecon_ingressed_anat_zipped)
    assert len(qsirecon_anat_cmd) > 0
    assert len(qsirecon_anat_cmd) > len(qsirecon_cmd)


@pytest.mark.parametrize(('input_datasets', 'config_file', 'processing_level'), testing_pairs)
def test_generate_bidsapp_runscript(input_datasets, config_file, processing_level, tmp_path):
    """Test that the bidsapp runscript is generated correctly."""
    config_path = NOTEBOOKS_DIR / config_file
    container_name = config_file.split('_')[1]
    config = read_yaml(config_path)
    dict_zip_foldernames, bids_app_output_dir = app_output_settings_from_config(config)
    script_content = generate_bidsapp_runscript(
        input_datasets,
        processing_level,
        container_name=container_name,
        relative_container_path=f'containers/.datalad/containers/{container_name}/image',
        bids_app_output_dir=bids_app_output_dir,
        dict_zip_foldernames=config['zip_foldernames'],
        bids_app_args=config['bids_app_args'],
        singularity_args=config['singularity_args'],
        templateflow_home='/path/to/templateflow_home',
    )

    out_fn = tmp_path / f'{config_path.name}_{processing_level}.sh'
    with open(out_fn, 'w') as f:
        f.write(script_content)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(script_content)
    assert passed, status


def run_shellcheck(script_path):
    """Run shellcheck on a shell script string and return the result.

    Parameters
    ----------
    script_path : str
        The path to the shell script to check

    Returns
    -------
    tuple
        (bool, str) where bool indicates success (True) or failure (False),
        and str contains shellcheck output
    """

    try:
        # Run shellcheck on the temporary file
        result = subprocess.run(['shellcheck', script_path], capture_output=True, text=True)
        return result.returncode == 0, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.output
    except Exception as e:
        return False, str(e)


@pytest.mark.parametrize('processing_level', ['subject', 'session'])
def test_generate_bidsapp_runscript_no_zip(processing_level, tmp_path):
    """Test that the run script works when zip_foldernames is absent."""
    script_content = generate_bidsapp_runscript(
        input_datasets_prep,
        processing_level,
        container_name='toybidsapp-0-0-7',
        relative_container_path='containers/.datalad/containers/toybidsapp-0-0-7/image',
        bids_app_output_dir='outputs',
        dict_zip_foldernames=None,
        bids_app_args='',
        singularity_args=['--containall'],
        templateflow_home=None,
    )

    assert '7z' not in script_content
    assert 'rm -rf outputs' not in script_content
    assert 'singularity run' in script_content

    out_fn = tmp_path / f'no_zip_{processing_level}.sh'
    with open(out_fn, 'w') as f:
        f.write(script_content)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(script_content)
    assert passed, status


@pytest.mark.parametrize('processing_level', ['subject', 'session'])
def test_generate_zip_outputs_script(processing_level, tmp_path):
    """Test that the standalone zip script is generated correctly."""
    dict_zip_foldernames = {'fmriprep_anat': '24-1-1'}
    cmd_zip = get_output_zipping_cmds(dict_zip_foldernames, processing_level)

    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    template = env.get_template('zip_outputs.sh.jinja2')
    script_content = template.render(
        processing_level=processing_level,
        cmd_zip=cmd_zip,
        OUTPUT_MAIN_FOLDERNAME=OUTPUT_MAIN_FOLDERNAME,
    )

    assert '7z' in script_content
    assert 'rm -rf outputs' in script_content

    out_fn = tmp_path / f'zip_outputs_{processing_level}.sh'
    with open(out_fn, 'w') as f:
        f.write(script_content)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(script_content)
    assert passed, status


def test_generate_pipeline_runscript(tmp_path):
    """Test that the pipeline runscript is generated correctly."""
    config_path = NOTEBOOKS_DIR / 'eg_nordic-fmriprep_pipeline.yaml'
    config = read_yaml(config_path)

    # Extract pipeline steps from config
    pipeline_config = config['pipeline']

    script_content = generate_pipeline_runscript(
        pipeline_config=pipeline_config,
        processing_level='subject',
        input_datasets=input_datasets_prep,
        templateflow_home='/path/to/templateflow_home',
        final_zip_foldernames=config.get('zip_foldernames', {}),
    )

    out_fn = tmp_path / f'{config_path.name}_pipeline.sh'
    with open(out_fn, 'w') as f:
        f.write(script_content)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(script_content)
    assert passed, status
