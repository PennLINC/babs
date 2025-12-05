import os
import zipfile
from pathlib import Path

import datalad.api as dlapi
import pandas as pd
import pytest
from niworkflows.utils.testing import generate_bids_skeleton

from babs.input_dataset import InputDataset, OutputDataset
from babs.input_datasets import InputDatasets


@pytest.mark.parametrize(
    ('session_type', 'processing_level'),
    [
        ('nosessions', 'subject'),
        ('sessions', 'subject'),
        ('nosessions', 'session'),
        ('sessions', 'session'),
    ],
)
def test_input_dataset_raw_bids(
    tmp_path_factory,
    bids_data_singlesession,
    bids_data_multisession,
    session_type,
    processing_level,
):
    """Test the InputDatasets class with a single session BIDS dataset."""

    if session_type == 'nosessions':
        origin_url = bids_data_singlesession
    elif session_type == 'sessions':
        origin_url = bids_data_multisession
    else:
        raise ValueError(f'Invalid session type: {session_type}')

    clone_path = tmp_path_factory.mktemp('cloned_input_dataset')
    dlapi.clone(origin_url, path=clone_path)

    # Be sure that it knows that it is not zipped
    input_dataset_incorrect = InputDataset(
        name='BIDS',
        origin_url=clone_path,
        # For testing, we just use the path on disk
        path_in_babs=str(clone_path.absolute())[1:],
        babs_project_analysis_path='/',
        is_zipped=True,
        processing_level=processing_level,
    )
    with pytest.raises(FileNotFoundError, match='no zip filename'):
        input_dataset_incorrect.verify_input_status()

    input_dataset = InputDataset(
        name='BIDS',
        origin_url=clone_path,
        path_in_babs=str(clone_path.absolute())[1:],
        babs_project_analysis_path='/',
        is_zipped=False,
        processing_level=processing_level,
    )

    # The only instance where we can't go further is if we need sessions and there aren't any
    if processing_level == 'session' and session_type == 'nosessions':
        with pytest.raises(FileNotFoundError, match=r'There is no `ses-\*` folder'):
            input_dataset.verify_input_status()
        return

    assert input_dataset.verify_input_status() is None

    # Get the inclusion dataframe, do some checks
    inclusion_df = input_dataset.generate_inclusion_dataframe()
    assert inclusion_df.shape[0] > 1
    assert 'sub_id' in inclusion_df
    if processing_level == 'session':
        assert 'ses_id' in inclusion_df
    else:
        assert 'ses_id' not in inclusion_df

    # Change the first sub_id to something that doesn't exist
    bad_df = inclusion_df.copy()
    bad_df.at[0, 'sub_id'] = 'sub-missing'
    with pytest.raises(
        FileNotFoundError, match='There is no `sub-missing` folder in input dataset BIDS'
    ):
        input_dataset.verify_input_status(bad_df)

    if processing_level == 'session':
        bad_df = inclusion_df.copy()
        bad_df.at[0, 'ses_id'] = 'ses-missing'
        with pytest.raises(FileNotFoundError, match='There is no `ses-missing` folder in "sub-'):
            input_dataset.verify_input_status(bad_df)


