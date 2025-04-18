"""Test the template_test_job.py functionality."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def test_template_job_execution():
    """Test that template_test_job.py can be copied and executed successfully."""
    # Get the path to the template file
    template_path = Path(__file__).parent.parent / 'babs' / 'template_test_job.py'

    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy the template file to a temporary directory
        temp_job = Path(temp_dir) / 'test_job.py'
        shutil.copy2(template_path, temp_job)

        # Create a check_setup directory
        check_setup_dir = Path(temp_dir) / 'check_setup'
        check_setup_dir.mkdir()

        # Execute the copied file with required arguments
        result = subprocess.run(
            [
                sys.executable,
                str(temp_job),
                '--path-workspace',
                str(temp_dir),
                '--path-check-setup',
                str(check_setup_dir),
            ],
            capture_output=True,
            text=True,
            env={**os.environ, 'RUNNING_PYTEST': '1'},  # Mark as running in test
        )

        # Check that execution was successful
        assert result.returncode == 0, f'Template job failed with:\n{result.stderr}'

        # Check that the YAML file was created
        yaml_file = check_setup_dir / 'check_env.yaml'
        assert yaml_file.exists(), 'YAML file was not created'

        # Read and check the YAML file contents
        with open(yaml_file) as f:
            yaml_content = f.read()
            assert 'workspace_writable:' in yaml_content
            assert 'which_python:' in yaml_content
            assert 'version:' in yaml_content

        # Check that no errors were reported
        assert not result.stderr, f'Template job produced errors:\n{result.stderr}'
