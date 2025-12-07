import os.path as op
import re
import subprocess
from io import StringIO

import pandas as pd
import yaml

from babs.utils import get_username, scheduler_status_columns, status_dtypes


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
    if result.returncode == 1 and 'Invalid job id specified' in result.stderr:
        print('No jobs in the queue')
        return pd.DataFrame(columns=scheduler_status_columns)
    if result.returncode != 0:
        raise RuntimeError(
            f'squeue command failed with return code {result.returncode}\nstderr: {result.stderr}'
        )

    # Print the full squeue output for debugging
    # print('\nFull squeue output:')
    # print(result.stdout)

    # Handle empty output
    if not result.stdout.strip():
        # print('Warning: squeue returned empty output')
        # Return empty DataFrame with correct columns
        return pd.DataFrame(columns=scheduler_status_columns)

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
    if not all(col in df.columns for col in scheduler_status_columns):
        raise RuntimeError(
            f'Unexpected DataFrame columns.\n\nExpected: {scheduler_status_columns},\n'
            f'got: {df.columns.tolist()}'
        )
    # reorder the columns to be standard
    df = df[scheduler_status_columns]

    # Convert only problematic columns
    for col in ['state', 'time_used', 'time_limit', 'partition', 'name']:
        if col in df.columns and col in status_dtypes:
            df[col] = df[col].astype(status_dtypes[col])

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
    # sections in this template yaml file:
    cmd_template = templates['cmd_template']
    cmd = cmd_template.replace('${max_array}', f'{maxarray}')

    if queue == 'slurm':
        job_id = sbatch_get_job_id(cmd.split(), analysis_path)
    else:
        raise Exception('Invalid job scheduler system type `queue`: ' + queue)

    return job_id


def submit_one_test_job(analysis_path, queue):
    """
    This is to submit one *test* job.
    This is used by `babs check-setup`.

    Parameters:
    ----------------
    analysis_path: str
        path to the `analysis` folder. One attribute in class `BABS`
    queue: str
        the type of job scheduling system, "sge" or "slurm"

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
    # sections in this template yaml file:
    cmd = templates['cmd_template']

    if queue == 'slurm':
        job_id = sbatch_get_job_id(cmd.split(), analysis_path)
    else:
        raise Exception('Invalid job scheduler system type `queue`: ' + queue)
    print(f'Test job has been submitted (job ID: {job_id}).')

    return job_id


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
    from jinja2 import Environment, PackageLoader, StrictUndefined

    env = Environment(
        loader=PackageLoader('babs', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    template = env.get_template('job_status_report.jinja')

    total_jobs = current_results_df.shape[0]
    total_submitted = int(current_results_df['submitted'].sum())
    total_is_done = int(current_results_df['has_results'].sum())
    total_pending = int((currently_running_df['state'] == 'PD').sum())
    total_running = int((currently_running_df['state'] == 'R').sum())
    total_failed = int(current_results_df['is_failed'].sum())

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