@pytest.mark.parametrize(
    ('session_type', 'processing_level'),
    [
        ('nosessions', 'subject'),
        ('sessions', 'subject'),
        ('sessions', 'session'),
    ],
)
def test_input_dataset_zipped_bids_derivatives(
    tmp_path_factory,
    fmriprep_multises_derivative_files_zipped_at_session,
    fmriprep_noses_derivative_files_zipped_at_subject,
    fmriprep_multises_derivative_files_zipped_at_subject,
    session_type,
    processing_level,
):
    """Test the InputDatasets class with a single session BIDS dataset."""

    if session_type == 'nosessions':
        origin_url = fmriprep_noses_derivative_files_zipped_at_subject
    elif session_type == 'sessions':
        if processing_level == 'session':
            origin_url = fmriprep_multises_derivative_files_zipped_at_session
        else:
            origin_url = fmriprep_multises_derivative_files_zipped_at_subject
    else:
        raise ValueError(f'Invalid session type: {session_type}')

    clone_path = tmp_path_factory.mktemp('cloned_input_dataset')
    dlapi.clone(origin_url, path=clone_path)

    input_dataset_incorrect = InputDataset(
        name='fmriprep',
        origin_url=clone_path,
        path_in_babs=str(clone_path.absolute())[1:],
        babs_project_analysis_path='/',
        is_zipped=False,
        unzipped_path_containing_subject_dirs='fmriprep',
        processing_level=processing_level,
    )
    with pytest.raises(FileNotFoundError, match=r'There are no `sub-\*` folders!'):
        input_dataset_incorrect.verify_input_status()

    input_dataset = InputDataset(
        name='fmriprep',
        origin_url=clone_path,
        path_in_babs=str(clone_path.absolute())[1:],
        babs_project_analysis_path='/',
        is_zipped=True,
        unzipped_path_containing_subject_dirs='fmriprep',
        processing_level=processing_level,
    )
    assert input_dataset.verify_input_status() is None

    # Get the inclusion dataframe, do some checks
    inclusion_df = input_dataset.generate_inclusion_dataframe()
    assert inclusion_df.shape[0] > 1
    assert 'sub_id' in inclusion_df


def test_input_datasets_subject_level(
    tmp_path_factory,
    bids_data_singlesession,
    fmriprep_noses_derivative_files_zipped_at_subject,
):
    """Test the InputDatasets class with two inputs."""

    zipped_clone_path = tmp_path_factory.mktemp('cloned_zipped_input_dataset')
    dlapi.clone(fmriprep_noses_derivative_files_zipped_at_subject, path=zipped_clone_path)
    unzipped_clone_path = tmp_path_factory.mktemp('cloned_unzipped_input_dataset')
    dlapi.clone(bids_data_singlesession, path=unzipped_clone_path)

    datasets = {
        'fmriprep': {
            'origin_url': zipped_clone_path,
            'path_in_babs': str(zipped_clone_path.absolute())[1:],
            'babs_project_analysis_path': '/',
            'is_zipped': True,
            'unzipped_path_containing_subject_dirs': 'fmriprep',
            'processing_level': 'subject',
        },
        'BIDS': {
            'origin_url': unzipped_clone_path,
            'path_in_babs': str(unzipped_clone_path.absolute())[1:],
            'babs_project_analysis_path': '/',
            'is_zipped': False,
            'processing_level': 'subject',
        },
    }

    input_datasets = InputDatasets(processing_level='subject', datasets=datasets)

    assert input_datasets.validate_input_contents() is None

    assert len(input_datasets) == 2
    assert input_datasets.processing_level == 'subject'
    inclu_df = input_datasets.generate_inclusion_dataframe()
    assert inclu_df.shape[0] == 2
    assert 'sub_id' in inclu_df
    assert 'ses_id' not in inclu_df


def test_input_datasets_session_level(
    tmp_path_factory,
    bids_data_multisession,
    fmriprep_multises_derivative_files_zipped_at_session,
):
    """Test the InputDatasets class with two inputs."""

    zipped_clone_path = tmp_path_factory.mktemp('cloned_zipped_input_dataset')
    dlapi.clone(fmriprep_multises_derivative_files_zipped_at_session, path=zipped_clone_path)
    unzipped_clone_path = tmp_path_factory.mktemp('cloned_unzipped_input_dataset')
    dlapi.clone(bids_data_multisession, path=unzipped_clone_path)

    datasets = {
        'fmriprep': {
            'origin_url': zipped_clone_path,
            'path_in_babs': str(zipped_clone_path.absolute())[1:],
            'babs_project_analysis_path': '/',
            'is_zipped': True,
            'unzipped_path_containing_subject_dirs': 'fmriprep',
        },
        'BIDS': {
            'origin_url': unzipped_clone_path,
            'path_in_babs': str(unzipped_clone_path.absolute())[1:],
            'babs_project_analysis_path': '/',
            'is_zipped': False,
        },
    }

    input_datasets = InputDatasets(processing_level='session', datasets=datasets)

    assert input_datasets.validate_input_contents() is None

    assert len(input_datasets) == 2
    assert input_datasets.processing_level == 'session'
    inclu_df = input_datasets.generate_inclusion_dataframe()
    assert inclu_df.shape[0] == 3
    assert 'sub_id' in inclu_df
    assert 'ses_id' in inclu_df


