"""Test the check_setup functionality."""

import random
from pathlib import Path

import pytest
import yaml

from babs import BABSCheckSetup
from babs.base import CONFIG_SECTIONS
from babs.utils import read_yaml


def test_missing_config_parts(babs_project_sessionlevel):
    """Test that missing config parts raise an error."""

    babs_proj = BABSCheckSetup(babs_project_sessionlevel)
    complete_config = read_yaml(babs_proj.config_path)
    deleted_section = random.choice(CONFIG_SECTIONS)

    complete_config.pop(deleted_section)
    with open(babs_proj.config_path, 'w') as f:
        yaml.dump(complete_config, f)

    with pytest.raises(ValueError, match=f'Section {deleted_section} not found'):
        BABSCheckSetup(babs_project_sessionlevel)


def test_missing_config_path(babs_project_sessionlevel):
    """Test that missing config path raises an error."""

    babs_proj = BABSCheckSetup(babs_project_sessionlevel)
    Path(babs_proj.config_path).unlink()

    # Check setup should raise an Exception about non-writable workspace
    with pytest.raises(FileNotFoundError, match='is not a valid BABS project'):
        BABSCheckSetup(babs_project_sessionlevel)


def test_missing_directories(tmp_path_factory):
    """Test that missing analysis path raises an error."""
    project_root = tmp_path_factory.mktemp('project_root')
    with pytest.raises(FileNotFoundError, match='is not a valid BABS project'):
        BABSCheckSetup(project_root)

    not_exists = Path('/does/not/exist')
    with pytest.raises(FileNotFoundError, match='project_root` does not exist!'):
        BABSCheckSetup(not_exists)


def test_validate_pipeline_config(babs_project_sessionlevel):
    """Test _validate_pipeline_config method."""
    from babs.base import BABS

    babs_proj = BABS(babs_project_sessionlevel)

    # Test valid config
    babs_proj.pipeline = [{'container_name': 'test-app'}]
    babs_proj._validate_pipeline_config()  # Should not raise

    # Test invalid configs
    babs_proj.pipeline = {'not': 'a list'}
    with pytest.raises(ValueError, match='Pipeline configuration must be a list'):
        babs_proj._validate_pipeline_config()

    babs_proj.pipeline = []
    with pytest.raises(ValueError, match='Pipeline configuration cannot be empty'):
        babs_proj._validate_pipeline_config()

    babs_proj.pipeline = ['not a dict']
    with pytest.raises(ValueError, match='Pipeline step 0 must be a dictionary'):
        babs_proj._validate_pipeline_config()

    babs_proj.pipeline = [{'missing': 'container_name'}]
    with pytest.raises(ValueError, match='Pipeline step 0 missing required field: container_name'):
        babs_proj._validate_pipeline_config()
