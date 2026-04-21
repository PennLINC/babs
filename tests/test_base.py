"""Test the check_setup functionality."""

import grp
import os
import os.path as op
import random
import re
import stat
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml
from conftest import get_config_simbids_path, update_yaml_for_run

from babs import BABSCheckSetup
from babs.base import BABS, CONFIG_SECTIONS
from babs.bootstrap import BABSBootstrap
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


def test_project_root_not_exists(tmp_path):
    """Test FileNotFoundError when project_root doesn't exist."""
    non_existent_path = tmp_path / 'does_not_exist'
    with pytest.raises(FileNotFoundError, match='`project_root` does not exist!'):
        BABS(non_existent_path)


def test_analysis_path_not_exists(tmp_path):
    """Test FileNotFoundError when analysis path doesn't exist."""
    project_root = tmp_path / 'project'
    project_root.mkdir()
    with pytest.raises(FileNotFoundError, match='is not a valid BABS project'):
        BABS(project_root)


def test_config_path_not_exists(babs_project_sessionlevel):
    """Test FileNotFoundError when config path doesn't exist."""
    babs_proj = BABSCheckSetup(babs_project_sessionlevel)
    Path(babs_proj.config_path).unlink()

    with pytest.raises(FileNotFoundError, match='is not a valid BABS project'):
        BABS(babs_project_sessionlevel)


def test_pipeline_config_details(babs_project_sessionlevel):
    """Test pipeline validation with config details."""
    babs_proj = BABS(babs_project_sessionlevel)

    # Test with cluster_resources, bids_app_args, singularity_args
    babs_proj.pipeline = [
        {
            'container_name': 'test-app',
            'config': {
                'cluster_resources': {'memory': '8GB', 'cpus': 4},
                'bids_app_args': {'--nthreads': 4},
                'singularity_args': ['--bind', '/tmp'],
            },
        }
    ]
    babs_proj._validate_pipeline_config()

    # Test with inter_step_cmds
    babs_proj.pipeline = [{'container_name': 'test-app', 'inter_step_cmds': ['echo "test"']}]
    babs_proj._validate_pipeline_config()

    # Test with both
    babs_proj.pipeline = [
        {
            'container_name': 'test-app',
            'config': {'cluster_resources': {'memory': '8GB'}},
            'inter_step_cmds': ['echo "test"'],
        }
    ]
    babs_proj._validate_pipeline_config()


def test_update_inclusion_empty_combine(babs_project_sessionlevel):
    """Test _update_inclusion_dataframe when combined dataframe is empty."""
    babs_proj = BABS(babs_project_sessionlevel)
    initial_inclusion_df = pd.DataFrame({'sub_id': ['sub-9999'], 'ses_id': ['ses-9999']})

    with pytest.raises(ValueError, match='No subjects/sessions to analyze!'):
        babs_proj._update_inclusion_dataframe(initial_inclusion_df=initial_inclusion_df)


def test_update_inclusion_warning(babs_project_sessionlevel, capsys):
    """Test _update_inclusion_dataframe warning when initial df has more subjects."""
    babs_proj = BABS(babs_project_sessionlevel)
    actual_df = babs_proj.input_datasets.generate_inclusion_dataframe()

    if 'ses_id' in actual_df.columns:
        initial_inclusion_df = pd.DataFrame(
            {
                'sub_id': ['sub-0001', 'sub-0002', 'sub-9999'],
                'ses_id': ['ses-01', 'ses-01', 'ses-01'],
            }
        )
    else:
        initial_inclusion_df = pd.DataFrame({'sub_id': ['sub-0001', 'sub-0002', 'sub-9999']})

    babs_proj._update_inclusion_dataframe(initial_inclusion_df=initial_inclusion_df)
    captured = capsys.readouterr()
    assert 'Warning: The initial inclusion dataframe' in captured.out


