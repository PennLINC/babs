import os
import shutil
import subprocess
from pathlib import Path

import pytest
from jinja2 import Environment, PackageLoader, StrictUndefined

from babs.generate_submit_script import generate_submit_script
from babs.templateflow import templateflow_from_config
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
        result = subprocess.run(
            ['shellcheck', script_path], capture_output=True, text=True, check=False
        )
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


def test_container_provided_via_worktree_of_shared_clone():
    """Jobs share the once-fetched image through a worktree, not a per-job get/symlink.

    Per-job `datalad get` of the same image from the RIA store fails at scale
    (babs#416); a worktree of `analysis/containers` shares its annex objects.
    """
    script = _render(input_datasets_prep, 'subject')

    # Locked, so `git worktree prune` in `babs submit` leaves running jobs alone:
    assert (
        'git -C "${CONTAINERS_SHARED}" worktree add --detach --force --no-checkout \\\n'
        '  --lock --reason "babs ${BRANCH}" "${PWD}/containers" "${CONTAINERS_COMMIT}"' in script
    )
    assert 'CONTAINERS_COMMIT="$(git rev-parse HEAD:containers)"' in script
    assert 'CONTAINERS_SHARED="/tmp/babs_project/analysis/containers"' in script
    assert 'ln -s' not in script
    # Only the image(s) are checked out, and not via `git sparse-checkout`
    # (which would write the shared clone's .git/config from every job):
    assert 'git -C containers checkout-index -- "${CONTAINER_FILES[@]}"' in script
    assert 'git -C containers sparse-checkout' not in script
    # `smudge --update` writes the shared clone's keys database from every job:
    assert 'git annex smudge' not in script

    # Cleanup must detach the worktree before `datalad drop`/`git annex dead`,
    # which would otherwise act on the shared clone's annex.
    cleanup = script[script.index('cleanup() {') : script.index('trap cleanup EXIT')]
    detach = cleanup.index('rm -rf containers')
    assert detach < cleanup.index('datalad drop -r .')
    assert detach < cleanup.index('git annex dead here')


def _script_section(script, start, end):
    """Return the lines of `script` from the one starting `start` to the next starting `end`."""
    lines = script.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith(start))
    last = next(i for i, line in enumerate(lines) if i > first and line.startswith(end))
    return '\n'.join(lines[first : last + 1])


