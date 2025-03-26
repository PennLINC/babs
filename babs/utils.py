"""Utils and helper functions"""

import copy
import glob
import os
import os.path as op
import re
import subprocess
import warnings
from argparse import Action
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from filelock import FileLock, Timeout
from qstat import qstat  # https://github.com/relleums/qstat


def get_datalad_version():
    return version('datalad')


def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir) if os.path.isdir(os.path.join(a_dir, name))]


def validate_unzipped_datasets(input_ds, processing_level):
    """Check if each of the unzipped input datasets is valid.

    Here we only check the "unzipped" datasets;
    the "zipped" dataset will be checked in `generate_cmd_unzip_inputds()`.

    * If subject-wise processing is enabled, there should be "sub" folders.
      "ses" folders are optional.
    * If session-wise processing is enabled, there should be both "sub" and "ses" folders.

    Parameters
    ----------
    input_ds : :obj:`babs.dataset.InputDatasets`
        info on input dataset(s)
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    """

    if processing_level not in ['session', 'subject']:
        raise ValueError('invalid `processing_level`!')

    if not all(input_ds.df['is_zipped']):  # there is at least one dataset is unzipped
        print('Performing sanity check for any unzipped input dataset...')

    for i_ds in range(input_ds.num_ds):
        if not input_ds.df.loc[i_ds, 'is_zipped']:  # unzipped ds:
            input_ds_path = input_ds.df.loc[i_ds, 'path_now_abs']
            # Check if there is sub-*:
            subject_dirs = sorted(glob.glob(os.path.join(input_ds_path, 'sub-*')))

            # only get the sub's foldername, if it's a directory:
            subjects = [op.basename(temp) for temp in subject_dirs if op.isdir(temp)]
            if len(subjects) == 0:  # no folders with `sub-*`:
                raise FileNotFoundError(
                    f'There is no `sub-*` folder in input dataset #{i_ds + 1} '
                    f'"{input_ds.df.loc[i_ds, "name"]}"!'
                )

            # For session: also check if there is session in each sub-*:
            if processing_level == 'session':
                for subject in subjects:  # every sub- folder should contain a session folder
                    session_dirs = sorted(glob.glob(os.path.join(input_ds_path, subject, 'ses-*')))
                    sessions = [op.basename(temp) for temp in session_dirs if op.isdir(temp)]
                    if len(sessions) == 0:
                        raise FileNotFoundError(
                            f'In input dataset #{i_ds + 1} "{input_ds.df.loc[i_ds, "name"]}", '
                            f'there is no `ses-*` folder in subject folder "{subject}"!'
                        )


def validate_processing_level(processing_level):
    """
    This is to validate variable `processing_level`'s value
    If it's one of supported string, change to the standard string
    if not, raise error message.
    """
    if processing_level not in ['subject', 'session']:
        raise ValueError(f'`processing_level = {processing_level}` is not allowed!')

    return processing_level


def read_yaml(fn, if_filelock=False):
    """
    This is to read yaml file.

    Parameters:
    ---------------
    fn: str
        path to the yaml file
    if_filelock: bool
        whether to use filelock

    Returns:
    ------------
    config: dict
        content of the yaml file
    """

    if if_filelock:
        lock_path = fn + '.lock'
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                with open(fn) as f:
                    config = yaml.safe_load(f)
                    # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`
                f.close()
        except Timeout:  # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print('Another instance of this application currently holds the lock.')
    else:
        with open(fn) as f:
            config = yaml.safe_load(f)
            # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`
        f.close()

    return config


def write_yaml(config, fn, if_filelock=False):
    """
    This is to write contents into yaml file.

    Parameters:
    ---------------
    config: dict
        the content to write into yaml file
    fn: str
        path to the yaml file
    if_filelock: bool
        whether to use filelock
    """
    if if_filelock:
        lock_path = fn + '.lock'
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):  # lock the file, i.e., lock job status df
                with open(fn, 'w') as f:
                    _ = yaml.dump(
                        config,
                        f,
                        sort_keys=False,  # not to sort by keys
                        default_flow_style=False,
                    )  # keep the format of nested contents
                f.close()
        except Timeout:  # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print('Another instance of this application currently holds the lock.')
    else:
        with open(fn, 'w') as f:
            _ = yaml.dump(
                config,
                f,
                sort_keys=False,  # not to sort by keys
                default_flow_style=False,
            )  # keep the format of nested contents
        f.close()


def replace_placeholder_from_config(value):
    """
    Replace the placeholder in values in container config yaml file

    Parameters:
    -------------
    value: str (or number)
        the value (v.s. key) in the input container config yaml file. Read in by babs.
        Okay to be a number; we will change it to str.

    """
    value = str(value)
    if value == '$BABS_TMPDIR':
        replaced = '"${PWD}/.git/tmp/wkdir"'

    return replaced


def app_output_settings_from_config(config):
    """
    This is to get information from `zip_foldernames` section
    in the container configuration YAML file.
    Note that users have option to request creating a sub-folder in `outputs` folder,
    if the BIDS App does not do so (e.g., fMRIPrep new BIDS output layout).

    Information:
    1. foldernames to zip
    2. whether the user requests creating a sub-folder
    3. path to the output dir to be used in the `singularity run`

    Parameters:
    ------------
    config: dictionary
        attribute `config` in class Container;

    Returns:
    ---------
    dict_zip_foldernames: dict
        `config["zip_foldernames"]` w/ placeholder key/value pair removed.
    create_output_dir_for_single_zip: bool
        whether requested to create a sub-folder in `outputs`.
    bids_app_output_dir: str
        output folder used in `singularity run` of the BIDS App.
        see examples below.

    Examples `bids_app_output_dir` of BIDS App:
    -------------------------------------------------
    In `zip_foldernames` section:
    1. No placeholder:                  outputs
    2. placeholder = true & 1 folder:   outputs/<foldername>

    Notes:
    ----------
    In fact, we use `OUTPUT_MAIN_FOLDERNAME` to define the 'outputs' string.
    """

    # create a copy of the config to avoid modifying the original
    config = copy.deepcopy(config)

    from .constants import (
        OUTPUT_MAIN_FOLDERNAME,
        PLACEHOLDER_MK_SUB_OUTPUT_FOLDER_DEPRECATED,
    )

    # By default, the output folder is `outputs`:
    bids_app_output_dir = OUTPUT_MAIN_FOLDERNAME

    # Sanity check: this section should exist:
    if 'zip_foldernames' not in config:
        raise Exception(
            'The `container_config` does not contain'
            ' the section `zip_foldernames`. Please add this section!'
        )

    # Check if placeholder to make a sub-folder in `outputs` folder
    create_output_dir_for_single_zip = config.get('all_results_in_one_zip', None)

    deprecated_create_output_dir_for_single_zip = None
    if PLACEHOLDER_MK_SUB_OUTPUT_FOLDER_DEPRECATED in config['zip_foldernames']:
        warnings.warn(
            "The placeholder '"
            + PLACEHOLDER_MK_SUB_OUTPUT_FOLDER_DEPRECATED
            + "' is deprecated. Please use the root level `all_results_in_one_zip`'"
            + "' instead.",
            stacklevel=2,
        )
        deprecated_create_output_dir_for_single_zip = (
            config['zip_foldernames'].pop(PLACEHOLDER_MK_SUB_OUTPUT_FOLDER_DEPRECATED).lower()
            == 'true'
        )

    # Only raise an exception if both are defined and they don't match
    if None not in (deprecated_create_output_dir_for_single_zip, create_output_dir_for_single_zip):
        if not deprecated_create_output_dir_for_single_zip == create_output_dir_for_single_zip:
            raise ValueError(
                'The `all_results_in_one_zip` and the deprecated placeholder'
                "'" + PLACEHOLDER_MK_SUB_OUTPUT_FOLDER_DEPRECATED + "' do not match."
            )

    # Make sure it's not empty after we popped the deprecated key
    if not config['zip_foldernames']:
        raise Exception('No output folder name provided in `zip_foldernames` section.')

    # Get the dict of foldernames + version number:
    if create_output_dir_for_single_zip:
        if not len(config['zip_foldernames']) == 1:
            raise Exception(
                'You ask BABS to create more than one output folder,'
                ' but BABS can only create one output folder.'
                " Please only keep one of them in 'zip_foldernames' section."
            )
        bids_app_output_dir += '/' + next(iter(config['zip_foldernames'].keys()))

    return config['zip_foldernames'], bids_app_output_dir


