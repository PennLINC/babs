from importlib import resources

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
    assert 'hard_memory_limit' in system.dict
    assert 'number_of_cpus' in system.dict
    assert 'hard_runtime_limit' in system.dict


def test_invalid_system_type():
    """Test that System raises a ValueError for invalid type"""
    with pytest.raises(ValueError, match="Invalid cluster system type: 'invalid_system'!"):
        System('invalid_system')


def test_config_file_exists():
    """Test that the dict_cluster_systems.yaml file exists in the expected location"""
    # Check that the file exists and can be loaded as YAML
    with resources.files('babs').joinpath('dict_cluster_systems.yaml').open() as f:
        config = yaml.safe_load(f)

    # Check that expected system types are in the config
    assert 'slurm' in config
