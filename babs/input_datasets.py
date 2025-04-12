"""This module is for input dataset(s)."""

import os

import pandas as pd

from babs.input_dataset import InputDataset


class InputDatasets:
    """Represent a collection of input datasets."""

    def __init__(self, processing_level, datasets):
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
            - path_in_babs: the path to where the input ds is cloned,
                relative to `analysis` folder
            - abs_path: the absolute path to the input ds
            - unzipped_path_containing_subject_dirs: the path to where the input data
                (for a sub or a ses) is,
                relative to `analysis` folder.
                If it's zipped ds, `unzipped_path_containing_subject_dirs` = `path_in_babs`/`name`,
                i.e., extra layer of folder got from unzipping
                If it's an unzipped ds, `unzipped_path_containing_subject_dirs` = `path_in_babs`
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
            dataset_config['processing_level'] = processing_level
            self._datasets.append(InputDataset(name=dataset_name, **dataset_config))
        self.initial_inclu_df = None
        self.processing_level = processing_level

    @property
    def num_ds(self):
        """Get the number of input datasets."""
        return len(self._datasets)

    def __iter__(self):
        """Make InputDatasets iterable over its datasets."""
        return iter(self._datasets)

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

    def validate_input_contents(self):
        """
        Parameters
        ----------
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        """

        for dataset in self._datasets:
            dataset.verify_input_status()

    def generate_inclusion_dataframe(self):
        """
        This is to get the list of subjects (and sessions) to analyze.

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
                dataset.generate_inclusion_dataframe() for dataset in self._datasets
            ]

            # Merge all these dataframes so that only rows present in each are kept:
            inclu_df = combine_inclusion_dataframes(initial_inclusion_dfs)

        return validate_sub_ses_processing_inclusion(inclu_df, self.processing_level)

    def as_records(self):
        """Return the input datasets as a list of dictionaries."""
        return [in_ds.as_dict() for in_ds in self._datasets]


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


def validate_sub_ses_processing_inclusion(processing_inclusion_file, processing_level):
    """
    Perform a basic sanity check on a subject/session inclusion file.

    Parameters
    ----------
    processing_inclusion_file: str, None or pd.DataFrame
        Path to the CSV file that lists the subject (and sessions) to analyze;
        or `None` if that CLI flag was not specified.
        or a pandas DataFrame if the inclusion list is provided inline
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis

    Returns
    -------
    initial_inclu_df: pandas DataFrame or None
        pandas DataFrame of the subject inclusion file, or `None` if
        `processing_inclusion_file` is`None`
    """
    if processing_inclusion_file is None:
        return None

    if isinstance(processing_inclusion_file, pd.DataFrame):
        initial_inclu_df = processing_inclusion_file
    elif not os.path.isfile(processing_inclusion_file):
        raise FileNotFoundError(
            '`processing_inclusion_file` does not exist!\n'
            f'    - Please check: {processing_inclusion_file}'
        )
    else:
        try:
            initial_inclu_df = pd.read_csv(processing_inclusion_file)
        except Exception as e:
            raise Exception(f'Error reading `{processing_inclusion_file}`:\n{e}')

    # Sanity check: there are expected column(s):
    if 'sub_id' not in initial_inclu_df.columns:
        raise Exception(f"There is no 'sub_id' column in `{processing_inclusion_file}`!")

    if processing_level == 'session' and 'ses_id' not in initial_inclu_df.columns:
        raise Exception(
            "There is no 'ses_id' column in `processing_inclusion_file`! "
            'It is expected as user requested to process data on a session-wise basis.'
        )

    # Sanity check: no repeated sub (or sessions):
    if processing_level == 'subject':
        # there should only be one occurrence per sub:
        if initial_inclu_df['sub_id'].duplicated().any():
            raise Exception("There are repeated 'sub_id' in `processing_inclusion_file`!")

    elif processing_level == 'session':
        # there should not be repeated combinations of `sub_id` and `ses_id`:
        if initial_inclu_df.duplicated(subset=['sub_id', 'ses_id']).any():
            raise Exception(
                "There are repeated combinations of 'sub_id' and 'ses_id' in "
                f'`{processing_inclusion_file}`!'
            )
    # Sort the initial included sub/ses list:
    sorting_indices = ['sub_id'] if processing_level == 'subject' else ['sub_id', 'ses_id']
    initial_inclu_df = initial_inclu_df.sort_values(by=sorting_indices).reset_index(drop=True)
    return initial_inclu_df
