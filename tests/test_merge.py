"""Test merge.py error handling and edge cases."""

import os
import shutil
import stat
import subprocess
from unittest.mock import MagicMock, patch

import datalad.api as dlapi
import pytest

from babs.merge import BABSMerge, robust_rm_dir
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


def test_rm_dir_nonexistent(tmp_path):
    """Test robust_rm_dir when path doesn't exist."""
    nonexistent_path = tmp_path / 'nonexistent'
    # Should not raise an error
    robust_rm_dir(str(nonexistent_path))


def test_rm_dir_regular(tmp_path):
    """Test robust_rm_dir with a regular (non-datalad) directory."""
    test_dir = tmp_path / 'test_dir'
    test_dir.mkdir()
    (test_dir / 'file.txt').write_text('test')

    robust_rm_dir(str(test_dir))

    assert not test_dir.exists()


def test_rm_dir_datalad_ok(tmp_path, monkeypatch):
    """Test robust_rm_dir with datalad dataset that removes successfully."""
    test_dir = tmp_path / 'test_datalad'
    test_dir.mkdir()
    (test_dir / '.datalad').mkdir()
    (test_dir / 'file.txt').write_text('test')

    # Mock datalad.remove to succeed
    def mock_remove(path, **kwargs):
        import shutil

        shutil.rmtree(path)

    monkeypatch.setattr(dlapi, 'remove', mock_remove)

    robust_rm_dir(str(test_dir))

    assert not test_dir.exists()


def test_rm_dir_datalad_fail(tmp_path, monkeypatch):
    """Test robust_rm_dir when datalad.remove fails and falls back to shutil.rmtree."""
    test_dir = tmp_path / 'test_datalad'
    test_dir.mkdir()
    (test_dir / '.datalad').mkdir()
    (test_dir / 'file.txt').write_text('test')

    # Mock datalad.remove to raise an exception
    def mock_remove(path, **kwargs):
        raise Exception('datalad remove failed')

    monkeypatch.setattr(dlapi, 'remove', mock_remove)

    robust_rm_dir(str(test_dir))

    assert not test_dir.exists()


def test_rm_dir_datalad_partial(tmp_path, monkeypatch):
    """Test robust_rm_dir when datalad.remove succeeds but path still exists."""
    test_dir = tmp_path / 'test_datalad'
    test_dir.mkdir()
    (test_dir / '.datalad').mkdir()
    (test_dir / 'file.txt').write_text('test')

    # Mock datalad.remove to succeed but not remove everything
    def mock_remove(path, **kwargs):
        # Remove some files but leave the directory
        (test_dir / 'file.txt').unlink()
        # Don't actually remove the directory

    monkeypatch.setattr(dlapi, 'remove', mock_remove)

    robust_rm_dir(str(test_dir))

    # Should fall back to shutil.rmtree and remove everything
    assert not test_dir.exists()


def test_rm_dir_git(tmp_path):
    """Test robust_rm_dir with a plain git repo (has .git directory but no .datalad)."""
    test_dir = tmp_path / 'test_git'
    test_dir.mkdir()
    (test_dir / '.git').mkdir()
    (test_dir / 'file.txt').write_text('test')

    # Should NOT call datalad.remove for a plain git repo
    with patch.object(dlapi, 'remove') as mock_remove:
        robust_rm_dir(str(test_dir))
        mock_remove.assert_not_called()

    # Should be removed via shutil.rmtree fallback
    assert not test_dir.exists()