@pytest.mark.parametrize(
    ('session_type', 'processing_level'),
    [
        ('nosessions', 'subject'),
        ('sessions', 'session'),
        ('sessions', 'subject'),
    ],
)
def test_output_dataset(
    tmp_path_factory,
    fmriprep_multises_derivative_files_zipped_at_session,
    fmriprep_noses_derivative_files_zipped_at_subject,
    fmriprep_multises_derivative_files_zipped_at_subject,
    session_type,
    processing_level,
):
    """Test the OutputDatasets class with a single session BIDS dataset."""

    if session_type == 'nosessions':
        origin_url = fmriprep_noses_derivative_files_zipped_at_subject
    elif session_type == 'sessions':
        if processing_level == 'session':
            origin_url = fmriprep_multises_derivative_files_zipped_at_session
        else:
            origin_url = fmriprep_multises_derivative_files_zipped_at_subject
    else:
        raise ValueError(f'Invalid session type: {session_type}')

    clone_path = tmp_path_factory.mktemp('cloned_input_dataset')
    dlapi.clone(origin_url, path=clone_path)

    input_dataset = InputDataset(
        name='fmriprep',
        origin_url=clone_path,
        path_in_babs='',
        babs_project_analysis_path=str(clone_path.absolute()),
        is_zipped=True,
        unzipped_path_containing_subject_dirs='fmriprep',
        processing_level=processing_level,
    )
    assert input_dataset.verify_input_status() is None

    # Create an output dataset
    output_dataset = OutputDataset(input_dataset)

    assert output_dataset.verify_input_status() is None

    # Get the inclusion dataframe, do some checks
    inclusion_df = input_dataset.generate_inclusion_dataframe()
    assert inclusion_df.shape[0] > 1
    assert 'sub_id' in inclusion_df

    # check that the output dataset has the same inclusion dataframe
    assert output_dataset.generate_inclusion_dataframe().equals(inclusion_df)


def test_req_files_unzip_subj(tmp_path):
    """Test required_files filtering for non-zipped dataset at subject level."""
    # Create BIDS structure
    bids_config = {
        'dataset_description': {
            'Name': 'Test BIDS Dataset',
            'BIDSVersion': '1.0.0',
        },
        'sub-01': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
        'sub-02': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            # Missing func files
        },
        'sub-03': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
    }
    bids_dir = tmp_path / 'bids'
    generate_bids_skeleton(str(bids_dir), bids_config)

    input_dataset = InputDataset(
        name='BIDS',
        origin_url=str(bids_dir),
        path_in_babs=str(bids_dir),
        babs_project_analysis_path=str(bids_dir),
        is_zipped=False,
        processing_level='subject',
        required_files=['anat/*_T1w.nii*', 'func/*_bold.nii*'],
    )

    inclusion_df = input_dataset.generate_inclusion_dataframe()

    # Should only include sub-01 and sub-03 (both have required files)
    assert inclusion_df.shape[0] == 2
    assert set(inclusion_df['sub_id'].tolist()) == {'sub-01', 'sub-03'}
    assert 'sub-02' not in inclusion_df['sub_id'].tolist()


