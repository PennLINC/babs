"""Utils and helper functions"""

import copy
import getpass
import os
import subprocess
import warnings
from importlib.metadata import version

import pandas as pd
import yaml
from filelock import FileLock, Timeout

RUNNING_PYTEST = os.environ.get('RUNNING_PYTEST', '0') == '1'

status_dtypes = {
    'job_id': 'Int64',
    'task_id': 'Int64',
    'state': 'str',
    'time_used': 'str',
    'time_limit': 'str',
    'nodes': 'Int64',
    'cpus': 'Int64',
    'partition': 'str',
    'name': 'str',
    'submitted': 'boolean',
    'has_results': 'boolean',
    'is_failed': 'boolean',
    'sub_id': 'str',
    'ses_id': 'str',
}


def get_latest_submitted_jobs_columns(processing_level):
    if processing_level == 'subject':
        return ['sub_id', 'job_id', 'task_id']
    elif processing_level == 'session':
        return ['sub_id', 'ses_id', 'job_id', 'task_id']
    else:
        raise ValueError(f'Invalid processing level: {processing_level}')


scheduler_status_columns = [
    'job_id',
    'task_id',
    'state',
    'time_used',
    'time_limit',
    'nodes',
    'cpus',
    'partition',
    'name',
]

results_status_columns = [
    'submitted',
    'has_results',
    'is_failed',
] + scheduler_status_columns

results_status_default_values = {
    'submitted': False,
    'has_results': False,
    'is_failed': False,
    'job_id': -1,
    'task_id': -1,
    'state': '',
    'time_used': '',
    'time_limit': '',
    'nodes': 0,
    'cpus': 0,
    'partition': '',
    'name': '',
}


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
        except Timeout:  # after waiting for time defined in `timeout`:
            # if another instance also uses locks, and is currently running,
            #   there will be a timeout error
            print('Another instance of this application currently holds the lock.')
            # Still read the file even if lock times out
            with open(fn) as f:
                config = yaml.safe_load(f)
    else:
        with open(fn) as f:
            config = yaml.safe_load(f)
            # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`

    return config


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
    else:
        replaced = value

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
    Get branch list from git repository.

    If no branches are found, an empty list is returned.

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

    return branches


