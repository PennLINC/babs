"""This is to get data for pytests"""

import os.path as op

# import tempfile
import subprocess
import sys
import zipfile

import datalad.api as dlapi
import pytest

SIMBIDS_VERSION = '0.0.3'
sys.path.append('..')
__location__ = op.dirname(op.abspath(__file__))
TEMPLATEFLOW_HOME = '/root/TEMPLATEFLOW_HOME_TEMP'


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
