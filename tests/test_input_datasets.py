"""Tests for babs.utils."""

from unittest import mock

import datalad.api as dlapi
import pandas as pd
import pytest

from babs.input_datasets import (
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
