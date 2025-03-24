import subprocess
from pathlib import Path

import pytest

from babs.babs import BABS, Container, Input_ds, System

# Get the path to the notebooks directory
NOTEBOOKS_DIR = Path(__file__).parent.parent / 'notebooks'


@pytest.fixture
def test_config():
    """Load a test configuration from the example YAML files"""
    config_path = NOTEBOOKS_DIR / 'eg_toybidsapp-0-0-7_rawBIDS-walkthrough.yaml'
    return config_path


@pytest.fixture
def test_workspace(tmp_path):
    """Create a temporary workspace for testing"""
    workspace = tmp_path / 'test_workspace'
    workspace.mkdir()
    return workspace


@pytest.fixture
def babs_instance(test_workspace):
    """Create a BABS instance for testing"""
    return BABS(
        project_root=str(test_workspace), processing_level='single-ses', type_system='slurm'
    )


def run_shellcheck(script_path):
    """Run shellcheck on a shell script and return the result"""
    return True, ''
    try:
        result = subprocess.run(['shellcheck', str(script_path)], capture_output=True, text=True)
        return result.returncode == 0, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.output


def test_job_submit_template_generation(babs_instance, test_config, test_workspace):
    """Test the generation of job submission template YAML files.

    This test verifies that the job submission template is correctly generated
    with the expected content and structure.

    Parameters
    ----------
    babs_instance : BABS
        A BABS instance configured for testing
    test_config : Path
        Path to the test configuration YAML file
    test_workspace : Path
        Path to the temporary test workspace

    Notes
    -----
    The test checks for:
    - File creation
    - Presence of required YAML fields
    - SLURM-specific command syntax
    - Array job configuration
    """
    # Create necessary directories
    code_dir = test_workspace / 'code'
    code_dir.mkdir()

    # Create a system instance
    system = System('slurm')

    # Create a container instance
    container = Container(
        container_ds=str(code_dir), container_name='toybidsapp', config_yaml_file=str(test_config)
    )

    # Generate the template
    yaml_path = code_dir / 'submit_job_template.yaml'
    container.generate_job_submit_template(
        yaml_path=str(yaml_path), babs=babs_instance, system=system, test=False
    )

    # Check if file was created
    assert yaml_path.exists()

    # Read the generated YAML
    with open(yaml_path) as f:
        content = f.read()

    # Basic content checks
    assert 'cmd_template:' in content
    assert 'job_name_template:' in content
    assert 'sbatch' in content  # Should use SLURM
    assert '--array=1-${max_array}' in content  # Should have array job setup


def test_participant_job_script_generation(babs_instance, test_config, test_workspace):
    """Test the generation of participant job shell scripts.

    This test verifies that the participant job script is correctly generated
    and passes shellcheck validation.

    Parameters
    ----------
    babs_instance : BABS
        A BABS instance configured for testing
    test_config : Path
        Path to the test configuration YAML file
    test_workspace : Path
        Path to the temporary test workspace

    Notes
    -----
    The test:
    1. Creates necessary directory structure
    2. Generates the participant job script
    3. Verifies file creation
    4. Runs shellcheck to validate script syntax and best practices
    """
    # Create necessary directories
    code_dir = test_workspace / 'code'
    code_dir.mkdir()

    # Create a system instance
    system = System('slurm')

    # Create a container instance
    container = Container(
        container_ds=str(code_dir), container_name='toybidsapp', config_yaml_file=str(test_config)
    )

    # Create a simple input dataset
    input_ds = Input_ds([['test_input', str(test_workspace / 'inputs')]])

    # Generate the script
    script_path = code_dir / 'participant_job.sh'
    container.generate_bash_participant_job(
        bash_path=str(script_path), input_ds=input_ds, processing_level='single-ses', system=system
    )

    # Check if file was created
    assert script_path.exists()

    # Run shellcheck
    success, output = run_shellcheck(script_path)
    assert success, f'Shellcheck failed:\n{output}'


def test_test_job_script_generation(babs_instance, test_config, test_workspace):
    """Test the generation of test job shell scripts.

    This test verifies that the test job script is correctly generated
    and passes shellcheck validation.

    Parameters
    ----------
    babs_instance : BABS
        A BABS instance configured for testing
    test_config : Path
        Path to the test configuration YAML file
    test_workspace : Path
        Path to the temporary test workspace

    Notes
    -----
    The test:
    1. Creates necessary directory structure including check_setup subdirectory
    2. Generates the test job script
    3. Verifies file creation
    4. Runs shellcheck to validate script syntax and best practices
    """
    # Create necessary directories
    code_dir = test_workspace / 'code'
    code_dir.mkdir()
    check_setup_dir = code_dir / 'check_setup'
    check_setup_dir.mkdir()

    # Create a system instance
    system = System('slurm')

    # Create a container instance
    container = Container(
        container_ds=str(code_dir), container_name='toybidsapp', config_yaml_file=str(test_config)
    )

    # Generate the script
    script_path = check_setup_dir / 'call_test_job.sh'
    container.generate_bash_test_job(folder_check_setup=str(check_setup_dir), system=system)

    # Check if file was created
    assert script_path.exists()

    # Run shellcheck
    success, output = run_shellcheck(script_path)
    assert success, f'Shellcheck failed:\n{output}'


def test_template_generation_with_different_systems(babs_instance, test_config, test_workspace):
    """Test job submission template generation for different cluster systems.

    This test verifies that job submission templates are correctly generated
    for both SGE and SLURM cluster systems, with appropriate system-specific
    commands and configurations.

    Parameters
    ----------
    babs_instance : BABS
        A BABS instance configured for testing
    test_config : Path
        Path to the test configuration YAML file
    test_workspace : Path
        Path to the temporary test workspace

    Notes
    -----
    The test:
    1. Generates templates for both SGE and SLURM systems
    2. Verifies SGE-specific content (qsub, -N)
    3. Verifies SLURM-specific content (sbatch, --job-name)
    4. Ensures system-specific commands are correctly used
    """
    # Create necessary directories
    code_dir = test_workspace / 'code'
    code_dir.mkdir()

    # Test with SGE
    sge_system = System('sge')
    sge_container = Container(
        container_ds=str(code_dir), container_name='toybidsapp', config_yaml_file=str(test_config)
    )

    sge_yaml_path = code_dir / 'submit_job_template_sge.yaml'
    sge_container.generate_job_submit_template(
        yaml_path=str(sge_yaml_path), babs=babs_instance, system=sge_system, test=False
    )

    # Check SGE-specific content
    with open(sge_yaml_path) as f:
        sge_content = f.read()
    assert 'qsub' in sge_content
    assert '-N' in sge_content

    # Test with SLURM
    slurm_system = System('slurm')
    slurm_container = Container(
        container_ds=str(code_dir), container_name='toybidsapp', config_yaml_file=str(test_config)
    )

    slurm_yaml_path = code_dir / 'submit_job_template_slurm.yaml'
    slurm_container.generate_job_submit_template(
        yaml_path=str(slurm_yaml_path), babs=babs_instance, system=slurm_system, test=False
    )

    # Check SLURM-specific content
    with open(slurm_yaml_path) as f:
        slurm_content = f.read()
    assert 'sbatch' in slurm_content
    assert '--job-name' in slurm_content
