import subprocess
from pathlib import Path

import pytest

from babs.generate_bidsapp_runscript import (
    generate_bidsapp_runscript,
    get_input_unzipping_cmds,
)
from babs.utils import (
    app_output_settings_from_config,
    read_yaml,
)

input_datasets_prep = [
    {
        'name': 'bids',
        'path_now_rel': 'inputs/data/BIDS',
        'path_data_rel': 'inputs/data/BIDS',
        'is_zipped': False,
    },
]

input_datasets_fmriprep_ingressed_anat = [
    {
        'name': 'freesurfer',
        'path_now_rel': 'inputs/data',
        'path_data_rel': 'inputs/data/freesurfer',
        'is_zipped': True,
    },
    {
        'name': 'bids',
        'path_now_rel': 'inputs/data/BIDS',
        'path_data_rel': 'inputs/data/BIDS',
        'is_zipped': False,
    },
]

input_datasets_xcpd = [
    {
        'name': 'fmriprep',
        'path_now_rel': 'inputs/data',
        'path_data_rel': 'inputs/data/fmriprep',
        'is_zipped': True,
    },
]

input_datasets_qsirecon = [
    {
        'name': 'qsiprep',
        'path_now_rel': 'inputs/data',
        'path_data_rel': 'inputs/data/qsiprep',
        'is_zipped': True,
    },
]

input_datasets_qsirecon_ingressed_anat_zipped = [
    {
        'name': 'freesurfer',
        'path_now_rel': 'inputs/data',
        'path_data_rel': 'inputs/data/freesurfer',
        'is_zipped': True,
    },
    {
        'name': 'qsiprep',
        'path_now_rel': 'inputs/data',
        'path_data_rel': 'inputs/data/qsiprep',
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
def test_generate_bidsapp_runscript(input_datasets, config_file, processing_level):
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

    out_fn = Path('.') / f'{config_path.name}_{processing_level}.sh'
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
