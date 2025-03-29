"""Tests for babs.utils."""

import os
import os.path as op
import shutil
import zipfile
from unittest import mock

import datalad.api as dlapi
import pandas as pd
import pytest
import yaml
from niworkflows.utils.testing import generate_bids_skeleton

import babs.utils as utils
from babs.dataset import validate_zipped_input_contents


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


def create_mock_input_dataset(tmp_path_factory, bids_skeleton_yaml, processing_level, zipped):
    """Create a mock zipped input dataset with n_subjects, each with n_sessions.

    Parameters
    ----------
    tmp_path_factory : pytest.TempPathFactory
        The factory to create temporary directories.
    bids_skeleton_yaml : str
        The name of the YAML file containing the BIDS skeleton.
    processing_level : str
        The processing level ('subject' or 'session').
    zipped : bool
        Whether to zip the dataset.

    Returns
    -------
    input_dataset : Path
        The path containing the input dataset. Clone this datasets to
        simulate what happens in a BABS initialization.
    """
    input_dataset = tmp_path_factory.mktemp('input_dataset')
    qsiprep_dir = input_dataset / 'qsiprep'

    # Get the path to the YAML file in the tests directory
    project_root = op.dirname(op.dirname(op.abspath(__file__)))
    yaml_path = op.join(project_root, 'tests', bids_skeleton_yaml)

    with open(yaml_path) as f:
        bids_skeleton = yaml.safe_load(f)

    # Create the qsiprep directory first
    generate_bids_skeleton(qsiprep_dir, bids_skeleton)

    # Loop over all files in qsiprep_dir and if they are .nii.gz, write random data to them
    for file_path in qsiprep_dir.rglob('*.nii.gz'):
        with open(file_path, 'wb') as f:
            f.write(os.urandom(10 * 1024 * 1024))  # 10MB of random data

    # Zip the dataset
    if zipped:
        if processing_level == 'subject':
            for subject in qsiprep_dir.glob('sub-*'):
                zip_path = input_dataset / f'{subject.name}_qsiprep-1-0-1.zip'
                with zipfile.ZipFile(zip_path, 'w') as zf:
                    for file_path in subject.rglob('*'):
                        if file_path.is_file():
                            arcname = f'qsiprep/{subject.name}/{file_path.relative_to(subject)}'
                            zf.write(file_path, arcname)
        elif processing_level == 'session':
            for subject in qsiprep_dir.glob('sub-*'):
                for session in subject.glob('ses-*'):
                    zip_path = input_dataset / f'{subject.name}_{session.name}_qsiprep-1-0-1.zip'
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        for file_path in session.rglob('*'):
                            if file_path.is_file():
                                arcname = (
                                    f'qsiprep/{subject.name}/{session.name}/'
                                    f'{file_path.relative_to(session)}'
                                )
                                zf.write(file_path, arcname)
        shutil.rmtree(qsiprep_dir)
    else:
        input_dataset = qsiprep_dir

    # initialize a datalad dataset in input_dataset
    dlapi.create(path=input_dataset, force=True)

    # Datalad save the zip files
    dlapi.save(dataset=input_dataset, message='Add zip files')

    return input_dataset


@pytest.mark.parametrize(
    ('processing_level', 'bids_yaml_file'),
    [
        ('subject', 'multi_ses_qsiprep.yaml'),
        ('subject', 'no_ses_qsiprep.yaml'),
        ('session', 'multi_ses_qsiprep.yaml'),
        ('session', 'no_ses_qsiprep.yaml'),
    ],
)
def test_validate_zipped_input_contents_crosssectional(
    tmp_path_factory, bids_yaml_file, processing_level
):
    """Clone a mocked input dataset and test the validate_zipped_input_contents function."""
    # Clone the mocked input dataset
    clone_path = tmp_path_factory.mktemp('cloned_input_dataset')
    remote_input_dataset = create_mock_input_dataset(
        tmp_path_factory, bids_yaml_file, processing_level, True
    )
    dlapi.clone(remote_input_dataset, path=clone_path)

    # Print the directory structure
    print('\nDirectory structure:')
    print_tree(clone_path)

    # If there are multiple zip files per subject and processing_level is 'subject',
    # there should be an error because there is no way to know which zip file to use
    if bids_yaml_file == 'multi_ses_qsiprep.yaml' and processing_level == 'subject':
        with pytest.raises(ValueError, match='more than one zip file per subject'):
            validate_zipped_input_contents(clone_path, 'qsiprep', processing_level)
    elif bids_yaml_file == 'no_ses_qsiprep.yaml' and processing_level == 'session':
        with pytest.raises(ValueError, match='--processing-level subject'):
            validate_zipped_input_contents(clone_path, 'qsiprep', processing_level)
    else:
        validate_zipped_input_contents(clone_path, 'qsiprep', processing_level)


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
    utils.validate_unzipped_datasets(mock_input_ds, 'subject')

    # Test with processing_level = 'session' (should pass)
    utils.validate_unzipped_datasets(mock_input_ds, 'session')

    # Test with processing_level = 'invalid' (should fail)
    with pytest.raises(ValueError, match='invalid `processing_level`!'):
        utils.validate_unzipped_datasets(mock_input_ds, 'invalid')
