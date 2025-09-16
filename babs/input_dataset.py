"""This module is for input dataset(s)."""

from collections import defaultdict
from glob import glob
import fnmatch
import os
import re
import subprocess
import warnings
import zipfile

import datalad.api as dlapi
import pandas as pd



class InputDataset:
    """Represent an input dataset."""

    _is_input_dataset = True

    def __init__(
        self,
        name,
        origin_url,
        path_in_babs,
        is_zipped,
        unzipped_path_containing_subject_dirs=None,
        required_files=None,
        processing_level=None,
        babs_project_analysis_path=None,
    ):
        """Initialize `InputDataset` class.

        Parameters
        ----------
        name: str
            name of the input dataset
        origin_url: str
            origin URL of the input dataset
        path_in_babs: str
            relative path to the input dataset in the BABS directory
        is_zipped: bool or str
            whether the input dataset is zipped. Can be a boolean or string ('true'/'false')
        unzipped_path_containing_subject_dirs: str or None
            when unzipped, this string precedes the subject directories
        required_files: list of str or None
            list of required files in the input dataset
        processing_level: {'subject', 'session'} or None
            whether processing is done on a subject-wise or session-wise basis
        babs_project_analysis_path: str or None
            path to the BABS project analysis directory
        """
        self.name = name
        self.origin_url = origin_url
        self.path_in_babs = path_in_babs
        # Convert string 'true'/'false' to boolean if needed
        if isinstance(is_zipped, str):
            self.is_zipped = is_zipped.lower() == 'true'
        else:
            self.is_zipped = bool(is_zipped)
        self.required_files = required_files
        if processing_level not in ['subject', 'session']:
            raise ValueError('invalid `processing_level`!')
        self.processing_level = processing_level
        self._babs_project_analysis_path = babs_project_analysis_path

        # If not specified, set this based on whether the inputs are zipped
        if unzipped_path_containing_subject_dirs in (None, 'None'):
            if self.is_zipped:
                unzipped_path_containing_subject_dirs = f'{self.path_in_babs}/{self.name}'
            else:
                unzipped_path_containing_subject_dirs = self.path_in_babs

        self.unzipped_path_containing_subject_dirs = unzipped_path_containing_subject_dirs

    def set_babs_project_analysis_path(self, babs_project_analysis_path):
        """Set the BABS project analysis path."""
        self._babs_project_analysis_path = babs_project_analysis_path

    @property
    def babs_project_analysis_path(self):
        """Get the path to this input dataset in the BABS project analysis directory."""
        if self._babs_project_analysis_path is None:
            raise ValueError('BABS project analysis path is not set.')
        if self._is_input_dataset:
            return os.path.join(self._babs_project_analysis_path, self.path_in_babs)
        else:
            # If this is an output dataset, the path is the analysis directory
            return self._babs_project_analysis_path

    @property
    def is_up_to_date(self):
        """Check if the input dataset is up to date."""
        in_babs_ds = dlapi.Dataset(self.babs_project_analysis_path)
        babs_sha = in_babs_ds.repo.get_hexsha()

        origin_ds = dlapi.Dataset(self.origin_url)
        origin_sha = origin_ds.repo.get_hexsha()

        if not babs_sha == origin_sha:
            print(f'Input dataset {self.name} is not up to date.')
            print(f'BABS SHA: {babs_sha}')
            print(f'Origin SHA: {origin_sha}')
        return babs_sha == origin_sha

    def verify_input_status(self, inclusion_df=None):
        """
        Verify that this dataset is indeed zipped or unzipped, and check that
        the inclusion dataframe contains subjects/sessions that exist in this dataset.

        Parameters
        ----------
        inclusion_df: pandas DataFrame or None
            pandas DataFrame of the subject/session inclusion file, or `None`.
            If `None`, a random subject/session will be used to check the input dataset.
        """
        if self.is_zipped:
            validate_zipped_input_contents(
                self.babs_project_analysis_path,
                self.name,
                self.processing_level,
                inclusion_df,
            )
        else:
            validate_nonzipped_input_contents(
                self.babs_project_analysis_path,
                self.name,
                self.processing_level,
                inclusion_df,
            )

    def generate_inclusion_dataframe(self, initial_inclu_df=None):
        """
        This is to get the list of subjects (and sessions) to analyze.

        Parameters
        ----------
        processing_level: {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        initial_inclu_df: pandas DataFrame or None
            pandas DataFrame of the subject/session inclusion file, or `None`.
            If `None`, the inclusion list will be generated from the input dataset.

        Returns
        -------
        inclu_df: pandas DataFrame
            A pandas DataFrame with the subjects and sessions available in the input dataset
        """

        if initial_inclu_df is not None:
            print('Using the subjects (sessions) provided in the initial inclusion list.')
            inclu_df = initial_inclu_df
        else:
            if self._is_input_dataset:
                print(
                    'Did not provide an initial inclusion list.'
                    f' Examining input dataset {self.name}'
                    ' to get an initial inclusion list.'
                )

            if self.is_zipped:
                inclu_df = self._get_sub_ses_from_zipped_input()
            else:
                inclu_df = self._get_sub_ses_from_nonzipped_input()

        # Apply required_files filtering, if specified
        inclu_df = self._filter_inclusion_by_required_files(inclu_df)

        if inclu_df.empty:
            # Return an empty dataframe with only the inclusion columns
            if self.processing_level == 'session':
                columns = ['sub_id', 'ses_id']
            else:
                columns = ['sub_id']
            return pd.DataFrame(columns=columns)

        return inclu_df

    def _filter_inclusion_by_required_files(self, inclu_df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the inclusion dataframe using the dataset's required_files patterns, if any.

        For non-zipped datasets, required file patterns are treated as paths relative to the
        subject/session directory and matched using glob semantics.

        For zipped datasets, required file patterns are matched against the zip filename(s).

        Parameters
        ----------
        inclu_df : pd.DataFrame
            DataFrame containing at least a 'sub_id' column, and optionally 'ses_id'.

        Returns
        -------
        pd.DataFrame
            Filtered inclusion dataframe.
        """
        if not self.required_files:
            return inclu_df
        if inclu_df.empty:
            return inclu_df

        # Normalize patterns to strings
        required_patterns = [str(pat) for pat in self.required_files if pat is not None]
        if not required_patterns:
            return inclu_df

        keep_indices = []

        if not self.is_zipped:
            # Try to use git to list tracked files for robust matching without fetching content
            tracked_files: list[str] | None = None
            try:
                proc = subprocess.run(
                    ['git', 'ls-files'],
                    cwd=self.babs_project_analysis_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                tracked_files = proc.stdout.splitlines()
            except Exception:
                tracked_files = None

            # Non-zipped dataset: check files exist under subject/session directory
            for idx, row in inclu_df.iterrows():
                if (
                    self.processing_level == 'session'
                    and 'ses_id' in row
                    and pd.notna(row['ses_id'])
                ):
                    base_dir = os.path.join(
                        self.babs_project_analysis_path, row['sub_id'], row['ses_id']
                    )
                else:
                    base_dir = os.path.join(self.babs_project_analysis_path, row['sub_id'])

                # Subject/session directory must exist
                if not os.path.isdir(base_dir):
                    continue

                all_patterns_present = True
                for pattern in required_patterns:
                    # Patterns are relative to base_dir
                    if tracked_files is not None:
                        subject_rel = os.path.relpath(base_dir, self.babs_project_analysis_path)
                        if subject_rel == '.':
                            subject_rel = ''
                        if subject_rel and not subject_rel.endswith(os.sep):
                            subject_rel = subject_rel + os.sep
                        files_under_subject = [
                            f
                            for f in tracked_files
                            if (not subject_rel) or f.startswith(subject_rel)
                        ]

                        any_match = False
                        for f in files_under_subject:
                            rel_path = f[len(subject_rel) :] if subject_rel else f
                            # Direct relative match (session-level)
                            if fnmatch.fnmatch(rel_path, pattern):
                                any_match = True
                                break
                            # Subject-level: attempt matching the pattern at any depth
                            parts = rel_path.split(os.sep)
                            for i in range(len(parts)):
                                suffix = os.path.join(*parts[i:]) if i > 0 else rel_path
                                if fnmatch.fnmatch(suffix, pattern):
                                    any_match = True
                                    break
                            if any_match:
                                break

                        if not any_match:
                            all_patterns_present = False
                            break
                    else:
                        # Filesystem glob; include recursive scan for subject-level hierarchies
                        matches = []
                        # Direct relative pattern
                        matches.extend(glob(os.path.join(base_dir, pattern)))
                        # Recursive search to find pattern at any depth (subject-level use-case)
                        matches.extend(
                            glob(os.path.join(base_dir, '**', pattern), recursive=True)
                        )
                        if len(matches) == 0:
                            all_patterns_present = False
                            break

                if all_patterns_present:
                    keep_indices.append(idx)
        else:
            # Zipped dataset: match required patterns against the zip filename(s) for the row
            for idx, row in inclu_df.iterrows():
                if (
                    self.processing_level == 'session'
                    and 'ses_id' in row
                    and pd.notna(row['ses_id'])
                ):
                    zip_specific_pattern = f"{row['sub_id']}_{row['ses_id']}_*{self.name}*.zip"
                else:
                    zip_specific_pattern = f"{row['sub_id']}_*{self.name}*.zip"

                candidate_zips = glob(
                    os.path.join(self.babs_project_analysis_path, zip_specific_pattern)
                )
                if not candidate_zips:
                    # No zip found for this row; exclude
                    continue

                all_patterns_present = True
                for pattern in required_patterns:
                    # Compare against basename of the zip files
                    any_match = any(
                        fnmatch.fnmatch(os.path.basename(zip_path), pattern)
                        for zip_path in candidate_zips
                    )
                    if not any_match:
                        all_patterns_present = False
                        break

                if all_patterns_present:
                    keep_indices.append(idx)

        if not keep_indices:
            # Nothing matched; return empty frame with appropriate columns
            return inclu_df.iloc[0:0]

        return inclu_df.loc[keep_indices].reset_index(drop=True)

    def _get_sub_ses_from_zipped_input(self):
        """Find the subjects (and sessions) available as zip files in the input dataset.
        No validation is done on the zip files.

        Returns
        -------
        sub_ses_df: pandas DataFrame
            A pandas DataFrame with the subjects and sessions available in the input dataset
        """
        zip_name = self.name if self._is_input_dataset else ''
        zip_pattern = (
            f'sub-*_ses-*_{zip_name}*.zip'
            if self.processing_level == 'session'
            else f'sub-*_{zip_name}*.zip'
        )
        found_zip_files = sorted(glob(os.path.join(self.babs_project_analysis_path, zip_pattern)))

        found_sub_ses = []
        for zip_file in found_zip_files:
            zip_filename = os.path.basename(zip_file)
            # Extract subject ID (required for both processing levels)
            sub_match = re.search(r'(sub-[^_]+)', zip_filename)
            if not sub_match:
                raise ValueError(f'Could not find subject ID in zip filename: {zip_filename}')
            sub_id = sub_match.group(1)

            if self.processing_level == 'session':
                # Extract session ID if needed
                ses_match = re.search(r'(ses-[^_]+)', zip_filename)
                if not ses_match:
                    raise ValueError(f'Could not find session ID in zip filename: {zip_filename}')
                ses_id = ses_match.group(1)
                found_sub_ses.append({'sub_id': sub_id, 'ses_id': ses_id})
            else:
                found_sub_ses.append({'sub_id': sub_id})

        return pd.DataFrame(found_sub_ses)

    def _get_sub_ses_from_nonzipped_input(self):
        """Find the subjects (and sessions) available as directories in the input dataset.
        No validation is done on the directories.

        Returns
        -------
        sub_ses_df: pandas DataFrame
            A pandas DataFrame with the subjects and sessions available in the input dataset
        """

        # Get all subject directories
        sub_dirs = sorted(glob(os.path.join(self.babs_project_analysis_path, 'sub-*')))
        if not sub_dirs:
            raise ValueError(f'No subject directories found in {self.babs_project_analysis_path}')

        # Initialize lists to store subject and session IDs
        sub_ids = []
        ses_ids = []

        # Process each subject directory
        for sub_dir in sub_dirs:
            sub_id = os.path.basename(sub_dir)  # e.g., 'sub-01'

            if self.processing_level == 'session':
                # Get all session directories under this subject
                ses_dirs = sorted(glob(os.path.join(sub_dir, 'ses-*')))
                if not ses_dirs:
                    continue  # Skip subjects with no sessions

                # Add each session for this subject
                for ses_dir in ses_dirs:
                    ses_id = os.path.basename(ses_dir)  # e.g., 'ses-01'
                    sub_ids.append(sub_id)
                    ses_ids.append(ses_id)
            else:
                # For subject-level processing, just add the subject
                sub_ids.append(sub_id)

        # Create DataFrame
        if self.processing_level == 'session':
            df = pd.DataFrame({'sub_id': sub_ids, 'ses_id': ses_ids})
        else:
            df = pd.DataFrame({'sub_id': sub_ids})

        return df

    def as_dict(self):
        """Return the input dataset as a dictionary."""
        # Ensure unzipped_path_containing_subject_dirs is set correctly
        if self.is_zipped:
            unzipped_path = f'{self.path_in_babs}/{self.name}'
        else:
            unzipped_path = self.path_in_babs

        return {
            'name': self.name,
            'origin_url': self.origin_url,
            'path_in_babs': self.path_in_babs,
            'is_zipped': self.is_zipped,
            'unzipped_path_containing_subject_dirs': unzipped_path,
            'required_files': self.required_files,
            'processing_level': self.processing_level,
            'babs_project_analysis_path': self.babs_project_analysis_path,
        }


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
        search_subid = first_row['sub_id']
        search_sesid = f'_{first_row["ses_id"]}' if processing_level == 'session' else ''
        query = f'{search_subid}{search_sesid}_*{root_dir_name}*.zip'
        temp_zipfile = glob(os.path.join(dataset_abs_path, query))
        # If there were multiple matches we would have found them above
        if not temp_zipfile:
            raise FileNotFoundError(f'No zip file found for inclusion-based query {query}')
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


def validate_nonzipped_input_contents(
    dataset_abs_path, dataset_name, processing_level, included_subjects_df=None
):
    """Perform a minimal sanity check that the input dataset is valid.

    * If subject-wise processing is enabled, there should be "sub" folders.
      "ses" folders are optional.
    * If session-wise processing is enabled, there should be both "sub" and "ses" folders.

    Parameters
    ----------
    dataset_abs_path : str
        absolute path to the input dataset
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    """

    # Check if there is sub-*:
    subject_dirs = sorted(glob(os.path.join(dataset_abs_path, 'sub-*')))

    # only get the sub's foldername, if it's a directory:
    if included_subjects_df is not None:
        subjects = included_subjects_df['sub_id'].tolist()

        # Perform a quick check that the subjects exist
        for subject in subjects:
            if not os.path.exists(os.path.join(dataset_abs_path, subject)):
                raise FileNotFoundError(
                    f'There is no `{subject}` folder in input dataset {dataset_name}, '
                    f'located at {dataset_abs_path}. Check the inclusion dataframe.'
                )
    else:
        subjects = [os.path.basename(temp) for temp in subject_dirs if os.path.isdir(temp)]
    if not subjects:
        raise FileNotFoundError(
            f'In input dataset {dataset_name}, located at {dataset_abs_path}. '
            'There are no `sub-*` folders!'
        )

    # For session: also check if there is session in each sub-*:
    if processing_level == 'session':
        for subject in subjects:  # every sub- folder should contain a session folder
            session_dirs = sorted(glob(os.path.join(dataset_abs_path, subject, 'ses-*')))
            sessions = [os.path.basename(temp) for temp in session_dirs if os.path.isdir(temp)]
            if len(sessions) == 0:
                raise FileNotFoundError(
                    f'In input dataset {dataset_name}, located at {dataset_abs_path}.'
                    f'There is no `ses-*` folder in subject folder "{subject}"!'
                )

            # Check that all the included sessions are present
            if included_subjects_df is not None:
                sessions = included_subjects_df[included_subjects_df['sub_id'] == subject][
                    'ses_id'
                ].tolist()
                for session in sessions:
                    if session not in session_dirs:
                        raise FileNotFoundError(
                            f'In input dataset {dataset_name}, located at {dataset_abs_path}.'
                            f'There is no `{session}` folder in "{subject}"!'
                        )


class OutputDataset(InputDataset):
    """Represent an output dataset."""

    _is_input_dataset = False

    def __init__(self, input_dataset):
        # Store the raw value from input_dataset
        self._babs_project_analysis_path = input_dataset._babs_project_analysis_path

        # Initialize all other attributes from input_dataset
        self.name = input_dataset.name
        self.origin_url = input_dataset.origin_url
        self.path_in_babs = input_dataset.path_in_babs
        # All output datasets are zipped
        self.is_zipped = True
        self.unzipped_path_containing_subject_dirs = (
            input_dataset.unzipped_path_containing_subject_dirs
        )
        self.required_files = input_dataset.required_files
        self.processing_level = input_dataset.processing_level
