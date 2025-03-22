"""Module for handling input datasets in BABS."""

import os
import os.path as op

import pandas as pd

from .utils import (
    check_if_zipped,
    validate_type_session,
)


class InputDatasets:
    """Class for handling input datasets in BABS.

    Parameters
    ----------
    datasets : list of dict
        List of dictionaries containing input dataset information.
        Each dictionary should have keys:
        - name: str
            Name of the dataset
        - path_in: str
            Path to the input dataset
        - path_data_rel: str
            Relative path to the data directory
    """

    def __init__(self, datasets):
        """Initialize InputDatasets class.

        Parameters
        ----------
        datasets : list of dict
            List of dictionaries containing input dataset information.
        """
        self.df = pd.DataFrame(datasets)
        self.num_ds = len(datasets)
        self.is_zipped = None  # to be updated later

    def get_initial_inclu_df(self, list_sub_file, type_session):
        """Get initial inclusion DataFrame from list_sub_file.

        Parameters
        ----------
        list_sub_file : str
            Path to the list of subjects file
        type_session : str
            "multi-ses" or "single-ses"

        Returns
        -------
        pd.DataFrame
            DataFrame containing initial inclusion information
        """
        type_session = validate_type_session(type_session)
        if type_session == 'multi-ses':
            df = pd.read_csv(list_sub_file)
            # sanity check: there are expected column(s):
            self.validate_initial_inclu_df(type_session)
        else:  # single-ses
            df = pd.read_csv(list_sub_file, header=None)
            df.columns = ['sub']
        return df

    def validate_initial_inclu_df(self, type_session):
        """Validate the initial inclusion DataFrame.

        Parameters
        ----------
        type_session : str
            "multi-ses" or "single-ses"

        Raises
        ------
        Exception
            If the DataFrame is missing required columns
        """
        # Sanity check: there are expected column(s):
        if type_session == 'multi-ses':
            if not all(col in self.df.columns for col in ['sub', 'ses']):
                raise Exception(
                    'For multi-ses dataset, the list of subjects file must have'
                    ' columns "sub" and "ses".'
                )
        else:  # single-ses
            if 'sub' not in self.df.columns:
                raise Exception(
                    'For single-ses dataset, the list of subjects file must have column "sub".'
                )

    def assign_path_now_abs(self, analysis_path):
        """Assign absolute paths to the input datasets.

        Parameters
        ----------
        analysis_path : str
            Path to the analysis directory
        """
        for i_ds in range(0, self.num_ds):
            self.df.loc[i_ds, 'path_now_abs'] = op.join(
                analysis_path, self.df.loc[i_ds, 'path_now_rel']
            )

    def check_if_zipped(self):
        """Check if each input dataset is zipped.

        Updates the `is_zipped` attribute with a list of boolean values.
        """
        self.is_zipped = []
        for i_ds in range(0, self.num_ds):
            self.is_zipped.append(check_if_zipped(self.df.loc[i_ds, 'path_now_abs']))

    def check_validity_zipped_input_dataset(self, type_session):
        """Check validity of zipped input datasets.

        Parameters
        ----------
        type_session : str
            "multi-ses" or "single-ses"

        Raises
        ------
        Exception
            If the dataset structure is invalid
        """
        for i_ds in range(0, self.num_ds):
            if self.is_zipped[i_ds]:
                # check if the zip file exists:
                if not op.exists(self.df.loc[i_ds, 'path_now_abs']):
                    raise Exception(
                        'The zip file does not exist: ' + self.df.loc[i_ds, 'path_now_abs']
                    )
                # check if the zip file is valid:
                if not os.path.isfile(self.df.loc[i_ds, 'path_now_abs']):
                    raise Exception(
                        'The zip file is not a file: ' + self.df.loc[i_ds, 'path_now_abs']
                    )
                # check if the zip file is readable:
                if not os.access(self.df.loc[i_ds, 'path_now_abs'], os.R_OK):
                    raise Exception(
                        'The zip file is not readable: ' + self.df.loc[i_ds, 'path_now_abs']
                    )
