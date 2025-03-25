"""Tests for babs.utils."""

from unittest import mock

import pandas as pd
import pytest

import babs.utils as utils


def test_validate_unzipped_datasets_crosssectional(tmp_path_factory):
    """Test the validate_unzipped_datasets function."""
    # Mock up a dataset
    # The dataframe needs the following columns: is_zipped, path_now_abs, name
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
            'path_now_abs': [zipped_dset, unzipped_dset],
            'name': ['zipped_dset', 'unzipped_dset'],
        }
    )
    # Create mock object with the dataframe as an attribute
    mock_input_ds = mock.Mock()
    mock_input_ds.df = df
    mock_input_ds.num_ds = df.shape[0]

    # Test with processing_level = 'subject' (should pass)
    utils.validate_unzipped_datasets(mock_input_ds, 'subject')

    # Test with processing_level = 'session' (should fail)
    with pytest.raises(FileNotFoundError, match='there is no'):
        utils.validate_unzipped_datasets(mock_input_ds, 'session')

    # Test with processing_level = 'invalid' (should fail)
    with pytest.raises(ValueError, match='invalid `processing_level`!'):
        utils.validate_unzipped_datasets(mock_input_ds, 'invalid')


def test_validate_unzipped_datasets_longitudinal(tmp_path_factory):
    """Test the validate_unzipped_datasets function."""
    # Mock up a dataset
    # The dataframe needs the following columns: is_zipped, path_now_abs, name
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
            'path_now_abs': [
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
    utils.validate_unzipped_datasets(mock_input_ds, 'subject')

    # Test with processing_level = 'session' (should pass)
    utils.validate_unzipped_datasets(mock_input_ds, 'session')

    # Test with processing_level = 'invalid' (should fail)
    with pytest.raises(ValueError, match='invalid `processing_level`!'):
        utils.validate_unzipped_datasets(mock_input_ds, 'invalid')
