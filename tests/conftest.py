"""This is to get data for pytests"""

import os
import os.path as op

# import tempfile
import subprocess
import sys
import zipfile
from pathlib import Path

import datalad.api as dlapi
import pytest
import yaml

SIMBIDS_VERSION = '0.0.3'
sys.path.append('..')
__location__ = op.dirname(op.abspath(__file__))
TEMPLATEFLOW_HOME = '/root/TEMPLATEFLOW_HOME_TEMP'
NOTEBOOKS_DIR = Path(__file__).parent.parent / 'notebooks'


@pytest.fixture(scope='session', autouse=True)
def _setup_before_all_tests():
    print('Setting up Slurm MaxJobs limit...')
    result = subprocess.run(
        ['sacctmgr', '-i', 'modify', 'user', 'root', 'set', 'MaxJobs=200'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'Failed to set Slurm MaxJobs limit:\n'
            f'Command failed with return code {result.returncode}\n'
            f'stderr: {result.stderr}\n'
            f'stdout: {result.stdout}'
        )
    print('Successfully set Slurm MaxJobs limit')


@pytest.fixture(scope='session')
def squeue_available():
    """Fixture to check if squeue is available and skip tests if not."""
    from babs.scheduler import check_slurm_available

    if not check_slurm_available():
        pytest.skip('squeue command not available')
    return True


@pytest.fixture(scope='session')
def simbids_apptainer_image():
    """
    Get the path of the simbids-raw-mri apptainer image.
    """
    if not op.exists(f'/singularity_images/simbids_{SIMBIDS_VERSION}.sif'):
        raise Exception(f'simbids_{SIMBIDS_VERSION}.sif not found!')
    return f'/singularity_images/simbids_{SIMBIDS_VERSION}.sif'


@pytest.fixture(scope='session')
def simbids_container_ds(simbids_apptainer_image, tmp_path_factory):
    """
    Create a datalad dataset of the simbids apptainer image

    Returns
    -------
    origin_container_ds: Path
        path to the created container datalad dataset
    """
    # create a temporary dir:
    origin_container_ds_path = tmp_path_factory.mktemp('my-container')
    # create a new datalad dataset for holding the container:
    container_ds_handle = dlapi.create(path=origin_container_ds_path)
    # add container image into this datalad dataset:
    container_ds_handle.containers_add(
        name=f'simbids-{SIMBIDS_VERSION.replace(".", "-")}',
        url=simbids_apptainer_image,
    )

    return origin_container_ds_path


def get_simbids_raw_bids_data(simbids_apptainer_image_path, bids_dir, session_type):
    """
    Use simbids-raw-mri to create some input data. The apptainer version included in
    the testing image is used for simbids.

    """
    simbids_yaml = (
        'ds004146_configs.yaml' if session_type == 'multi-session' else 'ds005237_configs.yaml'
    )

    proc = subprocess.run(
        [
            'apptainer',
            'exec',
            '-B',
            str(bids_dir),
            simbids_apptainer_image_path,
            'simbids-raw-mri',
            str(bids_dir),
            simbids_yaml,
        ],
        stdout=subprocess.PIPE,
    )
    proc.check_returncode()
    # Initialize datalad in the bids_dir, forcing it to accept original files
    ds_path = str(bids_dir.absolute() / 'simbids')
    assert op.exists(ds_path)
    dl_handle = dlapi.create(path=ds_path, force=True)
    dl_handle.save(path=ds_path, message='Add original files')
    return ds_path


@pytest.fixture(scope='session')
def bids_data_singlesession(simbids_apptainer_image, tmp_path_factory):
    """
    Use simbids-raw-mri to create some input data. The apptainer version included in
    the testing image is used for simbids.

    """
    bids_dir = tmp_path_factory.mktemp('BIDS')
    return get_simbids_raw_bids_data(simbids_apptainer_image, bids_dir, 'single-session')


@pytest.fixture(scope='session')
def bids_data_multisession(simbids_apptainer_image, tmp_path_factory):
    """
    Use simbids-raw-mri to create some input data. The apptainer version included in
    the testing image is used for simbids.

    """
    bids_dir = tmp_path_factory.mktemp('BIDS')
    return get_simbids_raw_bids_data(simbids_apptainer_image, bids_dir, 'multi-session')


def run_simbids_app_simulation(
    simbids_apptainer_image_path, bids_dir, output_dir, app_name, extra_args=None
):
    """
    Run simbids to get fmriprep derivatives where multiple sessions are present
    """
    app_output_dir = output_dir / app_name
    args = [
        'apptainer',
        'run',
        '-B',
        str(bids_dir),
        '-B',
        str(output_dir),
        simbids_apptainer_image_path,
        str(bids_dir),
        str(app_output_dir),
        'participant',
        '--bids-app',
        app_name,
        '-v',
        '-v',
    ]
    if extra_args:
        args.extend(extra_args)
    proc = subprocess.run(args, stdout=subprocess.PIPE)
    proc.check_returncode()
    return app_output_dir


def zip_derivatives(data_dir, output_dir, zip_root, zip_level):
    """
    Zip the derivatives at the specified level.
    """
    content_dir = data_dir / zip_root
    # Zip the dataset
    if zip_level == 'subject':
        for subject in content_dir.glob('sub-*'):
            zip_path = output_dir / f'{subject.name}_{zip_root}-1-0-1.zip'
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for file_path in subject.rglob('*'):
                    if file_path.is_file():
                        arcname = f'{zip_root}/{subject.name}/{file_path.relative_to(subject)}'
                        zf.write(file_path, arcname)

    elif zip_level == 'session':
        for subject in content_dir.glob('sub-*'):
            for session in subject.glob('ses-*'):
                zip_path = output_dir / f'{subject.name}_{session.name}_{zip_root}-1-0-1.zip'
                with zipfile.ZipFile(zip_path, 'w') as zf:
                    for file_path in session.rglob('*'):
                        if file_path.is_file():
                            arcname = (
                                f'{zip_root}/{subject.name}/{session.name}/'
                                f'{file_path.relative_to(session)}'
                            )
                            zf.write(file_path, arcname)
    else:
        raise ValueError(f'Invalid zip level: {zip_level}')


@pytest.fixture(scope='session')
def fmriprep_noses_derivative_files(
    simbids_apptainer_image, tmp_path_factory, bids_data_singlesession
):
    """
    Run simbids to get fmriprep derivatives where no sessions are present
    """
    output_dir = tmp_path_factory.mktemp('outputs')
    run_simbids_app_simulation(
        simbids_apptainer_image, bids_data_singlesession, output_dir, 'fmriprep'
    )
    return output_dir


@pytest.fixture(scope='session')
def fmriprep_multises_derivative_files(
    simbids_apptainer_image, bids_data_multisession, tmp_path_factory
):
    """
    Run simbids to get fmriprep derivatives where multiple sessions are present
    """
    output_dir = tmp_path_factory.mktemp('outputs')
    run_simbids_app_simulation(
        simbids_apptainer_image, bids_data_multisession, output_dir, 'fmriprep'
    )
    return output_dir


@pytest.fixture(scope='session')
def fmriprep_multises_derivative_files_zipped_at_session(
    fmriprep_multises_derivative_files, tmp_path_factory
):
    zipped_dir = tmp_path_factory.mktemp('zipped')
    zip_derivatives(fmriprep_multises_derivative_files, zipped_dir, 'fmriprep', 'session')
    zip_ds_handle = dlapi.create(path=zipped_dir, force=True)
    zip_ds_handle.save(path=zipped_dir, message='Add zipped derivatives')
    return zipped_dir


@pytest.fixture(scope='session')
def fmriprep_noses_derivative_files_zipped_at_subject(
    fmriprep_noses_derivative_files, tmp_path_factory
):
    zipped_dir = tmp_path_factory.mktemp('zipped')
    zip_derivatives(fmriprep_noses_derivative_files, zipped_dir, 'fmriprep', 'subject')
    zip_ds_handle = dlapi.create(path=zipped_dir, force=True)
    zip_ds_handle.save(path=zipped_dir, message='Add zipped derivatives')
    return zipped_dir


@pytest.fixture(scope='session')
def fmriprep_multises_derivative_files_zipped_at_subject(
    fmriprep_multises_derivative_files, tmp_path_factory
):
    zipped_dir = tmp_path_factory.mktemp('zipped')
    zip_derivatives(fmriprep_multises_derivative_files, zipped_dir, 'fmriprep', 'subject')
    zip_ds_handle = dlapi.create(path=zipped_dir, force=True)
    zip_ds_handle.save(path=zipped_dir, message='Add zipped derivatives')
    return zipped_dir


@pytest.fixture(scope='session')
def templateflow_home(tmp_path_factory):
    """
    Create a temporary directory for TemplateFlow home
    """
    templateflow_home = tmp_path_factory.mktemp('TEMPLATEFLOW_HOME')
    return templateflow_home


def get_config_simbids_path():
    """Get the path to the config_simbids.yaml file."""
    e2e_slurm_path = Path(__file__).parent / 'e2e-slurm' / 'container'
    return e2e_slurm_path / 'config_simbids.yaml'


def update_yaml_for_run(new_dir, babs_config_yaml, input_datasets_updates=None):
    """Copy a packaged yaml to a new_dir and make any included_files in new_dir.

    Parameters
    ----------
    new_dir : Path
        The directory to copy the yaml to.
    babs_config_yaml : str
        The name of the yaml file to copy.
    input_datasets_updates : dict
        A dictionary of input datasets to update in the yaml file.

    Returns
    -------
    new_yaml_path : Path
        The path to the new yaml file.
    """
    from babs.utils import read_yaml

    # Check if we're using the config_simbids.yaml file
    if babs_config_yaml == 'config_simbids.yaml':
        packaged_yaml_path = get_config_simbids_path()
    else:
        packaged_yaml_path = op.join(NOTEBOOKS_DIR, babs_config_yaml)

    new_yaml_path = new_dir / babs_config_yaml

    assert op.exists(packaged_yaml_path)
    babs_config = read_yaml(packaged_yaml_path)

    # Create temporary files for each of the imported files:
    for imported_file in babs_config.get('imported_files', []):
        # create a temporary file:
        fn_imported_file = new_dir / imported_file['original_path'].lstrip('/')
        fn_imported_file.parent.mkdir(parents=True, exist_ok=True)
        with open(fn_imported_file, 'w') as f:
            f.write('FAKE DATA')
        imported_file['original_path'] = fn_imported_file

    # Update input datasets if provided
    if input_datasets_updates:
        for ds_name, ds_path in input_datasets_updates.items():
            babs_config['input_datasets'][ds_name]['origin_url'] = ds_path

    yaml_data = babs_config.copy()
    for imported_file in yaml_data.get('imported_files', []):
        imported_file['original_path'] = str(imported_file['original_path'])

    # Only update these if not already present in the YAML
    if 'script_preamble' not in yaml_data:
        yaml_data['script_preamble'] = 'PATH=/opt/conda/envs/babs/bin:$PATH'

    # How much cluster resources it needs:
    if 'cluster_resources' not in yaml_data:
        yaml_data['cluster_resources'] = {'interpreting_shell': '/bin/bash'}

    if 'job_compute_space' not in yaml_data:
        yaml_data['job_compute_space'] = '/tmp'

    with open(new_yaml_path, 'w') as f:
        yaml.dump(yaml_data, f)

    return new_yaml_path


def get_babs_project(
    tmp_path_factory,
    templateflow_home,
    simbids_container_ds,
    bids_data,
    processing_level,
    return_path=True,
):
    """
    Create a BABS project set to process at the session-level
    """

    from babs.bootstrap import BABSBootstrap

    # Check the container dataset
    assert op.exists(simbids_container_ds)
    assert op.exists(op.join(simbids_container_ds, '.datalad/config'))

    # Check the bids input dataset:
    assert op.exists(bids_data)
    assert op.exists(op.join(bids_data, '.datalad/config'))

    # Preparation of env variable `TEMPLATEFLOW_HOME`:
    os.environ['TEMPLATEFLOW_HOME'] = str(templateflow_home)
    assert os.getenv('TEMPLATEFLOW_HOME')

    # Get the cli of `babs init`:
    project_base = tmp_path_factory.mktemp('project')
    project_root = project_base / 'my_babs_project'
    container_name = 'simbids-0-0-3'

    # Use config_simbids.yaml instead of eg_fmriprep
    config_simbids_path = get_config_simbids_path()
    container_config = update_yaml_for_run(
        project_base,
        config_simbids_path.name,
        {'BIDS': bids_data},
    )

    babs_bootstrap = BABSBootstrap(project_root=project_root)
    babs_bootstrap.babs_bootstrap(
        processing_level=processing_level,
        queue='slurm',
        container_ds=simbids_container_ds,
        container_name=container_name,
        container_config=container_config,
        initial_inclusion_df=None,
    )

    if return_path:
        return project_root
    else:
        return babs_bootstrap


@pytest.fixture
def babs_project_subjectlevel(
    tmp_path_factory, templateflow_home, simbids_container_ds, bids_data_singlesession
):
    return get_babs_project(
        tmp_path_factory,
        templateflow_home,
        simbids_container_ds,
        bids_data_singlesession,
        'subject',
        return_path=True,
    )


@pytest.fixture
def babs_project_subjectlevel_babsobject(
    tmp_path_factory, templateflow_home, simbids_container_ds, bids_data_singlesession
):
    return get_babs_project(
        tmp_path_factory,
        templateflow_home,
        simbids_container_ds,
        bids_data_singlesession,
        'subject',
        return_path=False,
    )


@pytest.fixture
def babs_project_sessionlevel(
    tmp_path_factory, templateflow_home, simbids_container_ds, bids_data_multisession
):
    return get_babs_project(
        tmp_path_factory,
        templateflow_home,
        simbids_container_ds,
        bids_data_multisession,
        'session',
        return_path=True,
    )


@pytest.fixture
def babs_project_sessionlevel_babsobject(
    tmp_path_factory, templateflow_home, simbids_container_ds, bids_data_multisession
):
    return get_babs_project(
        tmp_path_factory,
        templateflow_home,
        simbids_container_ds,
        bids_data_multisession,
        'session',
        return_path=False,
    )
