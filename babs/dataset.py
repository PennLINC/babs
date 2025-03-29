"""This module is for input dataset(s)."""

import os
import shutil
import warnings
import zipfile
from collections import defaultdict
from glob import glob
from importlib import resources
from pathlib import Path

import datalad.api as dlapi
import numpy as np
import pandas as pd
import yaml
from niworkflows.utils.testing import generate_bids_skeleton


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
            got by method `get_initial_inclu_df()`, based on `processing_inclusion_file`
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
                'relative_path',
                'abs_path',
                'data_parent_dir',
                'is_zipped',
            ],
        )

        # number of dataset(s):
        self.num_ds = self.df.shape[0]  # number of rows in `df`

        # change the `datasets` from dictionary to a pandas dataframe:
        for i_dset, (name, path) in enumerate(datasets.items()):
            self.df.loc[i_dset, 'name'] = name
            self.df.loc[i_dset, 'path_in'] = path
            self.df.loc[i_dset, 'relative_path'] = os.path.join(
                'inputs/data',
                self.df.loc[i_dset, 'name'],
            )

        # sanity check: input ds names should not be identical:
        if len(set(self.df['name'].tolist())) != self.num_ds:  # length of the set = number of ds
            raise Exception("There are identical names in input datasets' names!")

        # Initialize other attributes: ------------------------------
        self.initial_inclu_df = None

    def get_initial_inclu_df(self, processing_inclusion_file, processing_level):
        """
        Define attribute `initial_inclu_df`, a pandas DataFrame or None
            based on `processing_inclusion_file`
            single-session data: column of 'sub_id';
            multi-session data: columns of 'sub_id' and 'ses_id'

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
        self.initial_inclu_df = validate_processing_inclusion_file(
            processing_inclusion_file, processing_level
        )

        # Sort the initial included sub/ses list:
        sorting_indices = ['sub_id'] if processing_level == 'subject' else ['sub_id', 'ses_id']
        if self.initial_inclu_df is not None:
            self.initial_inclu_df = self.initial_inclu_df.sort_values(by=sorting_indices)
            self.initial_inclu_df = self.initial_inclu_df.reset_index(drop=True)

    def update_abs_paths(self, analysis_path):
        """
        This is the assign the absolute path to input dataset

        Parameters
        ----------
        analysis_path: str
            absolute path to the `analysis` folder.
        """

        # Create abs_path using pandas operations
        self.df['abs_path'] = self.df['relative_path'].apply(
            lambda x: os.path.join(analysis_path, x)
        )

    def determine_input_zipped_status(self):
        """
        This is to check if each input dataset is zipped, and assign `data_parent_dir`.
        If it's a zipped ds: `data_parent_dir` = `relative_path`/`name`,
                i.e., extra layer of folder got from unzipping
        If it's an unzipped ds, `data_parent_dir` = `relative_path`
        """

        # Determine if it's a zipped dataset, for each input ds:
        records = self.df.to_dict('records')
        for row in records:
            subject_child_files = glob(os.path.join(row['abs_path'], 'sub-*'))
            n_zipped_children = sum(1 for item in subject_child_files if item.endswith('.zip'))
            n_directory_children = sum(1 for item in subject_child_files if os.path.isdir(item))

            if n_zipped_children > 0 and n_directory_children == 0:
                # all are zip files
                row['is_zipped'] = True  # Ensure Python native boolean
                print(f"input dataset '{row['name']}' is considered as a zipped dataset.")
            elif n_directory_children > 0 and n_zipped_children == 0:
                # all are directories
                row['is_zipped'] = False  # Ensure Python native boolean
                print(f"input dataset '{row['name']}' is considered as an unzipped dataset.")
            elif n_zipped_children > 0 and n_directory_children > 0:
                # detect both
                row['is_zipped'] = True  # Ensure Python native boolean
                print(
                    f"input dataset '{row['name']}' has both zipped files and unzipped folders; "
                    'thus it is considered as a zipped dataset.'
                )
            else:
                # did not detect any of them...
                raise FileNotFoundError(
                    f'BABS did not detect any folder or zip file of `sub-*` '
                    f"in input dataset '{row['name']}'."
                )

        # Create new DataFrame from updated records
        self.df = pd.DataFrame(records)

        # Assign `data_parent_dir` using pandas operations
        self.df['data_parent_dir'] = np.where(
            self.df['is_zipped'],
            self.df.apply(lambda x: os.path.join(x['relative_path'], x['name']), axis=1),
            self.df['relative_path'],
        )

    def validate_zipped_input_contents(self, processing_level):
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

        if not any(self.df['is_zipped']):
            print('No zipped input dataset found. Skipping check...')
            return
        print(
            'Performing check for any zipped input dataset... '
            'Getting example zip file(s) to check...'
        )

        for idx, row in self.df.iterrows():
            if not row['is_zipped']:
                continue


def validate_zipped_input_contents(
    dataset_abs_path, root_dir_name, processing_level, included_subjects_df=None
):
    """ """
    zip_pattern = (
        f'sub-*_ses-*_{root_dir_name}*.zip'
        if processing_level == 'session'
        else f'sub-*_{root_dir_name}*.zip'
    )
    found_zip_files = sorted(glob(os.path.join(dataset_abs_path, zip_pattern)))

    if not found_zip_files:
        message = (
            f'In zipped input dataset {dataset_abs_path} '
            'no zip filename matches the pattern of '
            f"'{zip_pattern}'."
        )
        if processing_level == 'session' and sorted(
            glob(os.path.join(dataset_abs_path, f'sub-*_{root_dir_name}*.zip'))
        ):
            message += (
                ' There were, however, subject-level zip files found.'
                ' Was the input processed on a subject-wise basis?'
                ' If so, please use the `--processing-level subject` flag'
                ' during BABS initialization.'
            )
        raise FileNotFoundError(message)

    # Check to see if there is only one zip file per subject if processing on a subject-wise basis
    if processing_level == 'subject':
        zip_files_per_subject = defaultdict(int)
        for zip_file in found_zip_files:
            zip_files_per_subject[os.path.basename(zip_file).split('_')[0]] += 1
        if any(count > 1 for count in zip_files_per_subject.values()):
            raise ValueError(
                'There is more than one zip file per subject in the zipped input dataset.'
            )

    # Now that we know there is only one zip file per job, get an example zip file
    # so we can test that the folder structure is what we expect
    if included_subjects_df is None:
        # if not filter is provided, use the first zip file
        temp_zipfile = found_zip_files[0]
    else:
        # if a filter is provided, use the first row of the included_subjects_df
        # to find the zip file
        first_row = included_subjects_df.iloc[0]
        search = (
            {'sub_id': first_row['sub_id']}
            if processing_level == 'subject'
            else {'sub_id': first_row['sub_id'], 'ses_id': first_row['ses_id']}
        )
        temp_zipfile = glob(
            os.path.join(dataset_abs_path, f'{search["sub_id"]}_{search["ses_id"]}_*.zip')
        )
        if not temp_zipfile:
            raise Exception(f'No zip file found for query {search}')
        if len(temp_zipfile) > 1:
            raise Exception(f'Multiple zip files found for query {search}')
        temp_zipfile = temp_zipfile[0]

    temp_zipfilename = os.path.basename(temp_zipfile)

    # Get the file from datalad
    dlapi.get(path=temp_zipfile, dataset=dataset_abs_path)

    # Check folder structure
    with zipfile.ZipFile(temp_zipfile) as zf:
        zip_contents = zf.namelist()
        if not any(name.startswith(f'{root_dir_name}/') for name in zip_contents):
            warnings.warn(
                f'In input dataset (named "{root_dir_name}"), '
                f'there is no folder called "{root_dir_name}" in zipped '
                f'input file "{temp_zipfilename}". '
                'This may cause error when running BIDS App for this subject/session',
                stacklevel=2,
            )

    # Cleanup
    dlapi.drop(path=temp_zipfile, dataset=dataset_abs_path)


def validate_processing_inclusion_file(processing_inclusion_file, processing_level):
    """
    Validate the subject inclusion file.

    Parameters
    ----------
    processing_inclusion_file: str or None
        Path to the CSV file that lists the subject (and sessions) to analyze;
        or `None` if that CLI flag was not specified.
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

    if not os.path.isfile(processing_inclusion_file):
        raise FileNotFoundError(
            '`processing_inclusion_file` does not exist!\n'
            f'    - Please check: {processing_inclusion_file}'
        )
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

    return initial_inclu_df


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
