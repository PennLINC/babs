import glob
import os.path as op
import shutil
import tempfile
import warnings

import datalad.api as dlapi
import pandas as pd

from babs.utils import (
    get_immediate_subdirectories,
)


class InputDatasets:
    """This class is for input dataset(s)"""

    def __init__(self, datasets):
        """
        This is to initialize `InputDatasets` class.

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
            self.df.loc[i_dset, 'path_now_rel'] = op.join(
                'inputs/data', self.df.loc[i_dset, 'name']
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
            if op.exists(list_sub_file) is False:  # does not exist:
                raise Exception('`list_sub_file` does not exists! Please check: ' + list_sub_file)
            else:  # exists:
                self.initial_inclu_df = pd.read_csv(list_sub_file)
                self.validate_initial_inclu_df(processing_level)

    def validate_initial_inclu_df(self, processing_level):
        # Sanity check: there are expected column(s):
        if 'sub_id' not in list(self.initial_inclu_df.columns):
            raise Exception("There is no 'sub_id' column in `list_sub_file`!")
        if processing_level == 'session':
            if 'ses_id' not in list(self.initial_inclu_df.columns):
                raise Exception(
                    "There is no 'ses_id' column in `list_sub_file`!"
                    ' It is expected as user requested to process data on a session-wise basis.'
                )

        # Sanity check: no repeated sub (or sessions):
        if processing_level == 'subject':
            # there should only be one occurrence per sub:
            if len(set(self.initial_inclu_df['sub_id'])) != len(self.initial_inclu_df['sub_id']):
                raise Exception("There are repeated 'sub_id' in" + '`list_sub_file`!')
        elif processing_level == 'session':
            # there should not be repeated combinations of `sub_id` and `ses_id`:
            after_dropping = self.initial_inclu_df.drop_duplicates(
                subset=['sub_id', 'ses_id'], keep='first'
            )
            # ^^ remove duplications in specific cols, and keep the first occurrence
            if after_dropping.shape[0] < self.initial_inclu_df.shape[0]:
                print(
                    "Combinations of 'sub_id' and 'ses_id' in some rows are duplicated."
                    ' Will only keep the first occurrence...'
                )
                self.initial_inclu_df = after_dropping

        # Sort:
        if processing_level == 'subject':
            # sort:
            self.initial_inclu_df = self.initial_inclu_df.sort_values(by=['sub_id'])
            # reset the index, and remove the additional colume:
            self.initial_inclu_df = self.initial_inclu_df.reset_index().drop(columns=['index'])
        elif processing_level == 'session':
            self.initial_inclu_df = self.initial_inclu_df.sort_values(by=['sub_id', 'ses_id'])
            self.initial_inclu_df = self.initial_inclu_df.reset_index().drop(columns=['index'])

    def assign_path_now_abs(self, analysis_path):
        """
        This is the assign the absolute path to input dataset

        Parameters
        ----------
        analysis_path: str
            absolute path to the `analysis` folder.
        """

        for i in range(0, self.num_ds):
            self.df.loc[i, 'path_now_abs'] = op.join(analysis_path, self.df.loc[i, 'path_now_rel'])

    def check_if_zipped(self):
        """
        This is to check if each input dataset is zipped, and assign `path_data_rel`.
        If it's a zipped ds: `path_data_rel` = `path_now_rel`/`name`,
                i.e., extra layer of folder got from unzipping
        If it's an unzipped ds, `path_data_rel` = `path_now_rel`
        """

        # Determine if it's a zipped dataset, for each input ds:
        for i_ds in range(0, self.num_ds):
            temp_list = glob.glob(self.df.loc[i_ds, 'path_now_abs'] + '/sub-*')
            count_zip = 0
            count_dir = 0
            for i_temp in range(0, len(temp_list)):
                if op.isdir(temp_list[i_temp]):
                    count_dir += 1
                elif temp_list[i_temp][-4:] == '.zip':
                    count_zip += 1

            if (count_zip > 0) & (count_dir == 0):  # all are zip files:
                self.df.loc[i_ds, 'is_zipped'] = True
                print(
                    "input dataset '"
                    + self.df.loc[i_ds, 'name']
                    + "'"
                    + ' is considered as a zipped dataset.'
                )
            elif (count_dir > 0) & (count_zip == 0):  # all are directories:
                self.df.loc[i_ds, 'is_zipped'] = False
                print(
                    "input dataset '"
                    + self.df.loc[i_ds, 'name']
                    + "'"
                    + ' is considered as an unzipped dataset.'
                )
            elif (count_zip > 0) & (count_dir > 0):  # detect both:
                self.df.loc[i_ds, 'is_zipped'] = True  # consider as zipped
                print(
                    "input dataset '"
                    + self.df.loc[i_ds, 'name']
                    + "'"
                    + ' has both zipped files and unzipped folders;'
                    + " thus it's considered as a zipped dataset."
                )
            else:  # did not detect any of them...
                raise Exception(
                    'BABS did not detect any folder or zip file of `sub-*`'
                    " in input dataset '" + self.df.loc[i_ds, 'name'] + "'."
                )

        # Assign `path_data_rel`:
        for i_ds in range(0, self.num_ds):
            if self.df.loc[i_ds, 'is_zipped'] is True:  # zipped ds
                self.df.loc[i_ds, 'path_data_rel'] = op.join(
                    self.df.loc[i_ds, 'path_now_rel'], self.df.loc[i_ds, 'name']
                )
            else:  # unzipped ds:
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

        if True in list(self.df['is_zipped']):  # there is at least one dataset is zipped
            print(
                'Performing sanity check for any zipped input dataset...'
                ' Getting example zip file(s) to check...'
            )
        for i_ds in range(0, self.num_ds):
            if self.df.loc[i_ds, 'is_zipped'] is True:  # zipped ds
                # Sanity check #1: zip filename: ----------------------------------
                if processing_level == 'session':
                    # check if matches the pattern of `sub-*_ses-*_<input_ds_name>*.zip`:
                    temp_list = glob.glob(
                        self.df.loc[i_ds, 'path_now_abs']
                        + '/sub-*_ses-*_'
                        + self.df.loc[i_ds, 'name']
                        + '*.zip'
                    )
                    temp_list = sorted(temp_list)  # sort by name
                    if len(temp_list) == 0:  # did not find any matched
                        raise Exception(
                            'In zipped input dataset #'
                            + str(i_ds + 1)
                            + " (named '"
                            + self.df.loc[i_ds, 'name']
                            + "'),"
                            + ' no zip filename matches the pattern of'
                            + " 'sub-*_ses-*_"
                            + self.df.loc[i_ds, 'name']
                            + "*.zip'"
                        )
                elif processing_level == 'subject':
                    temp_list = glob.glob(
                        self.df.loc[i_ds, 'path_now_abs']
                        + '/sub-*_'
                        + self.df.loc[i_ds, 'name']
                        + '*.zip'
                    )
                    temp_list = sorted(temp_list)  # sort by name
                    if len(temp_list) == 0:  # did not find any matched
                        raise Exception(
                            'In zipped input dataset #'
                            + str(i_ds + 1)
                            + " (named '"
                            + self.df.loc[i_ds, 'name']
                            + "'),"
                            + ' no zip filename matches the pattern of'
                            + " 'sub-*_"
                            + self.df.loc[i_ds, 'name']
                            + "*.zip'"
                        )
                    # not to check below stuff anymore:
                    # # also check there should not be `_ses-*_`
                    # temp_list_2 = glob.glob(self.df["path_now_abs"][i_ds]
                    #                         + "/*_ses-*_*.zip")
                    # if len(temp_list_2) > 0:   # exists:
                    #     raise Exception("In zipped input dataset #" + str(i_ds + 1)
                    #                     + " (named '" + self.df["name"][i_ds] + "'),"
                    #                     + " as it's a subject dataset,"
                    #                     + " zip filename should not contain"
                    #                     + " '_ses-*_'")

                # Sanity check #2: foldername within zipped file: -------------------
                temp_zipfile = temp_list[0]  # try out the first zipfile
                temp_zipfilename = op.basename(temp_zipfile)
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
                        'In input dataset #'
                        + str(i_ds + 1)
                        + " (named '"
                        + self.df.loc[i_ds, 'name']
                        + "'), there is no folder called '"
                        + self.df.loc[i_ds, 'name']
                        + "' in zipped input file '"
                        + temp_zipfilename
                        + "'. This may cause error"
                        + ' when running BIDS App for this subject/session',
                        stacklevel=2,
                    )
