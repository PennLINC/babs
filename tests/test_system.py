import os.path as op

import pytest
import yaml

from babs.system import System


def test_system_initialization():
    """Test that System initializes with a valid type"""
    system = System('slurm')
    assert system.type == 'slurm'
    assert isinstance(system.dict, dict)


def test_system_get_dict():
    """Test that System.get_dict() properly loads the config file"""
    system = System('slurm')

    # Check that essential keys exist
    assert 'interpreting_shell' in system.dict
    assert 'hard_memory_limit' in system.dict
    assert 'number_of_cpus' in system.dict
    assert 'hard_runtime_limit' in system.dict


def test_invalid_system_type():
    """Test that System raises a ValueError for invalid type"""
    with pytest.raises(ValueError, match="Invalid cluster system type: 'invalid_system'!"):
        System('invalid_system')


def test_config_file_exists():
    """Test that the dict_cluster_systems.yaml file exists in the expected location"""
    # Get the location of babs package
    import babs

    babs_path = op.dirname(babs.__file__)

    # Check that the file exists
    config_path = op.join(babs_path, 'dict_cluster_systems.yaml')
    assert op.exists(config_path), f'Config file not found at {config_path}'

    # Check that the file can be loaded as YAML
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Check that expected system types are in the config
    assert 'slurm' in config
