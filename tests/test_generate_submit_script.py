import subprocess
from pathlib import Path

import pytest

from babs.generate_submit_script import generate_submit_script
from babs.utils import (
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


@pytest.mark.parametrize(('input_datasets', 'config_file', 'processing_level'), testing_pairs)
def test_generate_submit_script(input_datasets, config_file, processing_level, tmp_path):
    """Test that the bidsapp runscript is generated correctly."""
    config_path = NOTEBOOKS_DIR / config_file
    container_name = config_file.split('_')[1]
    config = read_yaml(config_path)
    script_content = generate_submit_script(
        queue_system='slurm',
        cluster_resources_config=config['cluster_resources'],
        script_preamble=config['script_preamble'],
        job_scratch_directory=config['job_compute_space'],
        input_datasets=input_datasets,
        processing_level=processing_level,
        container_name=container_name,
        output_dir=config['output_dir'],
    )

    out_fn = tmp_path / f'participant_job_{config_path.name}_{processing_level}.sh'
    with open(out_fn, 'w') as f:
        f.write(script_content)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(script_content)
    assert passed, status


# ---------------------------------------------------------------------------
# pre_run / post_run splice-point hooks
# ---------------------------------------------------------------------------

PRE_RUN_MARKER = '# pre_run hooks:'
POST_RUN_MARKER = '# post_run hooks:'
CONTRACT_EXPORT = 'export subid BRANCH PROJECT_ROOT JOB_SCRATCH_DIR'


def _render_with_hooks(processing_level='subject', **hook_kwargs):
    """Render participant_job.sh for a simple single-app config, with optional hooks."""
    config = read_yaml(NOTEBOOKS_DIR / 'eg_fmriprep-24-1-1_regular.yaml')
    return generate_submit_script(
        queue_system='slurm',
        cluster_resources_config=config['cluster_resources'],
        script_preamble=config['script_preamble'],
        job_scratch_directory=config['job_compute_space'],
        input_datasets=input_datasets_prep,
        processing_level=processing_level,
        container_name='fmriprep-24-1-1',
        output_dir=config['output_dir'],
        **hook_kwargs,
    )


def _pre_run_block(text):
    """Slice out the rendered pre_run subshell (marker through its closing paren)."""
    start = text.index(PRE_RUN_MARKER)
    return text[start : text.index('\n)\n', start) + 2]


def test_hooks_absent_when_not_configured(tmp_path):
    """No hooks configured: no splice blocks rendered, and None behaves like []."""
    default_render = _render_with_hooks()
    empty_render = _render_with_hooks(hook_pre_run=[], hook_post_run=[])

    assert default_render == empty_render  # None and [] are both no-ops
    assert PRE_RUN_MARKER not in default_render
    assert POST_RUN_MARKER not in default_render

    out_fn = tmp_path / 'participant_job_nohooks.sh'
    out_fn.write_text(default_render)
    passed, status = run_shellcheck(str(out_fn))
    assert passed, status


def test_pre_run_and_post_run_hooks_spliced(tmp_path):
    """Configured hooks render as subshells exporting the contract, in order,
    positioned around the datalad run wrapper."""
    text = _render_with_hooks(
        hook_pre_run=['echo PRE_A', 'echo PRE_B'],
        hook_post_run=['echo POST_ONE'],
    )

    assert PRE_RUN_MARKER in text
    assert POST_RUN_MARKER in text
    # the contract is exported once per splice subshell
    assert text.count(CONTRACT_EXPORT) == 2
    # snippets appear, in the configured order
    assert text.index('echo PRE_A') < text.index('echo PRE_B')
    assert 'echo POST_ONE' in text

    # pre_run sits before the run; post_run after it, before the push
    i_pre = text.index(PRE_RUN_MARKER)
    i_run = text.index('\ndatalad run ')
    i_post = text.index(POST_RUN_MARKER)
    i_push = text.index('datalad push --to output-storage')
    assert i_pre < i_run < i_post < i_push

    out_fn = tmp_path / 'participant_job_hooks.sh'
    out_fn.write_text(text)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(text)
    assert passed, status


def test_hooks_export_sesid_only_at_session_level():
    """sesid joins the exported contract only for session-level processing."""
    session = _render_with_hooks(processing_level='session', hook_pre_run=['echo HI'])
    subject = _render_with_hooks(processing_level='subject', hook_pre_run=['echo HI'])

    assert 'export sesid' in _pre_run_block(session)
    assert 'export sesid' not in _pre_run_block(subject)


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


def test_generate_submit_script_pipeline(tmp_path):
    """Test submit script generation for pipeline configuration."""
    # Use same pattern as single-app tests: read from existing YAML config
    config_path = NOTEBOOKS_DIR / 'eg_nordic-fmriprep_pipeline.yaml'
    config = read_yaml(config_path)

    image_paths = [
        'containers/.datalad/environments/nordic-0-0-1/image',
        'containers/.datalad/environments/fmriprep-25.0.0/image',
    ]

    script_content = generate_submit_script(
        queue_system='slurm',
        cluster_resources_config=config['cluster_resources'],
        script_preamble=config['script_preamble'],
        job_scratch_directory=config['job_compute_space'],
        input_datasets=input_datasets_prep,
        processing_level='subject',
        container_name='pipeline',  # placeholder
        zip_foldernames=config['zip_foldernames'],
        run_script_relpath='code/pipeline_zip.sh',
        container_images=image_paths,
        datalad_run_message='nordic-fmriprep pipeline',
    )

    # Write script to file and run shellcheck (same as single-app tests)
    out_fn = tmp_path / 'participant_job.sh'
    with open(out_fn, 'w') as f:
        f.write(script_content)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(script_content)
    assert passed, status