def test_req_files_unzip_ses(tmp_path):
    """Test required_files filtering for non-zipped dataset at session level."""
    # Create BIDS structure
    bids_config = {
        'dataset_description': {
            'Name': 'Test BIDS Dataset',
            'BIDSVersion': '1.0.0',
        },
        'sub-01': [
            {
                'session': 'ses-01',
                'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
                'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
            },
            {
                'session': 'ses-02',
                'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
                # Missing func files
            },
        ],
        'sub-02': [
            {
                'session': 'ses-01',
                'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
                'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
            },
        ],
    }
    bids_dir = tmp_path / 'bids'
    generate_bids_skeleton(str(bids_dir), bids_config)

    input_dataset = InputDataset(
        name='BIDS',
        origin_url=str(bids_dir),
        path_in_babs=str(bids_dir),
        babs_project_analysis_path=str(bids_dir),
        is_zipped=False,
        processing_level='session',
        required_files=['anat/*_T1w.nii*', 'func/*_bold.nii*'],
    )

    inclusion_df = input_dataset.generate_inclusion_dataframe()

    # Should only include sub-01/ses-01 and sub-02/ses-01
    assert inclusion_df.shape[0] == 2
    assert ('sub-01', 'ses-01') in [
        (row['sub_id'], row['ses_id']) for _, row in inclusion_df.iterrows()
    ]
    assert ('sub-02', 'ses-01') in [
        (row['sub_id'], row['ses_id']) for _, row in inclusion_df.iterrows()
    ]
    # sub-01/ses-02 should be excluded
    assert ('sub-01', 'ses-02') not in [
        (row['sub_id'], row['ses_id']) for _, row in inclusion_df.iterrows()
    ]


def test_req_files_zip_subj(tmp_path):
    """Test required_files filtering for zipped dataset at subject level."""
    # Create BIDS structure
    bids_config = {
        'dataset_description': {
            'Name': 'Test BIDS Dataset',
            'BIDSVersion': '1.0.0',
        },
        'sub-01': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
        'sub-02': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            # Missing func files
        },
        'sub-03': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
    }
    temp_bids_dir = tmp_path / 'temp_bids'
    generate_bids_skeleton(str(temp_bids_dir), bids_config)

    # Create zip files from the skeleton structure
    bids_dir = tmp_path / 'bids'
    bids_dir.mkdir()

    for sub_id in ['01', '02', '03']:
        sub_dir = temp_bids_dir / f'sub-{sub_id}'
        if sub_dir.exists():
            zip_path = bids_dir / f'sub-{sub_id}_BIDS-1-0-0.zip'
            with zipfile.ZipFile(zip_path, 'w') as zf:
                # Add all files from the subject directory
                for root, _, files in os.walk(sub_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = f'BIDS/{file_path.relative_to(temp_bids_dir)}'
                        zf.write(file_path, arcname)

    # Create a datalad dataset
    dlapi.create(path=str(bids_dir), force=True)

    input_dataset = InputDataset(
        name='BIDS',
        origin_url=str(bids_dir),
        path_in_babs=str(bids_dir),
        babs_project_analysis_path=str(bids_dir),
        is_zipped=True,
        processing_level='subject',
        required_files=['anat/*_T1w.nii*', 'func/*_bold.nii*'],
    )

    inclusion_df = input_dataset.generate_inclusion_dataframe()

    # Should only include sub-01 and sub-03
    assert inclusion_df.shape[0] == 2
    assert set(inclusion_df['sub_id'].tolist()) == {'sub-01', 'sub-03'}
    assert 'sub-02' not in inclusion_df['sub_id'].tolist()


def test_req_files_none(tmp_path):
    """Test that no filtering occurs when required_files is None or empty."""
    # Create BIDS structure
    bids_config = {
        'dataset_description': {
            'Name': 'Test BIDS Dataset',
            'BIDSVersion': '1.0.0',
        },
        'sub-01': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
        },
        'sub-02': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
        },
    }
    bids_dir = tmp_path / 'bids'
    generate_bids_skeleton(str(bids_dir), bids_config)

    input_dataset = InputDataset(
        name='BIDS',
        origin_url=str(bids_dir),
        path_in_babs=str(bids_dir),
        babs_project_analysis_path=str(bids_dir),
        is_zipped=False,
        processing_level='subject',
        required_files=None,  # No filtering
    )

    inclusion_df = input_dataset.generate_inclusion_dataframe()

    # Should include all subjects
    assert inclusion_df.shape[0] == 2
    assert set(inclusion_df['sub_id'].tolist()) == {'sub-01', 'sub-02'}