def results_branch_dataframe(branches, processing_level) -> pd.DataFrame:
    """
    Create a dataframe from a list of branches.

    Parameters:
    --------------
    branches: list
        list of branches
    processing_level: str
        processing level

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
        r'job-(?P<job_id>\d+)-?(?P<task_id>\d+)?[-]'
        r'(?P<sub_id>sub-[^-]+)(?:-(?P<ses_id>ses-[^-]+))?'
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
    if processing_level == 'session':
        columns = ['job_id', 'task_id', 'sub_id', 'ses_id', 'has_results']
    else:
        columns = ['job_id', 'task_id', 'sub_id', 'has_results']

    if df.empty:
        return pd.DataFrame(columns=columns)

    for column_name in columns:
        df[column_name] = df[column_name].astype(status_dtypes[column_name])

    return df[columns]


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


def update_results_status(
    previous_job_completion_df, job_completion_df, merged_zip_completion_df=None
):
    """
    Update a status dataframe with a results branch dataframe.

    Parameters:
    --------------
    previous_job_completion_df: pd.DataFrame
        previous job completion dataframe
    job_completion_df: pd.DataFrame
        job completion dataframe from results_branch_dataframe()
    merged_zip_completion_df: pd.DataFrame or None
        job completion dataframe from BABS._get_merged_results_from_analysis_dir()

    Returns:
    -------------
    df: pd.DataFrame
        updated job status dataframe

    """
    # Determine if we should use ses_id for merging
    # Check previous_df and both completion dataframes
    use_sesid = 'ses_id' in previous_job_completion_df
    if use_sesid:
        # Check if either completion dataframe has ses_id
        # If job_completion_df is empty, check merged_zip_completion_df to determine columns
        has_sesid_in_job = not job_completion_df.empty and 'ses_id' in job_completion_df
        has_sesid_in_merged = (
            merged_zip_completion_df is not None
            and not merged_zip_completion_df.empty
            and 'ses_id' in merged_zip_completion_df
        )
        # If previous_df has ses_id but neither completion df has it, don't use ses_id for merge
        if not (has_sesid_in_job or has_sesid_in_merged):
            use_sesid = False

    merge_on = ['sub_id', 'ses_id'] if use_sesid else ['sub_id']

    # If we have a merged zip completion dataframe,
    # we need to concatenate it with the job completion dataframe
    if merged_zip_completion_df is not None and not merged_zip_completion_df.empty:
        merged_df = merged_zip_completion_df.copy()
        merged_df['has_results'] = True
        merged_df['task_id'] = pd.NA
        merged_df['job_id'] = pd.NA

        # Ensure both dataframes have the same columns before concatenation
        if job_completion_df.empty:
            job_completion_df = pd.DataFrame(columns=merged_df.columns)
        elif merged_df.empty:
            merged_df = pd.DataFrame(columns=job_completion_df.columns)

        job_completion_df = pd.concat([job_completion_df, merged_df], axis=0, ignore_index=True)

    # The job and task ids all need to be cleared out and replaced with the new ones
    # from the job_completion_df, which is based on the latest results branches
    updated_results_df = pd.merge(
        previous_job_completion_df.drop(columns=['has_results']),
        job_completion_df,
        on=merge_on,
        how='left',
        suffixes=('', '_completion'),
    )

    # Update the job_id and task_id columns
    for col in ['job_id', 'task_id']:
        update_mask = updated_results_df[col + '_completion'].notna()
        updated_results_df.loc[update_mask, col] = updated_results_df.loc[
            update_mask, col + '_completion'
        ]
        # For merged zip completion, job_id and task_id should be NA even if not in completion df
        # This happens when has_results is True but job_id/task_id_completion are NA
        merged_zip_mask = (
            updated_results_df['has_results'].fillna(False)
            & updated_results_df[col + '_completion'].isna()
        )
        updated_results_df.loc[merged_zip_mask, col] = pd.NA

    # Fill NaN values with appropriate defaults
    # Convert to Python boolean for compatibility with 'is True' checks in tests
    # Use object dtype to store Python booleans instead of numpy booleans
    has_results_list = [
        bool(x) if pd.notna(x) else False for x in updated_results_df['has_results'].fillna(False)
    ]
    updated_results_df['has_results'] = pd.Series(has_results_list, dtype=object)
    updated_results_df['submitted'] = (
        updated_results_df['submitted'].astype('boolean').fillna(False)
    )
    updated_results_df['state'] = updated_results_df['state'].fillna('')

    # Now compute is_failed with NaN-safe operations
    updated_results_df['is_failed'] = (
        updated_results_df['submitted']
        & ~updated_results_df['has_results']
        & ~updated_results_df['state'].isin(['PD', 'R'])
    )

    # Drop the completion columns
    updated_results_df = updated_results_df.drop(
        columns=['job_id_completion', 'task_id_completion']
    )

    return updated_results_df


def update_submitted_job_ids(results_df, submitted_df):
    """Update the most recent job and task ids in the status df.

    This is a quick update after submitting jobs when we freshly know the job_id
    and don't need to query anything.
    """
    if 'sub_id' not in submitted_df:
        raise ValueError('job_submit_df must have a sub_id column')

    # There should be only one job id per submitted job
    submitted_job_id = submitted_df['job_id'].unique()
    if len(submitted_job_id) != 1:
        raise ValueError('There should be only one job id per submitted job')
    submitted_job_id = int(submitted_job_id[0])

    use_sesid = 'ses_id' in results_df and 'ses_id' in submitted_df
    merge_on = ['sub_id', 'ses_id'] if use_sesid else ['sub_id']
    merged = pd.merge(results_df, submitted_df, on=merge_on, how='left', suffixes=('', '_batch'))
    # Updated which jobs have failed. If they have been submitted, do not have results,
    # and are not currently running, they have failed.
    updated_mask = merged['job_id_batch'] == submitted_job_id

    merged.loc[updated_mask, 'job_id'] = merged.loc[updated_mask, 'job_id_batch']
    merged.loc[updated_mask, 'task_id'] = merged.loc[updated_mask, 'task_id_batch']
    merged.drop(columns=['job_id_batch', 'task_id_batch'], inplace=True)
    merged.loc[updated_mask, 'submitted'] = True
    return merged


def update_job_batch_status(status_df, job_submit_df):
    """
    Update the status dataframe with the job submission information.

    Parameters:
    -----------
    status_df: pd.DataFrame
        status dataframe. Be sure has_results is up to date.
    job_submit_df: pd.DataFrame
        the current status of job submission: must have

    Returns:
    --------
    pd.DataFrame
        updated status dataframe

    """

    if job_submit_df.empty:
        return status_df

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
        updated_status_df.loc[currently_running, update_col] = updated_status_df.loc[
            currently_running, f'{update_col}_batch'
        ].astype(status_dtypes[update_col])

    # Drop the batch columns
    updated_status_df = updated_status_df.drop(
        columns=[col for col in updated_status_df.columns if col.endswith('_batch')]
    )

    # replace NaN with False in has_results
    updated_status_df['has_results'] = (
        updated_status_df['has_results'].astype('boolean').fillna(False)
    )

    # Update some of the dynamic columns
    updated_status_df['is_failed'] = (
        updated_status_df['submitted']
        & ~updated_status_df['has_results']
        & ~updated_status_df['state'].isin(['PD', 'R'])
    )

    return updated_status_df


def get_repo_hash(repo_path):
    """
    Get the hash of the current commit of a git repository.

    Parameters:
    --------------
    repo_path: str
        path to the git repository

    Returns:
    -------------
    hash: str
        the hash of the current commit
    """
    proc_hash = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=repo_path, capture_output=True, text=True
    )
    if proc_hash.returncode != 0:
        raise ValueError(
            f'Error getting the hash of the current commit in {repo_path}: {proc_hash.stderr}'
        )
    return proc_hash.stdout.strip()


def compare_repo_commit_hashes(repo1, repo2, repo1_name, repo2_name, raise_error=True):
    """
    Compare the commit hashes of two git repositories.
    """
    hash1 = get_repo_hash(repo1)
    hash2 = get_repo_hash(repo2)
    message = (
        f'The hash of current commit of `{repo1_name}` datalad dataset does not match'
        f' with that of `{repo2_name}`.'
        f' {repo1_name} = {hash1};'
        f' {repo2_name} = {hash2}.'
        'It might be because that latest commits in'
        f'  {repo1_name} were not pushed to {repo2_name}.'
        f" Try running this command in directory '{repo1}': \n"
        '$ datalad push --to input'
    )
    if hash1 != hash2:
        if raise_error:
            raise ValueError(message)
        else:
            warnings.warn(message, stacklevel=2)
    return hash1 == hash2


def parse_select_arg(select_arg):
    """
    Parse the --select argument.

    Parameters:
    -----------
    select_arg: list
        list of select arguments

    Returns:
    --------
    select_arg: pd.DataFrame
        dataframe of the inclusion list


    """

    # argparse with action='append' and nargs='+' produces a list of lists.
    # Flatten here so downstream logic can assume a flat list.
    def flatten(items):
        """Recursively flatten nested lists and tuples."""
        flat_list = []
        for item in items:
            if isinstance(item, list | tuple):
                flat_list.extend(flatten(item))
            else:
                flat_list.append(item)
        return flat_list

    if isinstance(select_arg, str):
        flat_list = [select_arg]
    else:
        flat_list = flatten(select_arg)

    all_subjects = all(isinstance(item, str) and item.startswith('sub-') for item in flat_list)

    if all_subjects:
        return pd.DataFrame({'sub_id': flat_list})

    if len(flat_list) % 2 == 1:
        raise ValueError(
            'When selecting specific sessions, include the subject ID and session ID'
            ' separated by a space. Even if selecting multiple sessions per subject '
            ' the subject ID must come first'
        )

    selection_df = pd.DataFrame(
        {
            'sub_id': flat_list[::2],
            'ses_id': flat_list[1::2],
        }
    )

    # Check all items in the sub_id column start with sub-
    if not all(selection_df['sub_id'].str.startswith('sub-')):
        raise ValueError('All subject IDs must start with "sub-"')

    # Check all items in the ses_id column start with ses-
    if not all(selection_df['ses_id'].str.startswith('ses-')):
        raise ValueError('All session IDs must start with "ses-"')

    return selection_df


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
        raise Exception(
            f'Error reading `{processing_inclusion_file}`: '
            f"There is no 'sub_id' column in the CSV file!"
        )

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