def get_list_sub_ses(input_ds, config, babs):
    """
    This is to get the list of subjects (and sessions) to analyze.

    Parameters
    ----------
    input_ds: class `InputDatasets`
        information about input dataset(s)
    config: config from class `Container`
        container's yaml file that's read into python
    babs: class `BABS`
        information about the BABS project.

    Returns
    -------
    subject project: a list of subjects
    session project: a dict of subjects and their sessions
    """

    # Get the initial list of subjects (and sessions): -------------------------------
    #   This depends on flag `list_sub_file`
    #       If it is None: get the initial list from input dataset
    #       If it's a csv file, use it as initial list
    if input_ds.initial_inclu_df is not None:  # there is initial including list
        # no need to sort (as already done when validating)
        print(
            'Using the subjects (sessions) list provided in `list_sub_file`'
            ' as the initial inclusion list.'
        )
        if babs.processing_level == 'subject':
            subs = list(input_ds.initial_inclu_df['sub_id'])
            # ^^ turn into a list
        elif babs.processing_level == 'session':
            dict_sub_ses = (
                input_ds.initial_inclu_df.groupby('sub_id')['ses_id'].apply(list).to_dict()
            )
            # ^^ group based on 'sub_id', apply list to every group,
            #   then turn into a dict.
            #   above won't change `input_ds.initial_inclu_df`

    else:  # no initial list:
        # TODO: ROADMAP: for each input dataset, get a list, then get the overlapped list
        # for now, only check the first dataset
        print(
            'Did not provide `list_sub_file`.'
            ' Will look into the first input dataset'
            ' to get the initial inclusion list.'
        )
        i_ds = 0
        if input_ds.df['is_zipped'][i_ds] is False:  # not zipped:
            full_paths = sorted(glob.glob(input_ds.df['path_now_abs'][i_ds] + '/sub-*'))
            # no need to check if there is `sub-*` in this dataset
            #   have been checked in `validate_unzipped_datasets()`
            # only get the sub's foldername, if it's a directory:
            subs = [op.basename(temp) for temp in full_paths if op.isdir(temp)]
        else:  # zipped:
            # full paths to the zip files:
            if babs.processing_level == 'subject':
                full_paths = glob.glob(
                    input_ds.df['path_now_abs'][i_ds]
                    + '/sub-*_'
                    + input_ds.df['name'][i_ds]
                    + '*.zip'
                )
            elif babs.processing_level == 'session':
                full_paths = glob.glob(
                    input_ds.df['path_now_abs'][i_ds]
                    + '/sub-*_ses-*'
                    + input_ds.df['name'][i_ds]
                    + '*.zip'
                )
                # ^^ above pattern makes sure only gets subs who have more than one ses
            full_paths = sorted(full_paths)
            zipfilenames = [op.basename(temp) for temp in full_paths]
            subs = [temp.split('_', 3)[0] for temp in zipfilenames]
            # ^^ str.split("delimiter", <maxsplit>)[i-th_field]
            # <maxsplit> means max number of "cuts"; # of total fields = <maxsplit> + 1
            subs = sorted(set(subs))  # `list(set())`: acts like "unique"

        # if it's session, get list of sessions for each subject:
        if babs.processing_level == 'session':
            # a nested list of sub and ses:
            #   first level is sub; second level is sess of a sub
            list_sub_ses = [None] * len(subs)  # predefine a list
            if input_ds.df['is_zipped'][i_ds] is False:  # not zipped:
                for i_sub, sub in enumerate(subs):
                    # get the list of sess:
                    full_paths = glob.glob(
                        op.join(input_ds.df['path_now_abs'][i_ds], sub, 'ses-*')
                    )
                    full_paths = sorted(full_paths)
                    sess = [op.basename(temp) for temp in full_paths if op.isdir(temp)]
                    # no need to validate again that session exists
                    # -  have been done in `validate_unzipped_datasets()`

                    list_sub_ses[i_sub] = sess

            else:  # zipped:
                for i_sub, sub in enumerate(subs):
                    # get the list of sess:
                    full_paths = glob.glob(
                        op.join(
                            input_ds.df['path_now_abs'][i_ds],
                            sub + '_ses-*_' + input_ds.df['name'][i_ds] + '*.zip',
                        )
                    )
                    full_paths = sorted(full_paths)
                    zipfilenames = [op.basename(temp) for temp in full_paths]
                    sess = [temp.split('_', 3)[1] for temp in zipfilenames]
                    # ^^ field #1, i.e., 2nd field which is `ses-*`
                    # no need to validate if sess exists; as it's done when getting `subs`

                    list_sub_ses[i_sub] = sess

            # then turn `subs` and `list_sub_ses` into a dict:
            dict_sub_ses = dict(zip(subs, list_sub_ses, strict=False))

    # Remove the subjects (or sessions) which does not have the required files:
    #   ------------------------------------------------------------------------
    # remove existing csv files first:
    temp_files = glob.glob(op.join(babs.analysis_path, 'code/sub_*missing_required_file.csv'))
    # ^^ subject: `sub_missing*`; session: `sub_ses_missing*`
    if len(temp_files) > 0:
        for temp_file in temp_files:
            os.remove(temp_file)
    temp_files = []  # clear
    # for session:
    fn_csv_sub_delete = op.join(babs.analysis_path, 'code/sub_missing_any_ses_required_file.csv')
    if op.exists(fn_csv_sub_delete):
        os.remove(fn_csv_sub_delete)

    # read `required_files` section from yaml file, if there is:
    if 'required_files' in config:
        print(
            'Filtering out subjects (and sessions) based on `required files`'
            ' designated in `container_config`...'
        )

        # sanity check on the target input dataset(s):
        if len(config['required_files']) > input_ds.num_ds:
            raise Exception(
                'Number of input datasets designated in `required_files`'
                ' in `container_config`'
                ' is more than actual number of input datasets!'
            )
        for i in range(0, len(config['required_files'])):
            i_ds_str = list(config['required_files'].keys())[i]  # $INPUT_DATASET_#?
            i_ds = int(i_ds_str.split('#', 1)[1]) - 1
            # ^^ split the str, get the 2nd field, i.e., '?'; then `-1` to start with 0
            if (i_ds + 1) > input_ds.num_ds:  # if '?' > actual # of input ds:
                raise Exception(
                    "'"
                    + i_ds_str
                    + "' does not exist!"
                    + ' There is only '
                    + str(input_ds.num_ds)
                    + ' input dataset(s)!'
                )

        # for the designated ds, iterate all subjects (or sessions),
        #   remove if does not have the required files, and save to a list -> a csv
        if babs.processing_level == 'subject':
            subs_missing = []
            which_dataset_missing = []
            which_file_missing = []
            # iter across designated input ds in `required_files`:
            for i in range(0, len(config['required_files'])):
                i_ds_str = list(config['required_files'].keys())[i]  # $INPUT_DATASET_#?
                i_ds = int(i_ds_str.split('#', 1)[1]) - 1
                # ^^ split the str, get the 2nd field, i.e., '?'; then `-1` to start with 0
                if input_ds.df['is_zipped'][i_ds] is True:
                    print(
                        i_ds_str
                        + ": '"
                        + input_ds.df['name'][i_ds]
                        + "'"
                        + ' is a zipped input dataset; Currently BABS does not support'
                        + ' checking if there is missing file in a zipped dataset.'
                        + ' Skip checking this input dataset...'
                    )
                    continue  # skip
                list_required_files = config['required_files'][i_ds_str]

                # iter across subs:
                updated_subs = copy.copy(subs)  # not to reference `subs`, but copy!
                # ^^ only update this list, not `subs` (as it's used in for loop)
                for sub in subs:
                    # iter of list of required files:
                    for required_file in list_required_files:
                        temp_files = glob.glob(
                            op.join(input_ds.df['path_now_abs'][i_ds], sub, required_file)
                        )
                        temp_files_2 = glob.glob(
                            op.join(
                                input_ds.df['path_now_abs'][i_ds],
                                sub,
                                '**',  # consider potential `ses-*` folder
                                required_file,
                            )
                        )
                        #  ^^ "**" means checking "all folders" in a subject
                        #  ^^ "**" does not work if there is no `ses-*` folder,
                        #       so also needs to check `temp_files`
                        if (len(temp_files) == 0) & (len(temp_files_2) == 0):  # didn't find any:
                            # remove from the `subs` list:
                            #   it shouldn't be removed by earlier datasets,
                            #   as we're iter across updated list `sub`
                            updated_subs.remove(sub)
                            # add to missing list:
                            subs_missing.append(sub)
                            which_dataset_missing.append(input_ds.df['name'][i_ds])
                            which_file_missing.append(required_file)
                            # no need to check other required files:
                            break
                # after getting out of for loops of `subs`, update `subs`:
                subs = copy.copy(updated_subs)

            # TODO: when having two unzipped input datasets, test if above works as expected!
            #   esp: removing missing subs (esp missing lists in two input ds are different)
            #   for both 1) subject; 2) session data!

            # save `subs_missing` into a csv file:
            if len(subs_missing) > 0:  # there is missing one
                df_missing = pd.DataFrame(
                    list(
                        zip(subs_missing, which_dataset_missing, which_file_missing, strict=False)
                    ),
                    columns=['sub_id', 'input_dataset_name', 'missing_required_file'],
                )
                fn_csv_missing = op.join(babs.analysis_path, 'code/sub_missing_required_file.csv')
                df_missing.to_csv(fn_csv_missing, index=False)
                print(
                    'There are '
                    + str(len(subs_missing))
                    + ' subject(s)'
                    + " who don't have required files."
                    + ' Please refer to this CSV file for full list and information: '
                    + fn_csv_missing
                )
                print("BABS will not run the BIDS App on these subjects' data.")
                print(
                    'Note for this file: For each reported subject, only'
                    ' one missing required file'
                    ' in one input dataset is recorded,'
                    ' even if there are multiple.'
                )

            else:
                print('All subjects have required files.')

        elif babs.processing_level == 'session':
            subs_missing = []  # elements can repeat if more than one ses in a sub has missing file
            sess_missing = []
            which_dataset_missing = []
            which_file_missing = []
            # iter across designated input ds in `required_files`:
            for i in range(0, len(config['required_files'])):
                i_ds_str = list(config['required_files'].keys())[i]  # $INPUT_DATASET_#?
                i_ds = int(i_ds_str.split('#', 1)[1]) - 1
                # ^^ split the str, get the 2nd field, i.e., '?'; then `-1` to start with 0
                if input_ds.df['is_zipped'][i_ds] is True:
                    print(
                        i_ds_str
                        + ": '"
                        + input_ds.df['name'][i_ds]
                        + "'"
                        + ' is a zipped input dataset; Currently BABS does not support'
                        + ' checking if there is missing file in a zipped dataset.'
                        + ' Skip checking this input dataset...'
                    )
                    continue  # skip
                list_required_files = config['required_files'][i_ds_str]

                # iter across subs: (not to update subs for now)
                for sub in list(dict_sub_ses.keys()):
                    # iter across sess:
                    # make sure there is at least one ses in this sub to loop:
                    if len(dict_sub_ses[sub]) > 0:  # deal with len=0 later
                        updated_sess = copy.deepcopy(dict_sub_ses[sub])
                        for ses in dict_sub_ses[sub]:
                            # iter across list of required files:
                            for required_file in list_required_files:
                                temp_files = glob.glob(
                                    op.join(
                                        input_ds.df['path_now_abs'][i_ds],
                                        sub,
                                        ses,
                                        required_file,
                                    )
                                )
                                if len(temp_files) == 0:  # did not find any:
                                    # remove this ses from dict:
                                    updated_sess.remove(ses)
                                    # add to missing list:
                                    subs_missing.append(sub)
                                    sess_missing.append(ses)
                                    which_dataset_missing.append(input_ds.df['name'][i_ds])
                                    which_file_missing.append(required_file)
                                    # no need to check other required files:
                                    break

                        # after getting out of loops of `sess`, update `sess`:
                        dict_sub_ses[sub] = copy.deepcopy(updated_sess)

            # after getting out of loops of `subs` and list of required files,
            #   go thru the list of subs, and see if the list of ses is empty:
            subs_delete = []
            subs_forloop = copy.deepcopy(list(dict_sub_ses.keys()))
            for sub in subs_forloop:
                # if the list of ses is empty:
                if len(dict_sub_ses[sub]) == 0:
                    # remove this key from the dict:
                    dict_sub_ses.pop(sub)
                    # add to missing sub list:
                    subs_delete.append(sub)

            # save missing ones into a csv file:
            if len(subs_missing) > 0:  # there is missing one:
                df_missing = pd.DataFrame(
                    list(
                        zip(
                            subs_missing,
                            sess_missing,
                            which_dataset_missing,
                            which_file_missing,
                            strict=False,
                        )
                    ),
                    columns=[
                        'sub_id',
                        'ses_id',
                        'input_dataset_name',
                        'missing_required_file',
                    ],
                )
                fn_csv_missing = op.join(
                    babs.analysis_path, 'code/sub_ses_missing_required_file.csv'
                )
                df_missing.to_csv(fn_csv_missing, index=False)
                print(
                    'There are '
                    + str(len(sess_missing))
                    + ' session(s)'
                    + " which don't have required files."
                    + ' Please refer to this CSV file for full list and information: '
                    + fn_csv_missing
                )
                print("BABS will not run the BIDS App on these sessions' data.")
                print(
                    'Note for this file: For each reported session, only'
                    ' one missing required file'
                    ' in one input dataset is recorded,'
                    ' even if there are multiple.'
                )
            else:
                print('All sessions from all subjects have required files.')
            # save deleted subjects into a list:
            if len(subs_delete) > 0:
                df_sub_delete = pd.DataFrame(
                    list(zip(subs_delete, strict=False)), columns=['sub_id']
                )
                fn_csv_sub_delete = op.join(
                    babs.analysis_path, 'code/sub_missing_any_ses_required_file.csv'
                )
                df_sub_delete.to_csv(fn_csv_sub_delete, index=False)
                print(
                    'Regarding subjects, '
                    + str(len(subs_delete))
                    + ' subject(s)'
                    + " don't have any session that includes required files."
                    + ' Please refer to this CSV file for the full list: '
                    + fn_csv_sub_delete
                )

    else:
        print(
            'Did not provide `required files` in `container_config`.'
            ' Not to filter subjects (or sessions)...'
        )

    # Save the final list of sub/ses in a CSV file:
    if babs.processing_level == 'subject':
        fn_csv_final = op.join(
            babs.analysis_path, babs.list_sub_path_rel
        )  # "code/sub_final_inclu.csv"
        df_final = pd.DataFrame(list(zip(subs, strict=False)), columns=['sub_id'])
        df_final.to_csv(fn_csv_final, index=False)
        print(
            'The final list of included subjects has been saved to this CSV file: ' + fn_csv_final
        )
    elif babs.processing_level == 'session':
        fn_csv_final = op.join(
            babs.analysis_path, babs.list_sub_path_rel
        )  # "code/sub_ses_final_inclu.csv"
        subs_final = []
        sess_final = []
        for sub in list(dict_sub_ses.keys()):
            for ses in dict_sub_ses[sub]:
                subs_final.append(sub)
                sess_final.append(ses)
        df_final = pd.DataFrame(
            list(zip(subs_final, sess_final, strict=False)), columns=['sub_id', 'ses_id']
        )
        df_final.to_csv(fn_csv_final, index=False)
        print(
            'The final list of included subjects and sessions has been saved to this CSV file: '
            + fn_csv_final
        )

    # Return: -------------------------------------------------------
    if babs.processing_level == 'subject':
        return subs
    elif babs.processing_level == 'session':
        return dict_sub_ses


