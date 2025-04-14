"""Utils and helper functions"""

import copy
import getpass
import os
import os.path as op
import subprocess
import warnings
from importlib.metadata import version

import numpy as np
import pandas as pd
import yaml
from filelock import FileLock, Timeout


def get_datalad_version():
    return version('datalad')


def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir) if os.path.isdir(os.path.join(a_dir, name))]


def validate_processing_level(processing_level):
    """
    This is to validate variable `processing_level`'s value
    If it's one of supported string, change to the standard string
    if not, raise error message.
    """
    if processing_level not in ['subject', 'session']:
        raise ValueError(f'`processing_level = {processing_level}` is not allowed!')

    return processing_level


def read_yaml(fn, use_filelock=False):
    """
    This is to read yaml file.

    Parameters:
    ---------------
    fn: str
        path to the yaml file
    use_filelock: bool
        whether to use filelock

    Returns:
    ------------
    config: dict
        content of the yaml file
    """

    if use_filelock:
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


def write_yaml(config, fn, use_filelock=False):
    """
    This is to write contents into yaml file.

    Parameters:
    ---------------
    config: dict
        the content to write into yaml file
    fn: str
        path to the yaml file
    use_filelock: bool
        whether to use filelock
    """

    # Convert numpy types to native Python types
    def convert_numpy(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    # Recursively convert numpy types in the config
    def convert_dict(d):
        if isinstance(d, dict):
            return {k: convert_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [convert_dict(v) for v in d]
        return convert_numpy(d)

    config = convert_dict(config)

    if use_filelock:
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
                last_line = ''
    else:  # e.g., `qw` pending
        last_line = ''

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
    no_alert_in_log: bool
        There is no alert message in the log files.
        When `alert_message` is `msg_no_alert`,
        or is `np.nan` (`valid_alert_msg=False`), this is True;
        Otherwise, any other message, this is False
    found_log_files: bool or np.nan
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
    valid_alert_msg = True  # by default, `alert_message` is valid (i.e., not np.nan)
    # this is to avoid check `np.isnan(alert_message)`, as `np.isnan(str)` causes error.
    found_log_files = np.nan

    if config_msg_alert is None:
        alert_message = np.nan
        valid_alert_msg = False
        found_log_files = np.nan  # unknown if log files exist or not
    else:
        o_fn = log_fn.replace('*', 'o')
        e_fn = log_fn.replace('*', 'e')

        if op.exists(o_fn) or op.exists(e_fn):  # either exists:
            found_log_files = True
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
            found_log_files = False
            alert_message = np.nan
            valid_alert_msg = False

    if (alert_message == msg_no_alert) or (not valid_alert_msg):
        # either no alert, or `np.nan`
        no_alert_in_log = True
    else:  # `alert_message`: np.nan or any other message:
        no_alert_in_log = False

    return alert_message, no_alert_in_log, found_log_files


def get_username():
    """
    Get the current username.

    Returns:
    --------
    str
        Current username
    """
    return getpass.getuser()


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


def get_results_branches(ria_directory):
    """
    Get branch list from git repository

    Parameters:
    --------------
    ria_directory: str
        path to the git (or datalad) repository

    """
    branch_output = subprocess.run(
        ['git', 'branch', '--list'],
        cwd=ria_directory,
        capture_output=True,
        text=True,
    )

    # Filter to just branches starting with 'job-'
    branches = [
        # Remove leading and trailing asterisks and spaces
        b.strip().replace('* ', '')
        for b in branch_output.stdout.strip().split('\n')
        if b.strip().replace('* ', '').startswith('job-')
    ]
    if not branches:
        raise ValueError('No branches found in the repository')
    return branches


def results_branch_dataframe(branches):
    """
    Create a dataframe from a list of branches.

    Parameters:
    --------------
    branches: list
        list of branches

    Returns:
    -------------
    df: pd.DataFrame
        dataframe with the following columns:
        job_id: int
        task_id: int
        sub_id: str
        ses_id: str
        has_results: bool

    Examples:
    ---------
    For sessionwise processing, the returned dataframe will look like:
    job_id  task_id  sub_id  ses_id  has_results
    123     1      sub-0000    ses-0000    True
    123     2      sub-0001    ses-0001    True

    for subjectwise processing, the returned dataframe will look like:

    job_id  task_id  sub_id  has_results
    123     1      sub-0000    True
    123     2      sub-0001    True

    """
    import re

    # Create a pattern with named groups - ses_id is optional
    pattern = (
        r'job-(?P<job_id>\d+)-?(?P<task_id>\d+)?[-_]'
        r'(?P<sub_id>sub-[^_]+)(?:_(?P<ses_id>ses-[^_]+))?'
    )

    result_data = []
    for branch in branches:
        match = re.match(pattern, branch)
        if match:
            # Convert match to dictionary and add has_results
            result = match.groupdict()
            result['has_results'] = True
            result_data.append(result)

    df = pd.DataFrame(result_data)

    return df


def identify_running_jobs(last_submitted_jobs_df, currently_running_df):
    """
    The currently-running jobs do not have the subject/session information.
    This function is to identify the jobs that are running.

    Parameters
    ----------
    currently_running_df: pd.DataFrame
        dataframe of currently running jobs (from request_all_job_status())
    last_submitted_jobs_df: pd.DataFrame
        dataframe of last submitted jobs

    Returns
    -------
    pd.DataFrame
        dataframe of identified running jobs with subject/session information
    """

    try:
        return pd.merge(currently_running_df, last_submitted_jobs_df, on=['job_id', 'task_id'])
    except Exception as e:
        raise ValueError(
            f'Error merging currently_running_df and last_submitted_jobs_df: {e}'
            f'Currently running df:\n\n{currently_running_df}\n\n'
            f'Last submitted jobs df:\n\n{last_submitted_jobs_df}\n\n'
        )


def update_results_status(status_df, has_results_df):
    """
    Update a status dataframe with a results branch dataframe.

    Parameters:
    --------------
    status_df: pd.DataFrame
        status dataframe
    has_results_df: pd.DataFrame
        results branch dataframe

    Returns:
    -------------
    df: pd.DataFrame
        updated job status dataframe

    """
    use_sesid = 'ses_id' in status_df and 'ses_id' in has_results_df
    merge_on = ['sub_id', 'ses_id'] if use_sesid else ['sub_id']

    # First merge to get the most recent results information
    updated_results_df = pd.merge(
        status_df, has_results_df, on=merge_on, how='left', suffixes=('', '_results')
    )
    # Update job_id and task_id only where there's a new result
    has_results_mask = (
        updated_results_df['has_results'].notna() & updated_results_df['has_results']
    )
    updated_results_df.loc[has_results_mask, 'job_id'] = updated_results_df.loc[
        has_results_mask, 'job_id_results'
    ]
    updated_results_df.loc[has_results_mask, 'task_id'] = updated_results_df.loc[
        has_results_mask, 'task_id_results'
    ]
    updated_results_df = updated_results_df.drop(columns=['job_id_results', 'task_id_results'])

    return updated_results_df


def update_job_batch_status(status_df, job_submit_df):
    """
    Update the status dataframe with the job submission information.

    Parameters:
    -----------
    status_df: pd.DataFrame
        status dataframe. Be sure has_results is up to date.
    job_submit_df: pd.DataFrame
        the current status of job submission.

    Returns:
    --------
    pd.DataFrame
        updated status dataframe

    """

    if 'sub_id' not in job_submit_df:
        raise ValueError('job_submit_df must have a sub_id column')

    use_sesid = 'ses_id' in status_df and 'ses_id' in job_submit_df
    merge_on = ['sub_id', 'ses_id'] if use_sesid else ['sub_id']

    # First merge to get the most recent results information
    updated_status_df = pd.merge(
        status_df, job_submit_df, on=merge_on, how='left', suffixes=('', '_batch')
    )

    # Updated which jobs have failed. If they have been submitted, do not have results,
    # and are not currently running, they have failed.
    currently_running = updated_status_df['state_batch'].isin(['PD', 'R'])
    submitted_no_results = updated_status_df['submitted'] & ~updated_status_df['has_results']
    updated_status_df['is_failed'] = submitted_no_results & ~currently_running

    update_mask = (
        updated_status_df['job_id'] != updated_status_df['job_id_batch']
    ) & updated_status_df['job_id_batch'].notna()

    for update_col in [
        'job_id',
        'task_id',
        'state',
        'time_used',
        'time_limit',
        'nodes',
        'cpus',
        'partition',
        'name',
    ]:
        # Update job_id where update_mask is True
        updated_status_df.loc[update_mask, update_col] = updated_status_df.loc[
            update_mask, f'{update_col}_batch'
        ]

    # Drop the batch columns
    updated_status_df = updated_status_df.drop(
        columns=[col for col in updated_status_df.columns if col.endswith('_batch')]
    )

    return updated_status_df