def test_rm_dir_permission(tmp_path, monkeypatch):
    """Test robust_rm_dir handling of permission errors."""
    test_dir = tmp_path / 'test_readonly'
    test_dir.mkdir()
    readonly_file = test_dir / 'readonly.txt'
    readonly_file.write_text('test')

    # Make file readonly
    os.chmod(str(readonly_file), stat.S_IREAD)

    # Mock shutil.rmtree to simulate a permission error on first attempt,
    # then succeed on a retry.
    original_rmtree = shutil.rmtree
    call_count = {'count': 0}

    def mock_rmtree(path, onerror=None):
        call_count['count'] += 1
        if call_count['count'] == 1:
            # First call: trigger onerror, then raise so robust_rm_dir retries.
            if onerror:
                err = PermissionError(13, 'Permission denied', str(readonly_file))
                onerror(os.remove, str(readonly_file), (PermissionError, err, None))
            raise OSError('Permission denied')
        else:
            # Subsequent calls: succeed
            original_rmtree(path, onerror=onerror)

    monkeypatch.setattr('shutil.rmtree', mock_rmtree)

    robust_rm_dir(str(test_dir), max_retries=3, retry_delay=0)

    assert not test_dir.exists()
    assert call_count['count'] == 2


def test_rm_dir_retry(tmp_path, monkeypatch):
    """Test robust_rm_dir retry logic when removal fails initially."""
    test_dir = tmp_path / 'test_retry'
    test_dir.mkdir()
    (test_dir / 'file.txt').write_text('test')

    # Mock shutil.rmtree to fail twice then succeed
    original_rmtree = shutil.rmtree
    call_count = {'count': 0}

    def mock_rmtree(path, onerror=None):
        call_count['count'] += 1
        if call_count['count'] < 3:
            raise OSError(f'Failed attempt {call_count["count"]}')
        original_rmtree(path, onerror=onerror)

    monkeypatch.setattr('shutil.rmtree', mock_rmtree)

    robust_rm_dir(str(test_dir), max_retries=3, retry_delay=0)

    assert not test_dir.exists()
    assert call_count['count'] == 3


def test_rm_dir_max_retries(tmp_path, monkeypatch):
    """Test robust_rm_dir when max retries are exceeded."""
    test_dir = tmp_path / 'test_fail'
    test_dir.mkdir()
    (test_dir / 'file.txt').write_text('test')

    # Mock shutil.rmtree to always fail
    def mock_rmtree(path, onerror=None):
        raise OSError('Always fails')

    monkeypatch.setattr('shutil.rmtree', mock_rmtree)

    # Should warn but not crash
    with pytest.warns(UserWarning, match='Failed to remove temporary directory'):
        robust_rm_dir(str(test_dir), max_retries=2, retry_delay=0)

    # Directory should still exist
    assert test_dir.exists()


def test_merge_existing(babs_project_sessionlevel, tmp_path, monkeypatch):
    """Test babs_merge when merge_ds already exists."""
    babs_proj = BABSMerge(babs_project_sessionlevel)

    # Create merge_ds directory
    merge_ds_path = tmp_path / 'merge_ds'
    merge_ds_path.mkdir()
    monkeypatch.setattr(babs_proj, 'project_root', str(tmp_path))

    with pytest.raises(Exception, match="Folder 'merge_ds' already exists"):
        babs_proj.babs_merge()


def test_merge_no_head(babs_project_sessionlevel, tmp_path, monkeypatch):
    """Test babs_merge when there's no HEAD branch."""
    babs_proj = BABSMerge(babs_project_sessionlevel)

    monkeypatch.setattr(babs_proj, 'project_root', str(tmp_path))

    def set_analysis_id():
        babs_proj.analysis_dataset_id = 'test-id'

    monkeypatch.setattr(babs_proj, 'wtf_key_info', set_analysis_id)
    monkeypatch.setattr(babs_proj, '_get_results_branches', lambda: ['job-123'])

    from babs.merge import dlapi

    def mock_clone(source, path):
        # Create the directory so subsequent git commands can run
        os.makedirs(path, exist_ok=True)
        return None

    monkeypatch.setattr(dlapi, 'clone', mock_clone)

    def mock_remote_show(cmd, **kwargs):
        if 'remote' in cmd and 'show' in cmd:
            result = MagicMock()
            result.returncode = 0
            result.stdout = b'No HEAD branch found\n'  # No HEAD branch
            return result
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr('babs.merge.subprocess.run', mock_remote_show)

    with pytest.raises(Exception, match='There is no HEAD branch in output RIA!'):
        babs_proj.babs_merge()