@pytest.mark.skipif(shutil.which('git-annex') is None, reason='needs git-annex')
def test_container_worktree_runs_against_real_annex(tmp_path):
    """Run the job's container provisioning and cleanup against a real git-annex clone."""

    def git(cwd, *args):
        return subprocess.run(
            ['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    # The shared clone: an image plus other files the job must not check out.
    shared = tmp_path / 'analysis' / 'containers'
    (shared / 'images').mkdir(parents=True)
    (shared / 'images' / 'app.sif').write_text('IMAGE')
    (shared / 'other').mkdir()
    (shared / 'other' / 'notes.txt').write_text('not needed')
    git(shared, 'init', '-q')
    git(shared, 'annex', 'init', '-q', 'shared')
    git(shared, 'annex', 'add', 'images/app.sif')
    git(shared, 'add', 'other')
    git(shared, 'commit', '-q', '-m', 'image')
    recorded = git(shared, 'rev-parse', 'HEAD').strip()
    # Move the shared clone on; the job must still use the recorded commit.
    (shared / 'other' / 'later.txt').write_text('later')
    git(shared, 'add', 'other')
    git(shared, 'commit', '-q', '-m', 'later')

    # The job's dataset records `containers` at `recorded`.
    branch = 'job-12-3-sub-01'
    ds = tmp_path / 'scratch' / branch / 'ds'
    (ds / 'containers').mkdir(parents=True)
    git(ds, 'init', '-q')
    git(ds, 'update-index', '--add', '--cacheinfo', f'160000,{recorded},containers')
    git(ds, 'commit', '-q', '-m', 'ds')

    script = generate_submit_script(
        queue_system='slurm',
        cluster_resources_config={'interpreting_shell': '/bin/bash'},
        script_preamble='',
        job_scratch_directory=str(tmp_path / 'scratch'),
        input_datasets=input_datasets_prep,
        processing_level='subject',
        container_name='app',
        zip_foldernames={'app': '0'},
        container_images=['containers/images/app.sif'],
        analysis_path=str(tmp_path / 'analysis'),
    )
    provision = _script_section(script, 'CONTAINER_IMAGE_PATHS=(', 'done')
    cleanup = _script_section(script, 'cleanup() {', '}')
    worktree = ds / 'containers'

    env = {**os.environ, 'BRANCH': branch, 'JOB_SCRATCH_DIR': str(tmp_path / 'scratch')}
    subprocess.run(['bash', '-c', f'set -e -u\n{provision}'], cwd=ds, env=env, check=True)
    assert (worktree / 'images' / 'app.sif').read_text() == 'IMAGE'
    assert not (worktree / 'other').exists()
    assert git(worktree, 'rev-parse', 'HEAD').strip() == recorded
    assert git(worktree, 'status', '--porcelain') == ''
    assert f'locked babs {branch}' in git(shared, 'worktree', 'list', '--porcelain')

    # Cleanup removes the worktree and its record, and leaves the shared image.
    env['CONTAINERS_GITDIR'] = git(worktree, 'rev-parse', '--absolute-git-dir').strip()
    subprocess.run(['bash', '-c', f'set -u\n{cleanup}\ncleanup'], cwd=ds, env=env, check=True)
    assert not ds.exists()
    assert git(shared, 'worktree', 'list', '--porcelain').count('worktree ') == 1
    assert (shared / 'images' / 'app.sif').read_text() == 'IMAGE'


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
    result = subprocess.run(
        ['bash', '-c', script], cwd=tmp_path, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert zipname in result.stdout, f'zip not located:\nOUT:{result.stdout}\nERR:{result.stderr}'


def test_generate_submit_script_templateflow(tmp_path):
    """A `templateflow` section installs each template and lists each pattern as an input."""
    config = read_yaml(NOTEBOOKS_DIR / 'eg_fmriprep-24-1-1_regular.yaml')
    templateflow = templateflow_from_config(
        {
            'templateflow': {
                'url': 'https://github.com/templateflow/templateflow.git',
                'required': [
                    'tpl-MNI152NLin2009cAsym/*_res-02_T1w.nii.gz',
                    'tpl-OASIS30ANTs/*_res-01_T1w.nii.gz',
                ],
            }
        }
    )
    kwargs = {
        'queue_system': 'slurm',
        'cluster_resources_config': config['cluster_resources'],
        'script_preamble': config['script_preamble'],
        'job_scratch_directory': config['job_compute_space'],
        'input_datasets': input_datasets_prep,
        'processing_level': 'subject',
        'container_name': 'fmriprep',
        'zip_foldernames': config['zip_foldernames'],
        'analysis_path': '/tmp/babs_project/analysis',
    }

    script_content = generate_submit_script(templateflow=templateflow, **kwargs)
    # the job's clone is sparse: templateflow must be checked out to be installable
    assert '  containers \\\n  sourcedata/templateflow \\\n' in script_content
    assert 'datalad get -n "sourcedata/templateflow/tpl-MNI152NLin2009cAsym"' in script_content
    assert 'datalad get -n "sourcedata/templateflow/tpl-OASIS30ANTs"' in script_content
    assert (
        '-i "sourcedata/templateflow/tpl-MNI152NLin2009cAsym/*_res-02_T1w.nii.gz"'
        in script_content
    )
    assert '-i "sourcedata/templateflow/tpl-OASIS30ANTs/*_res-01_T1w.nii.gz"' in script_content

    out_fn = tmp_path / 'participant_job.sh'
    out_fn.write_text(script_content)
    passed, status = run_shellcheck(str(out_fn))
    assert passed, status

    # without the section, nothing templateflow-related is rendered
    assert 'templateflow' not in generate_submit_script(**kwargs)