def test_req_files_init_list(tmp_path):
    """Test that required_files filtering works with initial inclusion list."""
    # Create BIDS structure
    bids_config = {
        'dataset_description': {
            'Name': 'Test BIDS Dataset',
            'BIDSVersion': '1.0.0',
        },
        'sub-01': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
        'sub-02': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            # Missing func files
        },
        'sub-03': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
    }
    bids_dir = tmp_path / 'bids'
    generate_bids_skeleton(str(bids_dir), bids_config)

    input_dataset = InputDataset(
        name='BIDS',
        origin_url=str(bids_dir),
        path_in_babs=str(bids_dir),
        babs_project_analysis_path=str(bids_dir),
        is_zipped=False,
        processing_level='subject',
        required_files=['anat/*_T1w.nii*', 'func/*_bold.nii*'],
    )

    # Create initial inclusion list with all three subjects
    initial_df = pd.DataFrame({'sub_id': ['sub-01', 'sub-02', 'sub-03']})

    inclusion_df = input_dataset.generate_inclusion_dataframe(initial_inclu_df=initial_df)

    # Should filter to only sub-01 and sub-03
    assert inclusion_df.shape[0] == 2
    assert set(inclusion_df['sub_id'].tolist()) == {'sub-01', 'sub-03'}
    assert 'sub-02' not in inclusion_df['sub_id'].tolist()


def test_req_files_input_ds(tmp_path):
    """Test required_files filtering in InputDatasets class."""
    # Create BIDS structure
    bids_config = {
        'dataset_description': {
            'Name': 'Test BIDS Dataset',
            'BIDSVersion': '1.0.0',
        },
        'sub-01': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
        'sub-02': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            # Missing func files
        },
    }
    bids_dir = tmp_path / 'bids'
    generate_bids_skeleton(str(bids_dir), bids_config)

    datasets = {
        'BIDS': {
            'origin_url': str(bids_dir),
            'path_in_babs': str(bids_dir),
            'babs_project_analysis_path': str(bids_dir),
            'is_zipped': False,
            'processing_level': 'subject',
            'required_files': ['anat/*_T1w.nii*', 'func/*_bold.nii*'],
        },
    }

    input_datasets = InputDatasets(processing_level='subject', datasets=datasets)
    inclusion_df = input_datasets.generate_inclusion_dataframe()

    # Should only include sub-01
    assert inclusion_df.shape[0] == 1
    assert inclusion_df.iloc[0]['sub_id'] == 'sub-01'


def test_req_files_input_ds_init(tmp_path):
    """Test required_files filtering with initial inclusion list in InputDatasets."""
    # Create BIDS structure
    bids_config = {
        'dataset_description': {
            'Name': 'Test BIDS Dataset',
            'BIDSVersion': '1.0.0',
        },
        'sub-01': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
        'sub-02': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            # Missing func files
        },
        'sub-03': {
            'anat': [{'suffix': 'T1w', 'extension': '.nii.gz'}],
            'func': [{'suffix': 'bold', 'task': 'rest', 'extension': '.nii.gz'}],
        },
    }
    bids_dir = tmp_path / 'bids'
    generate_bids_skeleton(str(bids_dir), bids_config)

    datasets = {
        'BIDS': {
            'origin_url': str(bids_dir),
            'path_in_babs': str(bids_dir),
            'babs_project_analysis_path': str(bids_dir),
            'is_zipped': False,
            'processing_level': 'subject',
            'required_files': ['anat/*_T1w.nii*', 'func/*_bold.nii*'],
        },
    }

    input_datasets = InputDatasets(processing_level='subject', datasets=datasets)

    # Set initial inclusion list with all three subjects
    initial_df = pd.DataFrame({'sub_id': ['sub-01', 'sub-02', 'sub-03']})
    input_datasets.set_inclusion_dataframe(initial_df, 'subject')

    inclusion_df = input_datasets.generate_inclusion_dataframe()

    # Should filter to only sub-01 and sub-03
    assert inclusion_df.shape[0] == 2
    assert set(inclusion_df['sub_id'].tolist()) == {'sub-01', 'sub-03'}
    assert 'sub-02' not in inclusion_df['sub_id'].tolist()