def test_datalad_save_filter_files(babs_project_sessionlevel):
    """Test datalad_save with filter_files parameter."""
    babs_proj = BABS(babs_project_sessionlevel)
    test_file = op.join(babs_proj.analysis_path, 'code', 'test_file.txt')
    Path(test_file).parent.mkdir(parents=True, exist_ok=True)
    Path(test_file).write_text('test content')

    babs_proj.datalad_save(
        path=test_file, message='Test save with filter', filter_files=['test_file.txt']
    )
    assert Path(test_file).exists()


def test_datalad_save_failure(babs_project_sessionlevel, monkeypatch):
    """Test datalad_save when save fails."""
    babs_proj = BABS(babs_project_sessionlevel)
    mock_save = MagicMock(return_value=[{'status': 'error', 'message': 'Save failed'}])
    monkeypatch.setattr(babs_proj.analysis_datalad_handle, 'save', mock_save)

    test_file = op.join(babs_proj.analysis_path, 'code', 'test_file.txt')
    Path(test_file).parent.mkdir(parents=True, exist_ok=True)
    Path(test_file).write_text('test content')

    with pytest.raises(Exception, match='`datalad save` failed!'):
        babs_proj.datalad_save(path=test_file, message='Test save')


def test_key_info_ria_only(babs_project_sessionlevel):
    """Test wtf_key_info with flag_output_ria_only=True."""
    babs_proj = BABS(babs_project_sessionlevel)
    babs_proj.wtf_key_info(flag_output_ria_only=True)
    assert babs_proj.output_ria_data_dir is not None


def test_key_info_full(babs_project_sessionlevel):
    """Test wtf_key_info with flag_output_ria_only=False."""
    babs_proj = BABS(babs_project_sessionlevel)
    babs_proj.wtf_key_info(flag_output_ria_only=False)
    assert babs_proj.output_ria_data_dir is not None
    assert babs_proj.analysis_dataset_id is not None


def test_key_info_resolves_ria_alias_symlink(babs_project_sessionlevel):
    """When the output remote URL points at the RIA store root (no .git there),
    wtf_key_info should set output_ria_data_dir to the path resolved from
    output_ria/alias/data (the symlink to the actual dataset directory).
    """
    babs_proj = BABS(babs_project_sessionlevel)
    output_ria_path = babs_proj.output_ria_path
    alias_link = op.join(output_ria_path, 'alias', 'data')
    if not op.exists(alias_link) or not os.path.islink(alias_link):
        pytest.skip('output_ria/alias/data symlink not present (e.g. bootstrap not run)')
    expected_resolved = op.realpath(alias_link)

    # Mock git remote get-url to return RIA store root (no .git there), so alias resolution runs
    ria_root_url = 'ria+file://' + output_ria_path + '\n'
    real_subprocess_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        # Intercept only the call that asks for the output RIA push URL. It looks like:
        #   cmd = ['git', '--git-dir', <path>, 'remote', 'get-url', '--push', 'output']
        # So cmd[4:6] is ['get-url', '--push'].
        if len(cmd) >= 6 and cmd[0] == 'git' and cmd[4:6] == ['get-url', '--push']:
            proc = MagicMock()
            proc.stdout = ria_root_url.encode() if isinstance(ria_root_url, str) else ria_root_url
            proc.returncode = 0
            proc.check_returncode = MagicMock()
            return proc
        return real_subprocess_run(cmd, *args, **kwargs)

    with patch('babs.base.subprocess.run', side_effect=mock_run):
        babs_proj.wtf_key_info(flag_output_ria_only=True)

    assert babs_proj.output_ria_data_dir == expected_resolved