def submit_array(analysis_path, processing_level, queue, maxarray, flag_print_message=True):
    """
    This is to submit a job array based on template yaml file.

    Parameters
    ----------
    analysis_path: str
        path to the `analysis` folder. One attribute in class `BABS`
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    queue: str
        the type of job scheduling system, "sge" or "slurm"
    maxarray: str
        max index of the array (first index is always 1)
    flag_print_message: bool
        to print a message (True) or not (False)

    Returns:
    ------------------
    job_id: int
        the int version of ID of the submitted job.
    job_id_str: str
        the string version of ID of the submitted job.
    task_id_list: list
        the list of task ID (dtype int) from the submitted job, starting from 1.
    log_filename: list
        the list of log filenames (dtype str) of this job.
        Example: 'qsi_sub-01_ses-A.*<jobid>_<arrayid>';
        user needs to replace '*' with 'o', 'e', etc

    Notes:
    -----------------
    see `Container.generate_job_submit_template()`
    for details about template yaml file.
    """

    # Load the job submission template:
    #   details of this template yaml file: see `Container.generate_job_submit_template()`
    template_yaml_path = op.join(analysis_path, 'code', 'submit_job_template.yaml')
    with open(template_yaml_path) as f:
        templates = yaml.safe_load(f)
    f.close()
    # sections in this template yaml file:
    cmd_template = templates['cmd_template']
    job_name_template = templates['job_name_template']

    cmd = cmd_template.replace('${max_array}', maxarray)
    to_print = 'Job for an array of ' + maxarray
    job_name = job_name_template.replace('${max_array}', str(int(maxarray) - 1))

    # run the command, get the job id:
    proc_cmd = subprocess.run(
        cmd.split(),
        cwd=analysis_path,
        stdout=subprocess.PIPE,  # separate by space
    )
    proc_cmd.check_returncode()
    msg = proc_cmd.stdout.decode('utf-8')

    if queue == 'sge':
        job_id_str = msg.split()[2]  # <- NOTE: this is HARD-CODED!
        # e.g., on cubic: Your job 2275903 ("test.sh") has been submitted
    elif queue == 'slurm':
        job_id_str = msg.split()[-1]
        # e.g., on MSI: 1st line is about the group; 2nd line: 'Submitted batch job 30723107'
        # e.g., on MIT OpenMind: no 1st line from MSI; only 2nd line.
    else:
        raise Exception('type system can be slurm or sge')
    job_id = int(job_id_str)

    task_id_list = []
    log_filename_list = []

    for i_array in range(int(maxarray)):
        task_id_list.append(i_array + 1)  # minarray starts from 1
        # log filename:
        log_filename_list.append(job_name + '.*' + job_id_str + '_' + str(i_array + 1))

    to_print += ' has been submitted (job ID: ' + job_id_str + ').'
    if flag_print_message:
        print(to_print)

    return job_id, job_id_str, task_id_list, log_filename_list


