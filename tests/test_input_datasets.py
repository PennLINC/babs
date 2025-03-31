"""Tests for babs.utils."""

from unittest import mock

import datalad.api as dlapi
import pandas as pd
import pytest

from babs.input_datasets import (
    InputDatasets,
    create_mock_input_dataset,
    validate_unzipped_datasets,
    validate_zipped_input_contents,
)


def print_tree(path, prefix='', is_last=True):
    """Print a tree-like structure of a directory.

    Parameters
    ----------
    path : Path
        The path to print
    prefix : str
        The prefix to use for the current line
    is_last : bool
        Whether this is the last item in the current level
    """
    # Print the current directory/file
    print(f'{prefix}{"└── " if is_last else "├── "}{path.name}')

    # If it's a directory, print its contents
    if path.is_dir():
        # Update prefix for children
        new_prefix = prefix + ('    ' if is_last else '│   ')

        # Get all items in the directory
        items = sorted(path.iterdir())

        # Print each item
        for i, item in enumerate(items):
            is_last_item = i == len(items) - 1
            print_tree(item, new_prefix, is_last_item)


@pytest.mark.parametrize(
    ('multiple_sessions', 'zip_level', 'processing_level'),
    [
        (False, 'subject', 'subject'),
        (False, 'subject', 'session'),
        (True, 'subject', 'subject'),
        (True, 'subject', 'session'),
        (True, 'session', 'subject'),
        (True, 'session', 'session'),
    ],
)
def test_validate_zipped_input_contents(
    tmp_path_factory, multiple_sessions, zip_level, processing_level
):
    """Clone a mocked input dataset and test the validate_zipped_input_contents function."""
    # Clone the mocked input dataset
    remote_input_path = tmp_path_factory.mktemp('remote_input_dataset')
    clone_path = tmp_path_factory.mktemp('cloned_input_dataset')
    remote_input_dataset = create_mock_input_dataset(
        remote_input_path, multiple_sessions, zip_level
    )

    # make a clone with no data available locally
    dlapi.clone(remote_input_dataset, path=clone_path)

    # Print the directory structure
    print('\nDirectory structure:')
    print_tree(clone_path)

    # If there are multiple zip files per subject and processing_level is 'subject',
    # there should be an error because there is no way to know which zip file to use
    if zip_level == 'session' and processing_level == 'subject':
        with pytest.raises(ValueError, match='more than one zip file per subject'):
            validate_zipped_input_contents(clone_path, 'qsiprep', processing_level)
    elif zip_level == 'subject' and processing_level == 'session':
        with pytest.raises(FileNotFoundError, match='--processing-level subject'):
            validate_zipped_input_contents(clone_path, 'qsiprep', processing_level)
    else:
        validate_zipped_input_contents(clone_path, 'qsiprep', processing_level)


def test_validate_zipped_input_contents_with_session_include_list(tmp_path_factory):
    # Clone the mocked input dataset
    remote_input_path = tmp_path_factory.mktemp('remote_input_dataset')
    clone_path = tmp_path_factory.mktemp('cloned_input_dataset')

    remote_input_dataset = create_mock_input_dataset(
        remote_input_path, multiple_sessions=True, zip_level='session'
    )

    # make a clone with no data available locally
    dlapi.clone(remote_input_dataset, path=clone_path)

    df_has_session_include_list = pd.DataFrame(
        {
            'ses_id': ['ses-01', 'ses-02'],
            'sub_id': ['sub-01', 'sub-01'],
        }
    )

    # Check that session-wise inclusion works
    validate_zipped_input_contents(clone_path, 'qsiprep', 'session', df_has_session_include_list)
    with pytest.raises(ValueError, match='more than one zip file per subject'):
        validate_zipped_input_contents(
            clone_path, 'qsiprep', 'subject', df_has_session_include_list
        )

    # Check we get an error if the session isn't in the include list
    df_missing_session = pd.DataFrame(
        {
            'ses_id': ['ses-missing', 'ses-missing2'],
            'sub_id': ['sub-01', 'sub-01'],
        }
    )
    with pytest.raises(FileNotFoundError, match='No zip file found for inclusion-based query'):
        validate_zipped_input_contents(clone_path, 'qsiprep', 'session', df_missing_session)


def test_validate_unzipped_datasets_crosssectional(tmp_path_factory):
    """Test the validate_unzipped_datasets function."""
    # Mock up a dataset
    # The dataframe needs the following columns: is_zipped, abs_path, name
    zipped_dset = tmp_path_factory.mktemp(
        'test_validate_unzipped_datasets_crosssectional_zipped_dset'
    )
    unzipped_dset = tmp_path_factory.mktemp(
        'test_validate_unzipped_datasets_crosssectional_unzipped_dset'
    )

    # Write sub-01.zip to zipped dset
    (zipped_dset / 'sub-01.zip').touch()

    # Write sub-01 to unzipped dset
    (unzipped_dset / 'sub-01').mkdir()

    df = pd.DataFrame(
        {
            'is_zipped': [True, False],
            'abs_path': [zipped_dset, unzipped_dset],
            'name': ['zipped_dset', 'unzipped_dset'],
        }
    )
    # Create mock object with the dataframe as an attribute
    mock_input_ds = mock.Mock()
    mock_input_ds.df = df
    mock_input_ds.num_ds = df.shape[0]

    # Test with processing_level = 'subject' (should pass)
    validate_unzipped_datasets(mock_input_ds, 'subject')

    # Test with processing_level = 'session' (should fail)
    with pytest.raises(FileNotFoundError, match='there is no'):
        validate_unzipped_datasets(mock_input_ds, 'session')

    # Test with processing_level = 'invalid' (should fail)
    with pytest.raises(ValueError, match='invalid `processing_level`!'):
        validate_unzipped_datasets(mock_input_ds, 'invalid')


