"""This module is for input dataset(s)."""

import os
import shutil
import tempfile
import warnings
from glob import glob

import datalad.api as dlapi
import pandas as pd

from babs.utils import get_immediate_subdirectories


class InputDatasets:
    """This class is for input dataset(s)"""

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
            - path_now_rel: the path to where the input ds is cloned, relative to `analysis` folder
            - path_now_abs: the absolute path to the input ds
            - path_data_rel: the path to where the input data (for a sub or a ses) is,
                relative to `analysis` folder.
                If it's zipped ds, `path_data_rel` = `path_now_rel`/`name`,
                i.e., extra layer of folder got from unzipping
                If it's an unzipped ds, `path_data_rel` = `path_now_rel`
            - is_zipped: True or False, is the input data zipped or not
        num_ds: int
            number of input dataset(s)
        initial_inclu_df: pandas DataFrame or None
            got by method `get_initial_inclu_df()`, based on `list_sub_file`
            Assign `None` for now, before calling that method
            See that method for more.
        """

        # About input dataset(s): ------------------------
        # create an empty pandas DataFrame:
        self.df = pd.DataFrame(
            None,
            index=list(range(len(datasets))),
            columns=[
                'name',
                'path_in',
                'path_now_rel',
                'path_now_abs',
                'path_data_rel',
                'is_zipped',
            ],
        )

        # number of dataset(s):
        self.num_ds = self.df.shape[0]  # number of rows in `df`

        # change the `datasets` from dictionary to a pandas dataframe:
        for i_dset, (name, path) in enumerate(datasets.items()):
            self.df.loc[i_dset, 'name'] = name
            self.df.loc[i_dset, 'path_in'] = path
            self.df.loc[i_dset, 'path_now_rel'] = os.path.join(
                'inputs/data',
                self.df.loc[i_dset, 'name'],
            )

        # sanity check: input ds names should not be identical:
        if len(set(self.df['name'].tolist())) != self.num_ds:  # length of the set = number of ds
            raise Exception("There are identical names in input datasets' names!")

        # Initialize other attributes: ------------------------------
        self.initial_inclu_df = None

    def get_initial_inclu_df(self, list_sub_file, processing_level):
        """
        Define attribute `initial_inclu_df`, a pandas DataFrame or None
            based on `list_sub_file`
            single-session data: column of 'sub_id';
            multi-session data: columns of 'sub_id' and 'ses_id'

        Parameters
        ----------
        list_sub_file: str or None
            Path to the CSV file that lists the subject (and sessions) to analyze;
            or `None` if that CLI flag was not specified.
            subject data: column of 'sub_id';
            session data: columns of 'sub_id' and 'ses_id'
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        """
        # Get the initial included sub/ses list from `list_sub_file` CSV:
        if list_sub_file is None:  # if not to specify that flag in CLI, it'll be `None`
            self.initial_inclu_df = None
        else:
            if not os.path.isfile(list_sub_file):
                raise FileNotFoundError(
                    f'`list_sub_file` does not exists! Please check: {list_sub_file}'
                )
            else:
                self.initial_inclu_df = pd.read_csv(list_sub_file)
                self.validate_initial_inclu_df(processing_level)

    def validate_initial_inclu_df(self, processing_level):
        # Sanity check: there are expected column(s):
        if 'sub_id' not in list(self.initial_inclu_df.columns):
            raise Exception("There is no 'sub_id' column in `list_sub_file`!")

        if processing_level == 'session' and 'ses_id' not in list(self.initial_inclu_df.columns):
            raise Exception(
                "There is no 'ses_id' column in `list_sub_file`! "
                'It is expected as user requested to process data on a session-wise basis.'
            )

        # Sanity check: no repeated sub (or sessions):
        if processing_level == 'subject':
            # there should only be one occurrence per sub:
            if len(set(self.initial_inclu_df['sub_id'])) != len(self.initial_inclu_df['sub_id']):
                raise Exception("There are repeated 'sub_id' in `list_sub_file`!")

        elif processing_level == 'session':
            # there should not be repeated combinations of `sub_id` and `ses_id`:
            after_dropping = self.initial_inclu_df.drop_duplicates(
                subset=['sub_id', 'ses_id'],
                keep='first',
            )
            if after_dropping.shape[0] < self.initial_inclu_df.shape[0]:
                print(
                    "Combinations of 'sub_id' and 'ses_id' in some rows are duplicated. "
                    'Will only keep the first occurrence...'
                )
                self.initial_inclu_df = after_dropping

        if processing_level == 'subject':
            self.initial_inclu_df = self.initial_inclu_df.sort_values(by=['sub_id'])
            self.initial_inclu_df = self.initial_inclu_df.reset_index(drop=True)
        elif processing_level == 'session':
            self.initial_inclu_df = self.initial_inclu_df.sort_values(by=['sub_id', 'ses_id'])
            self.initial_inclu_df = self.initial_inclu_df.reset_index(drop=True)

    def assign_path_now_abs(self, analysis_path):
        """
        This is the assign the absolute path to input dataset

        Parameters
        ----------
        analysis_path: str
            absolute path to the `analysis` folder.
        """

        for i_ds in range(self.num_ds):
            self.df.loc[i_ds, 'path_now_abs'] = os.path.join(
                analysis_path,
                self.df.loc[i_ds, 'path_now_rel'],
            )

    def check_if_zipped(self):
        """
        This is to check if each input dataset is zipped, and assign `path_data_rel`.
        If it's a zipped ds: `path_data_rel` = `path_now_rel`/`name`,
                i.e., extra layer of folder got from unzipping
        If it's an unzipped ds, `path_data_rel` = `path_now_rel`
        """

        # Determine if it's a zipped dataset, for each input ds:
        for i_ds in range(self.num_ds):
            temp_list = glob(os.path.join(self.df.loc[i_ds, 'path_now_abs'], 'sub-*'))
            count_zip = 0
            count_dir = 0
            for i_temp in range(len(temp_list)):
                if os.path.isdir(temp_list[i_temp]):
                    count_dir += 1
                elif temp_list[i_temp][-4:] == '.zip':
                    count_zip += 1

            if (count_zip > 0) & (count_dir == 0):
                # all are zip files
                self.df.loc[i_ds, 'is_zipped'] = True
                print(
                    f"input dataset '{self.df.loc[i_ds, 'name']}' "
                    'is considered as a zipped dataset.'
                )
            elif (count_dir > 0) & (count_zip == 0):
                # all are directories
                self.df.loc[i_ds, 'is_zipped'] = False
                print(
                    f"input dataset '{self.df.loc[i_ds, 'name']}' "
                    'is considered as an unzipped dataset.'
                )
            elif (count_zip > 0) & (count_dir > 0):
                # detect both
                self.df.loc[i_ds, 'is_zipped'] = True  # consider as zipped
                print(
                    f"input dataset '{self.df.loc[i_ds, 'name']}' "
                    'has both zipped files and unzipped folders; '
                    'thus it is considered as a zipped dataset.'
                )
            else:
                # did not detect any of them...
                raise FileNotFoundError(
                    'BABS did not detect any folder or zip file of `sub-*` '
                    f"in input dataset '{self.df.loc[i_ds, 'name']}'."
                )

        # Assign `path_data_rel`
        for i_ds in range(0, self.num_ds):
            if self.df.loc[i_ds, 'is_zipped']:  # zipped ds
                self.df.loc[i_ds, 'path_data_rel'] = os.path.join(
                    self.df.loc[i_ds, 'path_now_rel'],
                    self.df.loc[i_ds, 'name'],
                )
            else:
                self.df.loc[i_ds, 'path_data_rel'] = self.df.loc[i_ds, 'path_now_rel']

    def check_validity_zipped_input_dataset(self, processing_level):
        """
        This is to perform two sanity checks on each zipped input dataset:
        1) sanity check on the zip filename:
            if session: sub-*_ses-*_<input_ds_name>*.zip
            if subject: sub-*_<input_ds_name>*.zip
        2) sanity check to make sure the 1st level folder in zipfile
            is consistent to this input dataset's name;
            Only checks the first zipfile.

        Parameters
        ----------
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        container_name: str
            Name of the container
        """

        if any(self.df['is_zipped']):
            print(
                'Performing sanity check for any zipped input dataset... '
                'Getting example zip file(s) to check...'
            )

        for i_ds in range(self.num_ds):
            if self.df.loc[i_ds, 'is_zipped']:
                # Sanity check #1: zip filename:
                if processing_level == 'session':
                    # check if matches the pattern of `sub-*_ses-*_<input_ds_name>*.zip`:
                    temp_list = glob(
                        os.path.join(
                            self.df.loc[i_ds, 'path_now_abs'],
                            f'sub-*_ses-*_{self.df.loc[i_ds, "name"]}*.zip',
                        )
                    )
                    temp_list = sorted(temp_list)  # sort by name
                    if len(temp_list) == 0:  # did not find any matched
                        raise Exception(
                            f'In zipped input dataset #{i_ds + 1} '
                            f'(named "{self.df.loc[i_ds, "name"]}"), '
                            'no zip filename matches the pattern of '
                            f"'sub-*_ses-*_{self.df.loc[i_ds, 'name']}*.zip'"
                        )

                elif processing_level == 'subject':
                    temp_list = glob(
                        os.path.join(
                            self.df.loc[i_ds, 'path_now_abs'],
                            f'sub-*_{self.df.loc[i_ds, "name"]}*.zip',
                        )
                    )
                    temp_list = sorted(temp_list)  # sort by name
                    if len(temp_list) == 0:  # did not find any matched
                        raise Exception(
                            (
                                f'In zipped input dataset #{i_ds + 1} '
                                f'(named "{self.df.loc[i_ds, "name"]}"), '
                                'no zip filename matches the pattern of '
                                f"'sub-*_{self.df.loc[i_ds, 'name']}*.zip'"
                            ),
                            stacklevel=2,
                        )

                # Sanity check #2: foldername within zipped file: -------------------
                temp_zipfile = temp_list[0]  # try out the first zipfile
                temp_zipfilename = os.path.basename(temp_zipfile)
                dlapi.get(path=temp_zipfile, dataset=self.df.loc[i_ds, 'path_now_abs'])
                # unzip to a temporary folder and get the foldername
                temp_unzip_to = tempfile.mkdtemp()
                shutil.unpack_archive(temp_zipfile, temp_unzip_to)
                list_unzip_foldernames = get_immediate_subdirectories(temp_unzip_to)
                # remove the temporary folder:
                shutil.rmtree(temp_unzip_to)
                # `datalad drop` the zipfile:
                dlapi.drop(path=temp_zipfile, dataset=self.df.loc[i_ds, 'path_now_abs'])

                # check if there is folder named as ds's name:
                if self.df.loc[i_ds, 'name'] not in list_unzip_foldernames:
                    warnings.warn(
                        (
                            f'In input dataset #{i_ds + 1} (named "{self.df.loc[i_ds, "name"]}"), '
                            f'there is no folder called "{self.df.loc[i_ds, "name"]}" in zipped '
                            f'input file "{temp_zipfilename}". '
                            'This may cause error when running BIDS App for this subject/session'
                        ),
                        stacklevel=2,
                    )