def df_submit_update(
    df_job_submit, job_id, task_id_list, log_filename_list, submitted=None, done=None, debug=False
):
    """
    This is to update the status of one array task in the dataframe df_job_submit
    (file: code/job_status.csv). This
    function is mostly used after job submission or resubmission. Therefore,
    a lot of fields will be reset. For other cases (e.g., to update job status
    to running state / successfully finished state, etc.), you may directly
    update df_jobs without using this function.

    Parameters
    ----------
    df_job_submit: pd.DataFrame
        dataframe of the submitted job
    job_id: int
        the int version of ID of the submitted job.
    task_id_list: list
        list of task id (dtype int), starts from 1
    log_filename_list: list
        list log filename (dtype str) of the submitted job
    submitted: bool or None
        whether the has_submitted field has to be updated
    done: bool or None
        whether the is_done field has to be updated
    debug: bool
        whether the job auditing fields need to be reset to np.nan
        (fields include last_line_stdout_file, and alert_message).

    Returns:
    -------
    df_job_submit: pd.DataFrame
        dataframe of the submitted job, updated
    """
    # Updating df_job_submit:
    # looping through each array task id in `task_id_list`
    for ind in range(len(task_id_list)):  # `task_id_list` starts from 1
        df_job_submit.loc[ind, 'job_id'] = job_id
        df_job_submit.loc[ind, 'task_id'] = int(task_id_list[ind])
        df_job_submit.at[ind, 'log_filename'] = log_filename_list[ind]
        # reset fields:
        df_job_submit.loc[ind, 'needs_resubmit'] = False
        df_job_submit.loc[ind, 'is_failed'] = np.nan
        df_job_submit.loc[ind, 'job_state_category'] = np.nan
        df_job_submit.loc[ind, 'job_state_code'] = np.nan
        df_job_submit.loc[ind, 'duration'] = np.nan
        if submitted is not None:
            # update the status:
            df_job_submit.loc[ind, 'has_submitted'] = submitted
        if done is not None:
            # update the status:
            df_job_submit.loc[ind, 'is_done'] = done
        if debug:
            df_job_submit.loc[ind, 'last_line_stdout_file'] = np.nan
            df_job_submit.loc[ind, 'alert_message'] = np.nan
    return df_job_submit


