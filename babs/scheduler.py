import os.path as op
import re
import subprocess
from io import StringIO

import numpy as np
import pandas as pd
import yaml
from filelock import FileLock, Timeout

from babs.utils import get_username

scheduler_status_dtype = {
    'job_id': 'Int64',
    'task_id': 'Int64',
    'log_filename': 'str',
    'submitted': 'boolean',
    'has_results': 'boolean',
    'is_failed': 'boolean',
    'needs_resubmit': 'boolean',
    'last_line_stdout_file': 'str',
    'state': 'str',
    'time_used': 'str',
    'alert_message': 'str',
}

status_columns = [
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


def squeue_to_pandas(job_id=None) -> pd.DataFrame:
    """Get Slurm queue status and parse it into a pandas DataFrame.

    Parameters
    ----------
    job_id: int or None
        the job id to request status for

    Returns
    -------
    pd.DataFrame
        DataFrame containing job information with columns:
        - job_id: Job ID
        - task_id: Task ID
        - state: Job state
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
    squeue_columns = [
        # job_id is {array_id}_{task_id}: it will be split later
        'job_id',
        'state',
        'time_used',
        'time_limit',
        'nodes',
        'cpus',
        'partition',
        'name',
    ]
    # Get current username
    username = get_username()

    commandlist = [
        'squeue',
        '-u',
        username,
        '-r',  # Show all array tasks
        '--noheader',  # Skip header line
        '--format=%i|%t|%M|%l|%D|%C|%P|%j',  # Custom format with pipe delimiter
    ]
    if job_id is not None:
        commandlist.append(f'-j{job_id}')

    # Get job status with custom format for easy parsing
    result = subprocess.run(
        commandlist,
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
        return pd.DataFrame(columns=status_columns)

    try:
        # Parse the output into a DataFrame
        df = pd.read_csv(
            StringIO(result.stdout),
            sep='|',
            names=squeue_columns,
            skipinitialspace=True,
        )
    except Exception as e:
        raise RuntimeError(f'Failed to parse squeue output: {str(e)}\nOutput was: {result.stdout}')

    # separate job_id into job_id and task_id
    df['task_id'] = df['job_id'].str.split('_').str[1].astype(int)
    df['job_id'] = df['job_id'].str.split('_').str[0].astype(int)

    # Validate DataFrame structure
    if not all(col in df.columns for col in status_columns):
        raise RuntimeError(
            f'Unexpected DataFrame columns. Expected: {status_columns}, got: {df.columns.tolist()}'
        )
    # reorder the columns to be standard
    df = df[status_columns]

    return df


def sbatch_get_job_id(sbatch_cmd_list, working_dir):
    """
    Robustly submit a SLURM sbatch command and get the job id

    Parameters
    ----------
    sbatch_cmd_list: list
        the command to submit the job
    working_dir: str
        the working directory to run the command from

    Returns
    -------
    int
        the job id
    """
    # run the command, get the job id:
    proc_cmd = subprocess.run(
        sbatch_cmd_list,
        cwd=working_dir,
        capture_output=True,
        text=True,
    )
    if proc_cmd.returncode != 0:
        raise RuntimeError(f'Failed to submit array job: {proc_cmd.stderr}')

    # Get the job id from the output
    msg = proc_cmd.stdout
    # Extract job ID using regex
    job_id_match = re.search(r'Submitted batch job (\d+)', msg)
    if not job_id_match:
        raise RuntimeError(f'Could not find job ID in message: {msg}')
    return int(job_id_match.group(1))


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


def submit_array(analysis_path, queue, maxarray):
    """
    This is to submit a job array based on template yaml file.

    Parameters
    ----------
    analysis_path: str
        path to the `analysis` folder. One attribute in class `BABS`
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
    cmd = cmd_template.replace('${max_array}', f'{maxarray}')

    if queue == 'slurm':
        job_id = sbatch_get_job_id(cmd.split(), analysis_path)
    else:
        raise Exception('Invalid job scheduler system type `queue`: ' + queue)

    return job_id


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
        whether the submitted field has to be updated
    done: bool or None
        whether the has_results field has to be updated
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
        df_jobs.loc[mask, 'state'] = row['state']
        df_jobs.loc[mask, 'state'] = row['state']
        df_jobs.loc[mask, 'time_used'] = row['time_used']
        if submitted is not None:
            # update the status:
            df_jobs.loc[mask, 'submitted'] = row['submitted']
        if done is not None:
            # update the status:
            df_jobs.loc[mask, 'has_results'] = row['has_results']
        if debug:
            df_jobs.loc[mask, 'last_line_stdout_file'] = row['last_line_stdout_file']
            df_jobs.loc[mask, 'alert_message'] = row['alert_message']
    return df_jobs


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

    if queue == 'slurm':
        job_id = sbatch_get_job_id(cmd.split(), analysis_path)
    else:
        raise Exception('Invalid job scheduler system type `queue`: ' + queue)
    print(f'Test job has been submitted (job ID: {job_id}).')

    return job_id


def create_job_status_csv(babs):
    """
    This is to create a CSV file of `job_status`.
    This should be used by `babs submit` and `babs status`.

    Parameters:
    ------------
    babs: class `BABS`
        information about a BABS project.
    """
    if op.exists(babs.job_status_path_abs):
        return

    # Load the complete list of subjects and optionally sessions
    df_sub = pd.read_csv(babs.list_sub_path_abs)
    df_job = df_sub.copy()  # deep copy of pandas df

    df_job['job_id'] = -1  # int
    df_job['task_id'] = -1  # int
    df_job['submitted'] = False
    df_job['state'] = np.nan
    df_job['time_used'] = np.nan
    df_job['time_limit'] = np.nan
    df_job['nodes'] = np.nan
    df_job['cpus'] = np.nan
    df_job['partition'] = np.nan
    df_job['name'] = np.nan
    df_job['has_results'] = False  # = has branch in output_ria
    # Fields for tracking:
    df_job['needs_resubmit'] = False
    df_job['is_failed'] = np.nan
    df_job['log_filename'] = np.nan
    df_job['last_line_stdout_file'] = np.nan
    df_job['alert_message'] = np.nan

    # Save the df as csv file, using lock:
    lock = FileLock(f'{babs.job_status_path_abs}.lock')
    try:
        with lock.acquire(timeout=5):
            df_job.to_csv(babs.job_status_path_abs, index=False)
    except Timeout:  # after waiting for time defined in `timeout`:
        # if another instance also uses locks, and is currently running,
        #   there will be a timeout error
        print('Another instance of this application currently holds the lock.')


def report_job_status(current_results_df, currently_running_df, analysis_path):
    """
    Print a report that summarizes the overall status of a BABS project.

    This will show how many of the jobs have been completed,
    how many are still running, and how many have failed.

    Parameters:
    -------------
    current_results_df: pd.DataFrame
        dataframe the accurately reflects which tasks have finished
    currently_running_df: pd.DataFrame
        dataframe of currently running tasks
    analysis_path: str
        path to the `analysis` folder of a `BABS` project
    """
    from jinja2 import Environment, PackageLoader, select_autoescape

    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        autoescape=select_autoescape(),
    )
    template = env.get_template('job_status_report.jinja')

    total_jobs = current_results_df.shape[0]
    total_submitted = currently_running_df.shape[0]
    total_is_done = current_results_df['has_results'].sum()
    total_pending = (currently_running_df['state'] == 'PD').sum()
    total_running = (currently_running_df['state'] == 'R').sum()
    total_failed = (
        current_results_df['is_failed'].sum() if 'is_failed' in current_results_df else 0
    )

    print(
        template.render(
            total_jobs=total_jobs,
            total_submitted=total_submitted,
            total_is_done=total_is_done,
            total_pending=total_pending,
            total_running=total_running,
            total_failed=total_failed,
            log_path=op.join(analysis_path, 'logs'),
        )
    )


def request_all_job_status(queue, job_id=None):
    """
    This is to get all jobs' status
    using `qstat` for SGE clusters and `squeue` for Slurm

    Parameters
    ----------
    queue: str
        the type of job scheduling system, "sge" or "slurm"
    job_id: int or None
        the job id to request status for

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
        return _request_all_job_status_slurm(job_id)


def _request_all_job_status_slurm(job_id=None):
    """
    This is to get all jobs' status for Slurm
    by calling `squeue`.

    Parameters
    ----------
    job_id: int or None
        the job id to request status for
    """
    if not check_slurm_available():
        raise RuntimeError('Slurm commands are not available on this system.')
    return squeue_to_pandas(job_id)
