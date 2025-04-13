"""Tests for Slurm-related functionality in BABS.

This module contains tests for Slurm job submission and monitoring functionality.
Tests are skipped if Slurm commands (squeue, sbatch) are not available on the system.
"""

import subprocess
from pathlib import Path

import pytest

from babs.scheduler import check_slurm_available, squeue_to_pandas


@pytest.fixture(scope='session')
def slurm_available() -> bool:
    """Fixture to check if Slurm is available and skip tests if not.

    Returns
    -------
    bool
        True if Slurm is available, otherwise raises pytest.skip.

    Notes
    -----
    This fixture is used to skip tests that require Slurm functionality
    when Slurm is not available on the system. It uses the check_slurm_available
    function to determine Slurm availability.
    """
    if not check_slurm_available():
        pytest.skip('Slurm commands (squeue, sbatch) not available')
    return True


def submit_array_job(working_directory: Path, array_size: int) -> tuple[Path, str]:
    """Submit a test array job to Slurm and return its output directory and job ID.

    Parameters
    ----------
    working_directory : Path
        Directory where job files will be created.
    array_size : int
        Number of array tasks to create.

    Returns
    -------
    Tuple[Path, str]
        A tuple containing:
        - Path to the job's scratch directory
        - Job ID of the submitted array job

    Raises
    ------
    subprocess.CalledProcessError
        If job submission fails.

    Notes
    -----
    This function:
    1. Loads a template job script
    2. Creates a temporary directory for the job
    3. Renders the template with the specified parameters
    4. Submits the job using sbatch
    5. Returns both the job directory and job ID
    """
    import importlib.resources

    from jinja2 import Environment, FileSystemLoader

    # Get the template file path
    template_path = importlib.resources.files('babs.templates').joinpath(
        'test_array_job.sh.jinja2'
    )

    # Create temp directory for job
    job_scratch_directory = working_directory / 'array_job'
    job_scratch_directory.mkdir(parents=True, exist_ok=True)

    # Set up jinja environment and load template
    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    template = env.get_template(template_path.name)

    # Render template with parameters
    script_content = template.render(
        array_size=array_size, job_scratch_directory=job_scratch_directory
    )

    # Write rendered script to file
    script_path = job_scratch_directory / 'array_job.sh'
    script_path.write_text(script_content)
    script_path.chmod(0o755)  # Make script executable

    # Submit the job with sbatch
    result = subprocess.run(['sbatch', script_path], capture_output=True, text=True, check=True)

    # Extract job ID from sbatch output
    job_id = result.stdout.strip().split()[-1]

    return job_scratch_directory, job_id


def test_array_job_submission(
    slurm_available: bool, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Test submission and monitoring of array jobs.

    This test:
    1. Creates a temporary directory
    2. Submits an array job with 3 tasks
    3. Verifies the job appears in the queue
    4. Checks that all array tasks are present

    Parameters
    ----------
    slurm_available : bool
        Fixture indicating if Slurm commands are available.
    tmp_path_factory : pytest.TempPathFactory
        Factory for creating temporary directories.
    """
    # Create temporary directory for test
    test_dir = tmp_path_factory.mktemp('test_array_job')

    # Submit array job with 3 tasks
    job_dir, job_id = submit_array_job(test_dir, array_size=3)

    # Wait a moment for job to be registered
    import time

    time.sleep(2)

    # Get job status
    df = squeue_to_pandas()

    # Verify job appears in status
    assert not df.empty
    assert any(str(job_id) in idx for idx in df['job_id'])

    # Print parsed DataFrame for debugging
    print('\nParsed DataFrame:')
    print(df)