def df_status_update(df_jobs, df_job_submit, submitted=None, done=None, debug=False):
    """
    This is to update the status of one array task in the dataframe df_jobs
    (file: code/job_status.csv). This is done by inserting information from
    the updated dataframe df_job_submit (file: code/job_submit.csv). This
    function is mostly used after job submission or resubmission. Therefore,
    a lot of fields will be reset. For other cases (e.g., to update job status
    to running state / successfully finished state, etc.), you may directly
    update df_jobs without using this function.

    Parameters:
    ----------------
    df_jobs: pd.DataFrame
        dataframe of jobs and their status
    df_job_submit: pd.DataFrame
        dataframe of the to-be-submitted job
    submitted: bool or None
        whether the has_submitted field has to be updated
    done: bool or None
        whether the is_done field has to be updated
    debug: bool
        whether the job auditing fields need to be reset to np.nan
        (fields include last_line_stdout_file, and alert_message).

    Returns:
    ------------------
    df_jobs: pd.DataFrame
        dataframe of jobs and their status, updated
    """
    # Updating df_jobs
    for _, row in df_job_submit.iterrows():
        sub_id = row['sub_id']

        if 'ses_id' in df_jobs.columns:
            ses_id = row['ses_id']
            # Locate the corresponding rows in df_jobs
            mask = (df_jobs['sub_id'] == sub_id) & (df_jobs['ses_id'] == ses_id)
        elif 'ses_id' not in df_jobs.columns:
            mask = df_jobs['sub_id'] == sub_id

        # Update df_jobs fields based on the latest info in df_job_submit
        df_jobs.loc[mask, 'job_id'] = row['job_id']
        df_jobs.loc[mask, 'task_id'] = row['task_id']
        df_jobs.loc[mask, 'log_filename'] = row['log_filename']
        # reset fields:
        df_jobs.loc[mask, 'needs_resubmit'] = row['needs_resubmit']
        df_jobs.loc[mask, 'is_failed'] = row['is_failed']
        df_jobs.loc[mask, 'job_state_category'] = row['job_state_category']
        df_jobs.loc[mask, 'job_state_code'] = row['job_state_code']
        df_jobs.loc[mask, 'duration'] = row['duration']
        if submitted is not None:
            # update the status:
            df_jobs.loc[mask, 'has_submitted'] = row['has_submitted']
        if done is not None:
            # update the status:
            df_jobs.loc[mask, 'is_done'] = row['is_done']
        if debug:
            df_jobs.loc[mask, 'last_line_stdout_file'] = row['last_line_stdout_file']
            df_jobs.loc[mask, 'alert_message'] = row['alert_message']
    return df_jobs


def prepare_job_array_df(df_job, df_job_specified, count, processing_level):
    """
    This is to prepare the df_job_submit to be submitted.

    Parameters:
    ----------------
    df_job: pd.DataFrame
        dataframe of jobs and their status
    df_job_specified: pd.DataFrame
        dataframe of jobs to be submitted (specified by user)
    count: int
        number of jobs to be submitted
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis

    Returns:
    ------------------
    df_job_submit: pd.DataFrame
        list of job indices to be submitted,
        these are indices from the full job status dataframe `df_job`
    """
    df_job_submit = pd.DataFrame()
    # Check if there is still jobs to submit:
    total_has_submitted = int(df_job['has_submitted'].sum())
    if total_has_submitted == df_job.shape[0]:  # all submitted
        print('All jobs have already been submitted. ' + 'Use `babs status` to check job status.')
        return df_job_submit

    # See if user has specified list of jobs to submit:
    # NEED TO WORK ON THIS
    if df_job_specified is not None:  # NEED TO WORK ON THIS
        print('Will only submit specified jobs...')
        job_ind_list = []
        for j_job in range(0, df_job_specified.shape[0]):
            # find the index in the full `df_job`:
            if processing_level == 'subject':
                sub = df_job_specified.at[j_job, 'sub_id']
                ses = None
                temp = df_job['sub_id'] == sub
            elif processing_level == 'session':
                sub = df_job_specified.at[j_job, 'sub_id']
                ses = df_job_specified.at[j_job, 'ses_id']
                temp = (df_job['sub_id'] == sub) & (df_job['ses_id'] == ses)

            # dj: should we keep this part?
            i_job = df_job.index[temp].to_list()
            # # sanity check: there should only be one `i_job`:
            # #   ^^ can be removed as done in `core_functions.py`
            i_job = i_job[0]  # take the element out of the list

            # check if the job has already been submitted:
            if not df_job['has_submitted'][i_job]:  # to run
                job_ind_list.append(i_job)
            else:
                to_print = 'The job for ' + sub
                if processing_level == 'session':
                    to_print += ', ' + ses
                to_print += (
                    ' has already been submitted,'
                    " so it won't be submitted again."
                    ' If you want to resubmit it,'
                    ' please use `babs status --resubmit`'
                )
                print(to_print)
    else:  # taking into account the `count` argument
        df_remain = df_job[~df_job.has_submitted]
        if count > 0:
            df_job_submit = df_remain[:count].reset_index(drop=True)
        else:  # if count is None or negative, run all
            df_job_submit = df_remain.copy().reset_index(drop=True)
    return df_job_submit


def submit_one_test_job(analysis_path, queue, flag_print_message=True):
    """
    This is to submit one *test* job.
    This is used by `babs check-setup`.

    Parameters:
    ----------------
    analysis_path: str
        path to the `analysis` folder. One attribute in class `BABS`
    queue: str
        the type of job scheduling system, "sge" or "slurm"
    flag_print_message: bool
        to print a message (True) or not (False)

    Returns:
    -----------
    job_id: int
        the int version of ID of the submitted job.
    job_id_str: str
        the string version of ID of the submitted job.
    log_filename: str
        log filename of this job.
        Example: 'qsi_sub-01_ses-A.*<jobid>'; user needs to replace '*' with 'o', 'e', etc

    Notes:
    -----------------
    see `Container.generate_test_job_submit_template()`
    for details about template yaml file.
    """
    # Load the job submission template:
    #   details of this template yaml file: see `Container.generate_test_job_submit_template()`
    template_yaml_path = op.join(
        analysis_path, 'code/check_setup', 'submit_test_job_template.yaml'
    )
    with open(template_yaml_path) as f:
        templates = yaml.safe_load(f)
    f.close()
    # sections in this template yaml file:
    cmd = templates['cmd_template']
    job_name = templates['job_name_template']

    to_print = 'Test job'

    # run the command, get the job id:
    proc_cmd = subprocess.run(
        cmd.split(),
        cwd=analysis_path,
        stdout=subprocess.PIPE,  # separate by space
    )

    proc_cmd.check_returncode()
    msg = proc_cmd.stdout.decode('utf-8')

    if queue == 'sge':
        job_id_str = msg.split()[2]  # <- NOTE: this is HARD-CODED!
        # e.g., on cubic: Your job 2275903 ("test.sh") has been submitted
    elif queue == 'slurm':
        job_id_str = msg.split()[-1]
        # e.g., on MSI: 1st line is about the group; 2nd line: 'Submitted batch job 30723107'
        # e.g., on MIT OpenMind: no 1st line from MSI; only 2nd line.
    else:
        raise Exception('type system can be slurm or sge')

    # This is necessary SLURM commands can fail but have return code 0
    try:
        job_id = int(job_id_str)
    except ValueError as e:
        raise ValueError(
            f'Cannot convert {job_id_str!r} into an int: {e}. '
            f'That output is a result of running command {cmd} which produced output {msg}.'
        )

    # log filename:
    log_filename = job_name + '.*' + job_id_str

    to_print += ' has been submitted (job ID: ' + job_id_str + ').'
    if flag_print_message:
        print(to_print)

    return job_id, job_id_str, log_filename


def create_job_status_csv(babs):
    """
    This is to create a CSV file of `job_status`.
    This should be used by `babs submit` and `babs status`.

    Parameters:
    ------------
    babs: class `BABS`
        information about a BABS project.
    """

    if op.exists(babs.job_status_path_abs) is False:
        # Generate the table:
        # read the subject list as a panda df:
        df_sub = pd.read_csv(babs.list_sub_path_abs)
        df_job = df_sub.copy()  # deep copy of pandas df

        # add columns:
        df_job['has_submitted'] = False
        df_job['job_id'] = -1  # int
        df_job['job_state_category'] = np.nan
        df_job['job_state_code'] = np.nan
        df_job['duration'] = np.nan
        df_job['is_done'] = False  # = has branch in output_ria
        df_job['needs_resubmit'] = False
        df_job['is_failed'] = np.nan
        df_job['log_filename'] = np.nan
        df_job['last_line_stdout_file'] = np.nan
        df_job['alert_message'] = np.nan

        # TODO: add different kinds of error

        # These `NaN` will be saved as empty strings (i.e., nothing between two ",")
        #   but when pandas read this csv, the NaN will show up in the df

        # Save the df as csv file, using lock:
        lock_path = babs.job_status_path_abs + '.lock'
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=5):
                df_job.to_csv(babs.job_status_path_abs, index=False)
        except Timeout:  # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print('Another instance of this application currently holds the lock.')


