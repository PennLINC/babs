import json
import os
import subprocess
from pathlib import Path

import pytest

from babs.generate_bidsapp_runscript import (
    generate_bidsapp_runscript,
    generate_pipeline_runscript,
    get_input_unzipping_cmds,
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


def generate_session_filter_file(config_file, input_datasets, tmp_path):
    """Render a session-level runscript, run its filter-file block, and parse the result.

    The filter file is written by the job script at runtime, so the only way to see what
    a BIDS app actually receives is to execute the block that builds it.
    """
    config = read_yaml(NOTEBOOKS_DIR / config_file)
    _, bids_app_output_dir = app_output_settings_from_config(config)
    script_content = generate_bidsapp_runscript(
        input_datasets,
        'session',
        container_name=config_file.split('_')[1],
        relative_container_path='containers/.datalad/containers/app/image',
        bids_app_output_dir=bids_app_output_dir,
        dict_zip_foldernames=config['zip_foldernames'],
        bids_app_args=config['bids_app_args'],
        singularity_args=config['singularity_args'],
        templateflow_home='/path/to/templateflow_home',
    )

    # the block runs from `filterfile=...` through the last `sed -i` that repairs the JSON
    lines = script_content.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('filterfile='))
    end = max(i for i, line in enumerate(lines) if line.startswith('sed -i'))
    block = '\n'.join(lines[start : end + 1])

    subprocess.run(
        ['bash', '-c', block],
        cwd=tmp_path,
        env={'sesid': 'ses-1', 'PATH': os.environ['PATH']},
        check=True,
    )
    return json.loads((tmp_path / 'ses-1_filter.json').read_text())


@pytest.mark.parametrize(
    'config_file',
    [
        'eg_fmriprep-24-1-1_regular.yaml',
        'eg_qsiprep-1-0-0_regular.yaml',
        'eg_aslprep-0-7-5.yaml',
    ],
)
def test_session_filter_file_fmap_carries_no_session(config_file, tmp_path):
    """The fmap entry must not pin a session.

    fmriprep passes this entry straight to sdcflows' ``find_estimators()`` alongside the
    session it resolved itself, and sdcflows raises "Filters include session, but session
    is already defined." when it receives both. That aborts workflow construction, so no
    session-level job can run. The session is already enforced by the sparse checkout.
    """
    filters = generate_session_filter_file(config_file, input_datasets_prep, tmp_path)

    assert filters['fmap'] == {'datatype': 'fmap'}

    # the remaining entries still restrict to this session ('ses-' is stripped by sed)
    others = {key: value for key, value in filters.items() if key != 'fmap'}
    assert others
    assert all(value.get('session') == '1' for value in others.values())


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
