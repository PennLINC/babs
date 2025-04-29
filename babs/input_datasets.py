"""This module is for input dataset(s)."""

from babs.input_dataset import InputDataset, OutputDataset
from babs.utils import combine_inclusion_dataframes, validate_sub_ses_processing_inclusion


class InputDatasets:
    """Represent a collection of input datasets."""

    def __init__(self, processing_level, datasets):
        """Initialize `InputDatasets` class.

        Parameters
        ----------
        processing_level: {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        datasets: dict
            The section of the yaml file for input datasets.
            See `preparation_config_yaml_file.rst <preparation_config_yaml_file.rst>`_ for more.

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
        self._dataset_dict = {}

        # change the `datasets` from dictionary to a pandas dataframe:
        for dataset_name, dataset_config in datasets.items():
            dataset_config['processing_level'] = processing_level
            self._datasets.append(InputDataset(name=dataset_name, **dataset_config))
            self._dataset_dict[dataset_name] = self._datasets[-1]
        self.initial_inclu_df = None
        self.processing_level = processing_level

    def __getitem__(self, key):
        """Get the input dataset by name."""
        return self._dataset_dict[key]

    def __len__(self):
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


class OutputDatasets(InputDatasets):
    """Represent a collection of output datasets."""

    def __init__(self, input_datasets):
        """Initialize `OutputDatasets` class.

        Parameters
        ----------
        input_datasets: InputDatasets
            The input datasets to use for the output datasets.
        """
        self._datasets = []
        self._dataset_dict = {}

        # change the `datasets` from dictionary to a pandas dataframe:
        for in_ds in input_datasets:
            self._datasets.append(OutputDataset(in_ds))
            self._dataset_dict[in_ds.name] = self._datasets[-1]
        self.initial_inclu_df = None
        self.processing_level = input_datasets.processing_level