def read_job_status_csv(csv_path):
    """
    This is to read the CSV file of `job_status`.

    Parameters:
    ------------
    csv_path: str
        path to the `job_status.csv`

    Returns:
    -----------
    df: pandas dataframe
        loaded dataframe
    """
    df = pd.read_csv(
        csv_path,
        dtype={
            'job_id': 'Int64',
            'task_id': 'Int64',
            'log_filename': 'str',
            'has_submitted': 'boolean',
            'is_done': 'boolean',
            'is_failed': 'boolean',
            'needs_resubmit': 'boolean',
            'last_line_stdout_file': 'str',
            'job_state_category': 'str',
            'job_state_code': 'str',
            'duration': 'str',
            'alert_message': 'str',
        },
    )
    return df


def report_job_status(df, analysis_path, config_msg_alert):
    """
    This is to report the job status
    based on the dataframe loaded from `job_status.csv`.

    Parameters:
    -------------
    df: pandas dataframe
        loaded dataframe from `job_status.csv`
    analysis_path: str
        Path to the analysis folder.
        This is used to generate the folder of log files
    config_msg_alert: dict or None
        From `get_config_msg_alert()`
        This is used to determine if to report `alert_message` column
    """

    print('\nJob status:')

    total_jobs = df.shape[0]
    print('There are in total of ' + str(total_jobs) + ' jobs to complete.')

    total_has_submitted = int(df['has_submitted'].sum())
    print(
        str(total_has_submitted)
        + ' job(s) have been submitted; '
        + str(total_jobs - total_has_submitted)
        + " job(s) haven't been submitted."
    )

    if total_has_submitted > 0:  # there is at least one job submitted
        total_is_done = int(df['is_done'].sum())
        print('Among submitted jobs,')
        print(str(total_is_done) + ' job(s) successfully finished;')

        if total_is_done == total_jobs:
            print('All jobs are completed!')
        else:
            total_pending = int((df['job_state_code'] == 'qw').sum())
            print(str(total_pending) + ' job(s) are pending;')

            total_pending = int((df['job_state_code'] == 'r').sum())
            print(str(total_pending) + ' job(s) are running;')

            # TODO: add stalled one

            total_is_failed = int(df['is_failed'].sum())
            print(str(total_is_failed) + ' job(s) failed.')

            # if there is job failed: print more info by categorizing msg:
            if total_is_failed > 0:
                if config_msg_alert is not None:
                    print('\nAmong all failed job(s):')
                # get the list of jobs that 'is_failed=True':
                list_index_job_failed = df.index[df['is_failed']].tolist()
                # ^^ notice that df["is_failed"] contains np.nan, so can only get in this way

                # summarize based on `alert_message` column:

                all_alert_message = df['alert_message'][list_index_job_failed].tolist()
                unique_list_alert_message = list(set(all_alert_message))
                # unique_list_alert_message.sort()   # sort and update the list itself
                # TODO: before `.sort()` ^^, change `np.nan` to string 'nan'!

                if config_msg_alert is not None:
                    for unique_alert_msg in unique_list_alert_message:
                        # count:
                        temp_count = all_alert_message.count(unique_alert_msg)
                        print(
                            str(temp_count)
                            + " job(s) have alert message: '"
                            + str(unique_alert_msg)
                            + "';"
                        )

        print('\nAll log files are located in folder: ' + op.join(analysis_path, 'logs'))


def request_all_job_status(queue):
    """
    This is to get all jobs' status
    using `qstat` for SGE clusters and `squeue` for Slurm

    Parameters
    ----------
    queue: str
        the type of job scheduling system, "sge" or "slurm"

    Returns:
    --------------
    df: pd.DataFrame
        All jobs' status, including running and pending (waiting) jobs'.
        If there is no job in the queue, df will be an empty DataFrame
        (i.e., Columns: [], Index: [])
    """
    if queue == 'sge':
        return _request_all_job_status_sge()
    elif queue == 'slurm':
        return _request_all_job_status_slurm()


def _request_all_job_status_sge():
    """
    This is to get all jobs' status for SGE
    using package [`qstat`](https://github.com/relleums/qstat)
    """
    queue_info, job_info = qstat()
    # ^^ queue_info: dict of jobs that are running
    # ^^ job_info: dict of jobs that are pending

    # turn all jobs into a dataframe:
    df = pd.DataFrame(queue_info + job_info)

    # check if there is no job in the queue:
    if (not queue_info) & (not job_info):  # both are `[]`
        pass  # don't set the index
    else:
        df = df.set_index('JB_job_number')  # set a column as index
        # index `JB_job_number`: job ID (data type: str)
        # column `@state`: 'running' or 'pending'
        # column `state`: 'r', 'qw', etc
        # column `JAT_start_time`: start time of running
        #   e.g., '2022-12-06T14:28:43'

    return df


def _parsing_squeue_out(squeue_std):
    """
    This is to parse printed messages from `squeue` on Slurm clusters
    and to convert Slurm codes to SGE codes

    Parameters
    -------------
    squeue_std: str
        Standard output from running command `squeue` in terminal

    Returns
    -----------
    df: pd.DataFrame
        Job status based on `squeue` printed messages.
        If there is no job in the queue, df will be an empty DataFrame
        (i.e., Columns: [], Index: [])
    """
    # Sanity check: if there is no job in queue:
    if len(squeue_std.splitlines()) <= 1:
        # there is only a header, no job is in queue:
        df = pd.DataFrame(data=[])  # empty dataframe
    else:  # there are job(s) in queue (e.g., pending or running)
        header_l = squeue_std.splitlines()[0].split()
        datarows = squeue_std.splitlines()[1:]

        # column index of these column names:
        # NOTE: this is hard coded! Please check out `_request_all_job_status_slurm()`
        #   for the format of printed messages from `squeue`
        dict_ind = {'jobid': 0, 'st': 4, 'state': 5, 'time': 6}
        # initialize a dict for holding the values from all jobs:
        # ROADMAP: pd.DataFrame is probably more memory efficient than dicts
        dict_val = {key: [] for key in dict_ind}

        # sanity check: these fields show up in the header we got:
        for fld in ['jobid', 'st', 'state', 'time']:
            if header_l[dict_ind[fld]].lower() != fld:
                raise Exception(
                    'error in the `squeue` output,'
                    f' expected {fld} and got {header_l[dict_ind[fld]].lower()}'
                )

        for row in datarows:
            if '.' not in row.split()[0]:
                for key, ind in dict_ind.items():
                    dict_val[key].append(row.split()[ind])
        # e.g.: dict_val: {'jobid': ['157414586', '157414584'],
        #   'st': ['PD', 'R'], 'state': ['PENDING', 'RUNNING'], 'time': ['0:00', '0:52']}

        # Renaming the keys, to be consistent with results got from SGE clusters:
        dict_val['JB_job_number'] = dict_val.pop('jobid')
        # change to lowercase, and rename the key:
        dict_val['@state'] = [x.lower() for x in dict_val.pop('state')]
        dict_val['duration'] = dict_val.pop('time')
        # e.g.,: dict_val: {'st': ['PD', 'R'], 'JB_job_number': ['157414586', '157414584'],
        #   '@state': ['pending', 'running'], 'duration': ['0:00', '0:52']}
        # NOTE: the 'duration' format might be slightly different from results from
        #   function `calcu_runtime()` used by SGE clusters.

        # job state mapping from slurm to sge:
        state_slurm2sge = {'R': 'r', 'PD': 'qw'}
        dict_val['state'] = [state_slurm2sge.get(sl_st, 'NA') for sl_st in dict_val.pop('st')]
        # e.g.,: dict_val: {'JB_job_number': ['157414586', '157414584'],
        #   '@state': ['pending', 'running'], 'duration': ['0:00', '0:52'], 'state': ['qw', 'r']}

        df = pd.DataFrame(data=dict_val)
        df = df.set_index('JB_job_number')

        # df for array submission looked different
        # Need to expand rows like 3556872_[98-1570] to 3556872_98, 3556872_99, etc
        # This code only expects the first line to be pending array tasks, 3556872_[98-1570]
        if '[' in df.index[0]:
            first_row = df.iloc[0]
            range_parts = re.search(r'\[(\d+-\d+)', df.index[0]).group(1)  # get the array range
            start, end = map(int, range_parts.split('-'))  # get min and max pending array
            job_id = df.index[0].split('_')[0]

            expanded_rows = []
            for task_id in range(start, end + 1):
                expanded_rows.append(
                    {
                        'JB_job_number': f'{job_id}_{task_id}',
                        '@state': first_row['@state'],
                        'duration': first_row['duration'],
                        'state': first_row['state'],
                        'job_id': job_id,
                        'task_id': task_id,
                    }
                )
            # Convert expanded rows to DataFrame
            expanded_df = pd.DataFrame(expanded_rows).set_index('JB_job_number')
            # Process the rest of the DataFrame
            remaining_df = df.iloc[1:].copy()
            remaining_df['job_id'] = remaining_df.index.str.split('_').str[0]
            remaining_df['task_id'] = remaining_df.index.str.split('_').str[1].astype(int)
            # Combine and sort
            final_df = pd.concat([expanded_df, remaining_df])
            final_df = final_df.sort_values(by=['job_id', 'task_id'])
            return final_df

    return df


