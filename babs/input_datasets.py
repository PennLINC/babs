"""This module is for input dataset(s)."""

import os
import shutil
import zipfile
from importlib import resources
from pathlib import Path

import datalad.api as dlapi
import pandas as pd
import yaml
from niworkflows.utils.testing import generate_bids_skeleton

from babs.input_dataset import InputDataset
from babs.utils import validate_sub_ses_processing_inclusion


class InputDatasets:
    """Represent a collection of input datasets."""

    def __init__(self, datasets):
        """Initialize `InputDatasets` class.

        Parameters
        ----------
        datasets : dict
            see CLI `babs init --datasets` for more

        Attributes
        ----------
        df: pandas DataFrame
            includes necessary information:
            - name: str: a name the user gives
            - path_in: str: the path to the input ds
            - relative_path: the path to where the input ds is cloned,
                relative to `analysis` folder
            - abs_path: the absolute path to the input ds
            - data_parent_dir: the path to where the input data (for a sub or a ses) is,
                relative to `analysis` folder.
                If it's zipped ds, `data_parent_dir` = `relative_path`/`name`,
                i.e., extra layer of folder got from unzipping
                If it's an unzipped ds, `data_parent_dir` = `relative_path`
            - is_zipped: True or False, is the input data zipped or not
        num_ds: int
            number of input dataset(s)
        initial_inclu_df: pandas DataFrame or None
            got by method `set_inclusion_dataframe()`, based on `processing_inclusion_file`
            Assign `None` for now, before calling that method
            See that method for more.
        """

        self._datasets = []

        # change the `datasets` from dictionary to a pandas dataframe:
        for dataset_name, dataset_config in datasets.items():
            self._datasets.append(InputDataset(name=dataset_name, **dataset_config))

        # sanity check: input ds names should not be identical:
        if len(set(self.df['name'].tolist())) != self.num_ds:  # length of the set = number of ds
            raise Exception("There are identical names in input datasets' names!")

        # Initialize other attributes: ------------------------------
        self.initial_inclu_df = None

    @property
    def num_ds(self):
        """Get the number of input datasets."""
        return len(self._datasets)

    def set_inclusion_dataframe(self, processing_inclusion_file, processing_level):
        """
        Set the inclusion dataframe, validate it and sort it.

        Parameters
        ----------
        processing_inclusion_file: str or None
            Path to the CSV file that lists the subject (and sessions) to analyze;
            or `None` if that CLI flag was not specified.
            subject data: column of 'sub_id';
            session data: columns of 'sub_id' and 'ses_id'
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        """
        # Get the initial included sub/ses list from `processing_inclusion_file` CSV:
        self.initial_inclu_df = validate_sub_ses_processing_inclusion(
            processing_inclusion_file, processing_level
        )

    def update_abs_paths(self, analysis_path):
        """
        This is to set the BABS project analysis path for each input dataset.

        Parameters
        ----------
        analysis_path: str
            absolute path to the `analysis` folder.
        """

        # Create abs_path using pandas operations
        for dataset in self._datasets:
            dataset.set_babs_project_analysis_path(analysis_path)

    def validate_input_contents(self, processing_level):
        """
        Parameters
        ----------
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        """

        for dataset in self._datasets:
            dataset.verify_input_zipped_status(processing_level)

    def generate_inclusion_dataframe(self, processing_level):
        """
        This is to get the list of subjects (and sessions) to analyze.

        Parameters
        ----------
        processing_level: {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis

        Returns
        -------
        inclu_df: pandas DataFrame
            A pandas DataFrame with the subjects and sessions available in the input dataset
        """

        if self.initial_inclu_df is not None:
            print('Using the subjects (sessions) provided in the initial inclusion list.')
            inclu_df = self.initial_inclu_df
        else:
            initial_inclusion_dfs = [
                dataset.generate_inclusion_dataframe(processing_level)
                for dataset in self._datasets
            ]

            # Merge all these dataframes so that only rows present in each are kept:
            inclu_df = combine_inclusion_dataframes(initial_inclusion_dfs)

        return validate_sub_ses_processing_inclusion(inclu_df, processing_level)


def create_mock_input_dataset(output_dir, multiple_sessions, zip_level):
    """Create a mock zipped input dataset with n_subjects, each with n_sessions.

    Parameters
    ----------
    output_dir : Pathlike
        The path to the output directory.
    multiple_sessions : bool
        Whether to create a BIDS dataset with multiple sessions.
    zip_level : {'subject', 'session', 'none'}
        The level at which to zip the dataset.

    Returns
    -------
    input_dataset : Path
        The path containing the input dataset. Clone this datasets to
        simulate what happens in a BABS initialization.
    """
    input_dataset = Path(output_dir)
    qsiprep_dir = input_dataset / 'qsiprep'

    # Get the YAML file from the package
    bids_skeleton_yaml = 'multi_ses_qsiprep.yaml' if multiple_sessions else 'no_ses_qsiprep.yaml'
    with resources.files('babs.bids_skeletons').joinpath(bids_skeleton_yaml).open() as f:
        bids_skeleton = yaml.safe_load(f)

    # Create the qsiprep directory first
    generate_bids_skeleton(qsiprep_dir, bids_skeleton)

    # Loop over all files in qsiprep_dir and if they are .nii.gz, write random data to them
    for file_path in qsiprep_dir.rglob('*.nii.gz'):
        with open(file_path, 'wb') as f:
            f.write(os.urandom(10 * 1024 * 1024))  # 10MB of random data

    # Zip the dataset
    if zip_level == 'subject':
        for subject in qsiprep_dir.glob('sub-*'):
            zip_path = input_dataset / f'{subject.name}_qsiprep-1-0-1.zip'
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for file_path in subject.rglob('*'):
                    if file_path.is_file():
                        arcname = f'qsiprep/{subject.name}/{file_path.relative_to(subject)}'
                        zf.write(file_path, arcname)
        shutil.rmtree(qsiprep_dir)
    elif zip_level == 'session':
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


def combine_inclusion_dataframes(initial_inclusion_dfs):
    """Combine multiple inclusion DataFrames into a single DataFrame.

    Parameters
    ----------
    initial_inclusion_dfs : list of pandas DataFrame
        List of DataFrames containing subject and session information

    Returns
    -------
    combined_df : pandas DataFrame
        A DataFrame containing only the rows that are present in all input DataFrames
    """
    if not initial_inclusion_dfs:
        raise ValueError('No DataFrames provided')

    if len(initial_inclusion_dfs) == 1:
        return initial_inclusion_dfs[0]

    # Start with the first DataFrame
    combined_df = initial_inclusion_dfs[0]

    # Iteratively join with remaining DataFrames
    for df in initial_inclusion_dfs[1:]:
        combined_df = pd.merge(combined_df, df, how='inner')

    return combined_df