@pytest.mark.parametrize(
    ('throttle_value', 'expected_in_template'),
    [(10, True), (None, False)],
)
def test_throttle_in_job_template(
    tmp_path_factory,
    templateflow_home,
    simbids_container_ds,
    bids_data_singlesession,
    throttle_value,
    expected_in_template,
):
    """Test that throttle value is correctly included in job submission template."""

    os.environ['TEMPLATEFLOW_HOME'] = str(templateflow_home)

    project_base = tmp_path_factory.mktemp('project')
    project_root = project_base / f'my_babs_project_{throttle_value or "none"}'
    container_config = update_yaml_for_run(
        project_base,
        get_config_simbids_path().name,
        {'BIDS': bids_data_singlesession},
    )

    babs_bootstrap = BABSBootstrap(project_root=project_root)
    babs_bootstrap.babs_bootstrap(
        processing_level='subject',
        queue='slurm',
        container_ds=simbids_container_ds,
        container_name='simbids-0-0-3',
        container_config=container_config,
        initial_inclusion_df=None,
        throttle=throttle_value,
    )

    assert babs_bootstrap.throttle == throttle_value

    template_path = op.join(babs_bootstrap.analysis_path, 'code', 'submit_job_template.yaml')
    with open(template_path) as f:
        cmd_template = yaml.safe_load(f)['cmd_template']

    assert '--array=1-${max_array}' in cmd_template
    if expected_in_template:
        assert f'%{throttle_value}' in cmd_template
    else:
        assert not re.search(r'%\d+', cmd_template)


def test_shared_group_inits_analysis_and_rias(
    tmp_path_factory,
    templateflow_home,
    simbids_container_ds,
    bids_data_singlesession,
):
    """Test --shared-group behavior for analysis and RIA creation."""

    os.environ['TEMPLATEFLOW_HOME'] = str(templateflow_home)
    shared_group = grp.getgrgid(os.getgid()).gr_name

    project_base = tmp_path_factory.mktemp('project')
    project_root = project_base / 'my_babs_project_shared_group'
    container_config = update_yaml_for_run(
        project_base,
        get_config_simbids_path().name,
        {'BIDS': bids_data_singlesession},
    )

    babs_bootstrap = BABSBootstrap(project_root=project_root)
    babs_bootstrap.babs_bootstrap(
        processing_level='subject',
        queue='slurm',
        container_ds=simbids_container_ds,
        container_name='simbids-0-0-3',
        container_config=container_config,
        initial_inclusion_df=None,
        shared_group=shared_group,
    )

    analysis_shared = subprocess.run(
        ['git', 'config', '--get', 'core.sharedrepository'],
        cwd=babs_bootstrap.analysis_path,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()
    assert analysis_shared in {'1', 'group', 'true'}

    dataset_id = babs_bootstrap.analysis_dataset_id
    assert dataset_id is not None
    ria_relpath = Path(dataset_id[:3]) / dataset_id[3:]
    output_ria_dir = Path(babs_bootstrap.output_ria_path) / ria_relpath
    input_ria_dir = Path(babs_bootstrap.input_ria_path) / ria_relpath
    for ria_dir in (output_ria_dir, input_ria_dir):
        shared_value = subprocess.run(
            ['git', '--git-dir', str(ria_dir), 'config', '--get', 'core.sharedrepository'],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout.strip()
        assert shared_value in {'1', 'group', 'true'}

    # Shared mode should generate scripts with explicit group mode 0o770.
    for check_path in (
        Path(babs_bootstrap.analysis_path) / 'code' / 'participant_job.sh',
        Path(babs_bootstrap.analysis_path) / 'code' / 'simbids-0-0-3_zip.sh',
        Path(babs_bootstrap.analysis_path) / 'code' / 'check_setup' / 'call_test_job.sh',
        Path(babs_bootstrap.analysis_path) / 'code' / 'check_setup' / 'test_job.py',
    ):
        mode = stat.S_IMODE(check_path.stat().st_mode)
        assert mode == 0o770

    safe_dirs = subprocess.run(
        ['git', 'config', '--global', '--get-all', 'safe.directory'],
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    ).stdout.splitlines()
    assert str(Path(babs_bootstrap.analysis_path).resolve()) in safe_dirs
    assert str(output_ria_dir.resolve()) in safe_dirs