def _request_all_job_status_slurm():
    """
    This is to get all jobs' status for Slurm
    by calling `squeue`.
    """
    username = get_username()
    squeue_proc = subprocess.run(
        ['squeue', '-u', username, '-o', '%.18i %.9P %.8j %.8u %.2t %T %.10M'],
        stdout=subprocess.PIPE,
    )
    std = squeue_proc.stdout.decode('utf-8')

    squeue_out_df = _parsing_squeue_out(std)
    return squeue_out_df


def calcu_runtime(start_time_str):
    """
    This is to calculate the duration time of running.

    Parameters:
    -----------------
    start_time_str: str
        The value in column 'JAT_start_time' for a specific job.
        Can be got via `df.at['2820901', 'JAT_start_time']`
        Example on CUBIC: ''

    Returns:
    -----------------
    duration_time_str: str
        Duration time of running.
        Format: '0:00:05.050744' (i.e., ~5sec), '2 days, 0:00:00'

    Notes
    -----
    TODO: add queue if needed
    Currently we don't need to add `queue`. Whether 'duration' has been returned
    is checked before current function is called.
    However the format of the duration that got from Slurm cluster might be a bit different from
    what we get here. See examples in function `_parsing_squeue_out()` for Slurm clusters.

    This duration time may be slightly longer than actual
    time, as this is using current time, instead of
    the time when `qstat`/requesting job queue.
    """
    # format of time in the job status requested:
    format_job_status = '%Y-%m-%dT%H:%M:%S'  # format in `qstat`
    # # format of returned duration time:
    # format_duration_time = "%Hh%Mm%Ss"  # '0h0m0s'

    d_now = datetime.now()
    duration_time = d_now - datetime.strptime(start_time_str, format_job_status)
    # ^^ str(duration_time): format: '0:08:40.158985'  # first is hour
    duration_time_str = str(duration_time)
    # ^^ 'datetime.timedelta' object (`duration_time`) has no attribute 'strftime'
    #   so cannot be directly printed into desired format...

    return duration_time_str


def get_last_line(fn):
    """
    This is to get the last line of a text file, e.g., `stdout` file

    Parameters:
    --------------------
    fn: str
        path to the text file.

    Returns:
    --------------------
    last_line: str or np.nan (if the log file haven't existed yet, or no valid line yet)
        last line of the text file.
    """

    if op.exists(fn):
        with open(fn) as f:
            all_lines = f.readlines()
            if len(all_lines) > 0:  # at least one line in the file:
                last_line = all_lines[-1]
                # remove spaces at the beginning or the end; remove '\n':
                last_line = last_line.strip().replace('\n', '')
            else:
                last_line = np.nan
    else:  # e.g., `qw` pending
        last_line = np.nan

    return last_line


def get_config_msg_alert(container_config):
    """
    To extract the configs of alert msgs in log files.

    Parameters
    ----------
    container_config: str or None
        path to the config yaml file of containers, which might includes
        a section of `alert_log_messages`

    Returns
    -------
    config_msg_alert: dict or None
    """

    if container_config is not None:  # yaml file is provided
        with open(container_config) as f:
            container_config = yaml.safe_load(f)

        # Check if there is section 'alert_log_messages':
        if 'alert_log_messages' in container_config:
            config_msg_alert = container_config['alert_log_messages']
            # ^^ if it's empty under `alert_log_messages`: config_msg_alert=None

            # Check if there is either 'stdout' or 'stderr' in "alert_log_messages":
            if config_msg_alert is not None:  # there is sth under "alert_log_messages":
                if ('stdout' not in config_msg_alert) & ('stderr' not in config_msg_alert):
                    # neither is included:
                    warnings.warn(
                        "Section 'alert_log_messages' is provided in `container_config`,"
                        " but neither 'stdout' nor 'stderr' is included in this section."
                        " So BABS won't check if there is"
                        ' any alerting message in log files.',
                        stacklevel=2,
                    )
                    config_msg_alert = None  # not useful anymore, set to None then.
            else:  # nothing under "alert_log_messages":
                warnings.warn(
                    "Section 'alert_log_messages' is provided in `container_config`, but"
                    " neither 'stdout' nor 'stderr' is included in this section."
                    " So BABS won't check if there is"
                    ' any alerting message in log files.',
                    stacklevel=2,
                )
                # `config_msg_alert` is already `None`, no need to set to None
        else:
            config_msg_alert = None
            warnings.warn(
                "There is no section called 'alert_log_messages' in the provided"
                " `container_config`. So BABS won't check if there is"
                ' any alerting message in log files.',
                stacklevel=2,
            )
    else:
        config_msg_alert = None

    return config_msg_alert


