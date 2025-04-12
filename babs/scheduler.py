import datetime
import os.path as op
import subprocess
from io import StringIO

import numpy as np
import pandas as pd
import yaml
from filelock import FileLock, Timeout


def check_slurm_available() -> bool:
    """Check if Slurm commands are available on the system.

    Returns
    -------
    bool
        True if both squeue and sbatch commands are available, False otherwise.

    Notes
    -----
    This function checks for the presence of both 'squeue' and 'sbatch' commands
    using the 'which' command. If either command is not found, it returns False.
    """
    try:
        subprocess.run(['which', 'squeue', 'sbatch'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def squeue_to_pandas() -> pd.DataFrame:
    """Get Slurm queue status and parse it into a pandas DataFrame.

    Returns
    -------
    pd.DataFrame
        DataFrame containing job information with columns:
        - job_id: Job ID (with array task if applicable)
        - state: Job state (single character)
        - time_used: Time used by the job
        - time_limit: Time limit for the job
        - nodes: Number of nodes allocated
        - cpus: Number of CPUs allocated
        - partition: Partition the job is running in
        - name: Job name

    Raises
    ------
    RuntimeError
        If squeue command fails or returns unexpected output.
    """
    # Get current username
    username_result = subprocess.run(['whoami'], capture_output=True, text=True)
    if username_result.returncode != 0:
        raise RuntimeError(f'Failed to get username: {username_result.stderr}')
    username = username_result.stdout.strip()

    # Get job status with custom format for easy parsing
    result = subprocess.run(
        [
            'squeue',
            '-u',
            username,
            '-r',  # Show all array tasks
            '--noheader',  # Skip header line
            '--format=%i|%t|%M|%l|%D|%C|%P|%j',  # Custom format with pipe delimiter
        ],
        capture_output=True,
        text=True,
    )

    # Check if command failed
    if result.returncode != 0:
        raise RuntimeError(
            f'squeue command failed with return code {result.returncode}\nstderr: {result.stderr}'
        )

    # Print the full squeue output for debugging
    print('\nFull squeue output:')
    print(result.stdout)

    # Handle empty output
    if not result.stdout.strip():
        print('Warning: squeue returned empty output')
        # Return empty DataFrame with correct columns
        return pd.DataFrame(
            columns=[
                'job_id',
                'state',
                'time_used',
                'time_limit',
                'nodes',
                'cpus',
                'partition',
                'name',
            ]
        )

    try:
        # Parse the output into a DataFrame
        df = pd.read_csv(
            StringIO(result.stdout),
            sep='|',
            names=[
                'job_id',
                'state',
                'time_used',
                'time_limit',
                'nodes',
                'cpus',
                'partition',
                'name',
            ],
            skipinitialspace=True,
        )

        # Validate DataFrame structure
        expected_columns = [
            'job_id',
            'state',
            'time_used',
            'time_limit',
            'nodes',
            'cpus',
            'partition',
            'name',
        ]
        if not all(col in df.columns for col in expected_columns):
            raise RuntimeError(
                f'Unexpected DataFrame columns. Expected: {expected_columns}, '
                f'got: {df.columns.tolist()}'
            )

        return df

    except Exception as e:
        raise RuntimeError(f'Failed to parse squeue output: {str(e)}\nOutput was: {result.stdout}')


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
    log_filename_list: list
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
        capture_output=True,
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
    if df_job_specified is not None:
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

        # Create df_job_submit from the collected job indices
        if job_ind_list:
            df_job_submit = df_job.iloc[job_ind_list].copy().reset_index(drop=True)
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
        capture_output=True,
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
        raise NotImplementedError('SGE is not supported anymore.')
    elif queue == 'slurm':
        return _request_all_job_status_slurm()


def _request_all_job_status_slurm():
    """
    This is to get all jobs' status for Slurm
    by calling `squeue`.
    """
    if not check_slurm_available():
        raise RuntimeError('Slurm commands are not available on this system.')
    return squeue_to_pandas()


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
