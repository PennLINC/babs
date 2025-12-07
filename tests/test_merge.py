"""Test merge.py error handling and edge cases."""

import subprocess
from unittest.mock import MagicMock

import pytest

from babs.merge import BABSMerge
from babs.utils import get_git_show_ref_shasum


def test_merge_no_branches(babs_project_sessionlevel, monkeypatch):
    """Test babs_merge when no branches have results."""
    babs_proj = BABSMerge(babs_project_sessionlevel)
    monkeypatch.setattr(babs_proj, '_get_results_branches', lambda: [])

    with pytest.raises(ValueError, match='There is no successfully finished job yet'):
        babs_proj.babs_merge()


def test_merge_all_branches_no_results(babs_project_sessionlevel, tmp_path, monkeypatch):
    """Test babs_merge when all branches have no results."""
    babs_proj = BABSMerge(babs_project_sessionlevel)

    merge_ds_path = tmp_path / 'merge_ds'
    merge_ds_path.mkdir()
    subprocess.run(['git', 'init'], cwd=merge_ds_path, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=merge_ds_path, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@test.com'],
        cwd=merge_ds_path,
        capture_output=True,
    )
    (merge_ds_path / 'test.txt').write_text('test')
    subprocess.run(['git', 'add', 'test.txt'], cwd=merge_ds_path, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=merge_ds_path, capture_output=True)

    default_branch = 'main'
    try:
        subprocess.run(
            ['git', 'checkout', '-b', default_branch],
            cwd=merge_ds_path,
            capture_output=True,
        )
    except Exception:
        default_branch = 'master'

    git_ref, _ = get_git_show_ref_shasum(default_branch, merge_ds_path)

    def mock_branches():
        return ['job-123-1-sub-0001']

    def mock_key_info(flag_output_ria_only=False):
        babs_proj.analysis_dataset_id = 'test-id'

    def mock_git_ref(branch, path):
        return git_ref, f'{git_ref} refs/remotes/origin/{branch}'

    monkeypatch.setattr(babs_proj, '_get_results_branches', mock_branches)
    monkeypatch.setattr(babs_proj, 'wtf_key_info', mock_key_info)
    monkeypatch.setattr('babs.merge.get_git_show_ref_shasum', mock_git_ref)
    from babs.merge import dlapi

    monkeypatch.setattr(dlapi, 'clone', lambda source, path: None)

    def mock_remote_show(cmd, **kwargs):
        if 'remote' in cmd and 'show' in cmd:
            result = MagicMock()
            result.returncode = 0
            result.stdout = f'HEAD branch: {default_branch}\n'.encode()
            return result
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr('babs.merge.subprocess.run', mock_remote_show)

    with pytest.raises(Exception, match='There is no job branch in output RIA that has results'):
        babs_proj.babs_merge()