def test_validate_unzipped_datasets_longitudinal(tmp_path_factory):
    """Test the validate_unzipped_datasets function."""
    # Mock up a dataset
    # The dataframe needs the following columns: is_zipped, abs_path, name
    zipped_dset = tmp_path_factory.mktemp(
        'test_validate_unzipped_datasets_longitudinal_zipped_dset'
    )
    unzipped_dset = tmp_path_factory.mktemp(
        'test_validate_unzipped_datasets_longitudinal_unzipped_dset'
    )

    # Write sub-01.zip to zipped dset
    (zipped_dset / 'sub-01.zip').touch()

    # Write sub-01 to unzipped dset
    (unzipped_dset / 'sub-01').mkdir()
    (unzipped_dset / 'sub-01' / 'ses-01').mkdir()

    df = pd.DataFrame(
        {
            'is_zipped': [True, False],
            'abs_path': [
                zipped_dset,
                unzipped_dset,
            ],
            'name': ['zipped_dset', 'unzipped_dset'],
        }
    )
    # Create mock object with the dataframe as an attribute
    mock_input_ds = mock.Mock()
    mock_input_ds.df = df
    mock_input_ds.num_ds = len(df)

    # Test with processing_level = 'subject' (should pass)
    validate_unzipped_datasets(mock_input_ds, 'subject')

    # Test with processing_level = 'session' (should pass)
    validate_unzipped_datasets(mock_input_ds, 'session')

    # Test with processing_level = 'invalid' (should fail)
    with pytest.raises(ValueError, match='invalid `processing_level`!'):
        validate_unzipped_datasets(mock_input_ds, 'invalid')


@pytest.mark.parametrize(
    ('multiple_sessions', 'zip_level', 'processing_level'),
    [
        (False, 'subject', 'subject'),
        (True, 'subject', 'subject'),
        (True, 'session', 'session'),
    ],
)
def test_get_list_sub_ses(tmp_path_factory, multiple_sessions, zip_level, processing_level):
    """Test the get_list_sub_ses method of InputDatasets class."""
    # Create a mock input dataset
    remote_input_path = tmp_path_factory.mktemp('remote_input_dataset')
    remote_input_dataset = create_mock_input_dataset(
        remote_input_path, multiple_sessions, zip_level
    )

    # Create an InputDatasets object
    input_ds = InputDatasets({'qsiprep': remote_input_dataset})
    input_ds.df['is_zipped'] = [zip_level != 'none']
    input_ds.df['abs_path'] = [remote_input_dataset]

    result = input_ds.generate_inclusion_dataframe(processing_level)

    # Verify the result is a DataFrame with the correct columns
    assert isinstance(result, pd.DataFrame)
    assert 'sub_id' in result.columns
    if processing_level == 'session':
        assert 'ses_id' in result.columns
    else:
        assert 'ses_id' not in result.columns

    # Verify the data format
    assert all(result['sub_id'].str.startswith('sub-'))
    if processing_level == 'session':
        assert all(result['ses_id'].str.startswith('ses-'))


@pytest.mark.get_list_sub_ses
def test_get_list_sub_ses_with_inclusion_list(tmp_path_factory):
    """Test the get_list_sub_ses method with inclusion lists."""
    # Create a mock input dataset
    remote_input_path = tmp_path_factory.mktemp('remote_input_dataset')
    remote_input_dataset = create_mock_input_dataset(
        remote_input_path, multiple_sessions=True, zip_level='subject'
    )

    # Create an InputDatasets object
    input_ds = InputDatasets({'qsiprep': remote_input_dataset})
    input_ds.df['is_zipped'] = [True]
    input_ds.df['abs_path'] = [remote_input_dataset]

    # Test with valid subject-level inclusion list
    input_ds.initial_inclu_df = pd.DataFrame({'sub_id': ['sub-01', 'sub-ABC']})
    result = input_ds.generate_inclusion_dataframe('subject')
    assert set(result['sub_id']) == {'sub-01', 'sub-ABC'}

    # Test with valid session-level inclusion list
    input_ds.initial_inclu_df = pd.DataFrame(
        {'sub_id': ['sub-01', 'sub-01'], 'ses_id': ['ses-01', 'ses-02']}
    )
    result = input_ds.generate_inclusion_dataframe('session')
    assert set(result['sub_id']) == {'sub-01'}
    assert set(result['ses_id']) == {'ses-01', 'ses-02'}

    # Test with invalid subject-level inclusion list (duplicate subjects)
    input_ds.initial_inclu_df = pd.DataFrame({'sub_id': ['sub-01', 'sub-01']})
    with pytest.raises(Exception, match="There are repeated 'sub_id' in"):
        input_ds.generate_inclusion_dataframe('subject')

    # Test with invalid session-level inclusion list (missing ses_id column)
    input_ds.initial_inclu_df = pd.DataFrame({'sub_id': ['sub-01']})
    with pytest.raises(Exception, match="There is no 'ses_id' column"):
        input_ds.generate_inclusion_dataframe('session')

    # Test with invalid session-level inclusion list (duplicate subject-session pairs)
    input_ds.initial_inclu_df = pd.DataFrame(
        {'sub_id': ['sub-01', 'sub-01'], 'ses_id': ['ses-01', 'ses-01']}
    )
    with pytest.raises(
        Exception, match="There are repeated combinations of 'sub_id' and 'ses_id'"
    ):
        input_ds.generate_inclusion_dataframe('session')
