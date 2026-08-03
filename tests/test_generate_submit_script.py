import subprocess
from pathlib import Path

import pytest
from jinja2 import Environment, PackageLoader, StrictUndefined

from babs.generate_submit_script import generate_submit_script
from babs.utils import (
    read_yaml,
    var_safe_name,
)

input_datasets_prep = [
    {
        'name': 'bids',
        'path_in_babs': 'inputs/data/BIDS',
        'unzipped_path_containing_subject_dirs': 'inputs/data/BIDS',
        'is_zipped': False,
        'common_paths': ['dataset_description.json'],
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
        'common_paths': [],
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
        zip_foldernames=config['zip_foldernames'],
        analysis_path='/tmp/babs_project/analysis',
    )

    out_fn = tmp_path / f'participant_job_{config_path.name}_{processing_level}.sh'
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
        analysis_path='/tmp/babs_project/analysis',
    )

    # Write script to file and run shellcheck (same as single-app tests)
    out_fn = tmp_path / 'participant_job.sh'
    with open(out_fn, 'w') as f:
        f.write(script_content)
    passed, status = run_shellcheck(str(out_fn))
    if not passed:
        print(script_content)
    assert passed, status


def _render(input_datasets, processing_level):
    """Render the participant job for a minimal single-app config (no YAML needed)."""
    return generate_submit_script(
        queue_system='slurm',
        cluster_resources_config={'interpreting_shell': '/bin/bash'},
        script_preamble='',
        job_scratch_directory='/tmp/job',
        input_datasets=input_datasets,
        processing_level=processing_level,
        container_name='fmriprep',
        zip_foldernames={'fmriprep': '0'},
        container_images=['containers/fmriprep.sif'],
        analysis_path='/tmp/babs_project/analysis',
    )


def test_bids_inheritance_tiers_per_processing_level():
    """Root tier is grabbed for every job; the subject tier only for session jobs.

    These assert on the *generated script text* (like the rest of this module);
    the runtime ``resolve_tier`` behavior is exercised by the e2e walkthrough.
    """
    path = input_datasets_prep[0]['path_in_babs']
    subj = _render(input_datasets_prep, 'subject')
    sess = _render(input_datasets_prep, 'session')

    # root tier resolved for both levels
    assert f'resolve_tier "{path}" ""' in subj
    assert f'resolve_tier "{path}" ""' in sess

    # subject tier resolved ONLY for session-level jobs (the gap session checkout misses)
    assert f'resolve_tier "{path}" "${{subid}}"' in sess
    assert f'resolve_tier "{path}" "${{subid}}"' not in subj

    # resolved paths are wired into `datalad run` as inputs
    for script in (subj, sess):
        assert 'DATALAD_INPUTS=()' in script
        assert '${DATALAD_INPUTS[@]+"${DATALAD_INPUTS[@]}"}' in script


def test_bids_inheritance_skips_zipped_inputs():
    """Zipped inputs get no inheritance grab; only the unzipped one is resolved."""
    script = _render(input_datasets_fmriprep_ingressed_anat, 'subject')
    # the unzipped BIDS dataset is resolved ...
    assert 'resolve_tier "inputs/data/BIDS" ""' in script
    # ... but the zipped freesurfer dataset (path_in_babs 'inputs/data') is not
    assert 'resolve_tier "inputs/data" ""' not in script


def test_common_paths_threaded_into_consumers():
    """An explicit common_paths entry reaches get, sparse-checkout, and `datalad run -i`."""
    dss = [dict(input_datasets_prep[0], common_paths=['phenotype/participants.tsv'])]
    script = _render(dss, 'subject')
    full = 'inputs/data/BIDS/phenotype/participants.tsv'
    assert f'datalad get -n "{full}"' in script  # datalad get
    assert "'phenotype/participants.tsv'" in script  # sparse=( ... ) set
    assert f'-i "{full}"' in script  # datalad run input


def _render_zip_locator(input_datasets, processing_level):
    """Render just the zip-locator template, mirroring generate_submit_script's env."""
    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    env.filters['shell_safe'] = var_safe_name
    return env.get_template('determine_zipfilename.sh.jinja2').render(
        input_datasets=input_datasets,
        processing_level=processing_level,
        has_a_zipped_input_dataset=any(d['is_zipped'] for d in input_datasets),
    )


# Zipped-input derivative names carry regex metacharacters (and should in some cases for BIDS spec)
ZIPPED_INPUT_NAMES = [
    'fMRIPrep-25.2.5+anat',  # the real culprit: '+' (an ERE quantifier) and '.'
    'SimBIDS-0.0.3+a+b',  # two '+' signs
    'MRIQC-24.0.2',  # '.' only (ERE '.' matches any char)
    'sup+r-W3.rd-f.le_name',  # just for fun: '+', multiple '.', '_', '-'
]


@pytest.mark.parametrize('name', ZIPPED_INPUT_NAMES)
@pytest.mark.parametrize('processing_level', ['subject', 'session'])
def test_find_single_zip_handles_regex_metachars_in_name(name, processing_level, tmp_path):
    """Regression: a zipped-input derivative name with regex metacharacters must be located.

    The finder interpolates the input dataset name into a grep pattern. Derivative
    names carry regex metacharacters (the '+' and '.' in 'fMRIPrep-25.2.5+anat'); a
    single `grep -E` read '+' as a quantifier and matched 0 zips, failing every
    chained job whose upstream derivative name carried a '+'. See
    determine_zipfilename.sh.jinja2 (fixed-string matching).
    """
    path_in_babs = f'sourcedata/{name}'
    stem = 'sub-01_ses-1' if processing_level == 'session' else 'sub-01'

    # a fake input tree with a '+'-named zip committed (only git-tracked files are seen)
    tree = tmp_path / path_in_babs
    tree.mkdir(parents=True)
    zipname = f'{stem}_{name}-25-2-5.zip'
    (tree / zipname).write_text('')
    subprocess.run(['git', 'init', '-q'], cwd=tree, check=True)
    subprocess.run(['git', 'add', '.'], cwd=tree, check=True)
    subprocess.run(
        ['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'zip'],
        cwd=tree,
        check=True,
    )

    finder = _render_zip_locator(
        [{'name': name, 'path_in_babs': path_in_babs, 'is_zipped': True}],
        processing_level=processing_level,
    )
    # the template defines the finder AND calls it, echoing the located zip path
    script = f'set -e\nsubid=sub-01\nsesid=ses-1\n{finder}\n'
    result = subprocess.run(['bash', '-c', script], cwd=tmp_path, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert zipname in result.stdout, f'zip not located:\nOUT:{result.stdout}\nERR:{result.stderr}'
