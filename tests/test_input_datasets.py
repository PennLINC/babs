import datalad.api as dlapi
import pytest

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