def get_alert_message_in_log_files(config_msg_alert, log_fn):
    """
    This is to get any alert message in log files of a job.

    Parameters:
    -----------------
    config_msg_alert: dict or None
        section 'alert_log_messages' in container config yaml file
        that includes what alert messages to look for in log files.
    log_fn: str
        Absolute path to a job's log files. It should have `*` to be replaced with `o` or `e`
        Example: /path/to/analysis/logs/toy_sub-0000.*11111

    Returns:
    ----------------
    alert_message: str or np.nan
        If config_msg_alert is None, or log file does not exist yet,
            `alert_message` will be `np.nan`;
        if not None, `alert_message` will be a str.
            Examples:
            - if did not find: see `MSG_NO_ALERT_MESSAGE_IN_LOGS`
            - if found: "stdout file: <message>"
    if_no_alert_in_log: bool
        There is no alert message in the log files.
        When `alert_message` is `msg_no_alert`,
        or is `np.nan` (`if_valid_alert_msg=False`), this is True;
        Otherwise, any other message, this is False
    if_found_log_files: bool or np.nan
        np.nan if `config_msg_alert` is None, as it's unknown whether log files exist or not
        Otherwise, True or False based on if any log files were found

    Notes:
    -----------------
    An edge case (not a bug): On cubic cluster, some info will be printed to 'stderr' file
    before 'stdout' file have any printed messages. So 'alert_message' column may say
    'BABS: No alert' but 'last_line_stdout_file' is still 'NaN'
    """

    from .constants import MSG_NO_ALERT_IN_LOGS

    msg_no_alert = MSG_NO_ALERT_IN_LOGS
    if_valid_alert_msg = True  # by default, `alert_message` is valid (i.e., not np.nan)
    # this is to avoid check `np.isnan(alert_message)`, as `np.isnan(str)` causes error.
    if_found_log_files = np.nan

    if config_msg_alert is None:
        alert_message = np.nan
        if_valid_alert_msg = False
        if_found_log_files = np.nan  # unknown if log files exist or not
    else:
        o_fn = log_fn.replace('*', 'o')
        e_fn = log_fn.replace('*', 'e')

        if op.exists(o_fn) or op.exists(e_fn):  # either exists:
            if_found_log_files = True
            found_message = False
            alert_message = msg_no_alert

            for key in config_msg_alert:  # as it's dict, keys cannot be duplicated
                if key in ['stdout', 'stderr']:
                    one_char = key[3]  # 'o' or 'e'
                    # the log file to look into:
                    fn = log_fn.replace('*', one_char)

                    if op.exists(fn):
                        with open(fn) as f:
                            # Loop across lines, from the beginning of the file:
                            for line in f:
                                # Loop across the messages for this kind of log file:
                                for message in config_msg_alert[key]:
                                    if message in line:  # found:
                                        found_message = True
                                        alert_message = key + ' file: ' + message
                                        # e.g., 'stdout file: <message>'
                                        break  # no need to search next message

                                if found_message:
                                    break  # no need to go to next line
                    # if the log file does not exist, probably due to pending
                    #   not to do anything

                if found_message:
                    break  # no need to go to next log file

        else:  # neither o_fn nor e_fn exists yet:
            if_found_log_files = False
            alert_message = np.nan
            if_valid_alert_msg = False

    if (alert_message == msg_no_alert) or (not if_valid_alert_msg):
        # either no alert, or `np.nan`
        if_no_alert_in_log = True
    else:  # `alert_message`: np.nan or any other message:
        if_no_alert_in_log = False

    return alert_message, if_no_alert_in_log, if_found_log_files


def get_username():
    """
    This is to get the current username.
    This will be used for job accounting, e.g., `qacct`.

    Returns:
    -----------
    username_lowercase: str

    NOTE: only support SGE now.
    """
    proc_username = subprocess.run(['whoami'], stdout=subprocess.PIPE)
    proc_username.check_returncode()
    username_lowercase = proc_username.stdout.decode('utf-8')
    username_lowercase = username_lowercase.replace('\n', '')  # remove \n

    return username_lowercase


def get_cmd_cancel_job(queue):
    """
    This is to get the command used for canceling a job
    (i.e., deleting a job from the queue).
    This is dependent on cluster system.

    Parameters
    ----------
    queue: str
        the type of job scheduling system, "sge" or "slurm"

    Returns:
    --------------
    cmd: str
        the command for canceling a job

    Notes:
    ----------------
    On SGE clusters, we use `qdel <job_id>` to cancel a job;
    On Slurm clusters, we use `scancel <job_id>` to cancel a job.
    """

    if queue == 'sge':
        cmd = 'qdel'
    elif queue == 'slurm':
        cmd = 'scancel'
    else:
        raise Exception('Invalid job scheduler system type `queue`: ' + queue)

    # print("the command for cancelling the job: " + cmd)   # NOTE: for testing only
    return cmd


def print_versions_from_yaml(fn_yaml):
    """
    This is to go thru information in `code/check_setup/check_env.yaml` saved by `test_job.py`.
    1. check if there is anything required but not installed
    2. print out the versions for user to visually check
    This is used by `babs check-setup`.

    Parameters:
    ----------------
    fn_yaml: str
        path to the yaml file (usually is `code/check_setup/check_env.yaml`)

    Returns:
    ------------
    flag_writable: bool
        if the workspace is writable
    flag_all_installed: bool
        if all necessary packages are installed
    """
    # Read the yaml file and print the content:
    config = read_yaml(fn_yaml)
    print('Below is the information of designated environment and temporary workspace:\n')
    # print the yaml file:
    f = open(fn_yaml)
    file_contents = f.read()
    print(file_contents)
    f.close()

    # Check if everything is as satisfied:
    if config['workspace_writable']:  # bool; if writable:
        flag_writable = True
    else:
        flag_writable = False

    # Check all dependent packages are installed:
    flag_all_installed = True
    for key in config['version']:
        if config['version'][key] == 'not_installed':  # see `babs/template_test_job.py`
            flag_all_installed = False
            warnings.warn('This required package is not installed: ' + key, stacklevel=2)

    return flag_writable, flag_all_installed


def get_git_show_ref_shasum(branch_name, the_path):
    """
    This is to get current commit's shasum by calling `git show-ref`.
    This can be used by `babs merge`.

    Parameters:
    --------------
    branch_name: str
        string name of the branch where you want to run `git show-ref` for
    the_path: str
        path to the git (or datalad) repository

    Returns:
    -------------
    git_ref: str
        current commit's shasum of this branch in this git repo
    msg: str
        the string got by `git show-ref`, before split by space and '\n'.
    Notes:
    -------
    bash version would be:
    `git show-ref ${git_default_branchname} | cut -d ' ' -f1 | head -n 1`
    Here, `cut` means split, `-f1` is to get the first split in each element in the list;
    `head -n 1` is to get the first element in the list
    """

    proc_git_show_ref = subprocess.run(
        ['git', 'show-ref', branch_name], cwd=the_path, stdout=subprocess.PIPE
    )
    proc_git_show_ref.check_returncode()
    msg = proc_git_show_ref.stdout.decode('utf-8')
    # `msg.split()`:    # split by space and '\n'
    #   e.g. for default branch (main or master):
    #   ['xxxxxx', 'refs/heads/master', 'xxxxx', 'refs/remotes/origin/master']
    #   usually first 'xxxxx' and second 'xxxxx' are the same
    #   for job's branch: usually there is only one line in msg, i.e.,:
    #   ['xxxx', 'refs/remotes/origin/job-0000-sub-xxxx']
    git_ref = msg.split()[0]  # take the first element

    return git_ref, msg


def ceildiv(a, b):
    """
    This is to calculate the ceiling of division of a/b.
    ref: https://stackoverflow.com/questions/14822184/...
      ...is-there-a-ceiling-equivalent-of-operator-in-python
    """
    return -(a // -b)


def _path_does_not_exist(path, parser):
    """Ensure a given path does not exist."""
    if path is None:
        raise parser.error('The path is required.')
    elif Path(path).exists():
        raise parser.error(f'The path <{path}> already exists.')

    return Path(path).absolute()


def _path_exists(path, parser):
    """Ensure a given path exists."""
    if path is None or not Path(path).exists():
        raise parser.error(f'The path <{path}> does not exist.')

    return Path(path).absolute()


class ToDict(Action):
    """A custom argparse "store" action to handle a list of key=value pairs."""

    def __call__(self, parser, namespace, values, option_string=None):
        """Call the argument."""
        d = {}
        for spec in values:
            try:
                name, loc = spec.split('=')
                loc = Path(loc)
            except ValueError:
                loc = Path(spec)
                name = loc.name

            if name in d:
                raise parser.error(f'Received duplicate derivative name: {name}')
            elif name == 'preprocessed':
                raise parser.error("The 'preprocessed' derivative is reserved for internal use.")

            d[name] = str(loc)
        setattr(namespace, self.dest, d)
