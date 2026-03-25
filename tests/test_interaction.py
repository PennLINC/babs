"""Tests for interaction behaviors."""

import pandas as pd
import pytest

from babs.interaction import BABSInteraction
from babs.utils import scheduler_status_columns


def _minimal_status_df():
    return pd.DataFrame(
        {
            'sub_id': ['sub-01', 'sub-02'],
            'submitted': [False, False],
            'has_results': [False, False],
            'is_failed': [False, False],
            'job_id': [-1, -1],
            'task_id': [-1, -1],
            'state': ['', ''],
            'time_used': ['', ''],
            'time_limit': ['', ''],
            'nodes': [0, 0],
            'cpus': [0, 0],
            'partition': ['', ''],
            'name': ['', ''],
        }
    )


def _status_df_for_submit():
    return pd.DataFrame(
        {
            'sub_id': ['sub-01', 'sub-02', 'sub-03'],
            'submitted': [True, True, False],
            'has_results': [False, False, False],
            'is_failed': [False, True, False],
            'job_id': [10, 11, -1],
            'task_id': [1, 1, -1],
            'state': ['R', '', ''],
            'time_used': ['0:01', '', ''],
            'time_limit': ['5-00:00:00', '', ''],
            'nodes': [1, 0, 0],
            'cpus': [1, 0, 0],
            'partition': ['normal', '', ''],
            'name': ['test_array_job', '', ''],
        }
    )


def test_babs_submit_blocks_non_cg_jobs(babs_project_subjectlevel, monkeypatch):
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    running_df = pd.DataFrame(
        {
            'job_id': [1],
            'task_id': [1],
            'state': ['R'],
            'time_used': ['0:01'],
            'time_limit': ['5-00:00:00'],
            'nodes': [1],
            'cpus': [1],
            'partition': ['normal'],
            'name': ['test_array_job'],
        }
    )
    monkeypatch.setattr(babs_proj, 'get_currently_running_jobs_df', lambda: running_df)

    with pytest.raises(Exception, match='There are still jobs running'):
        babs_proj.babs_submit(count=1)


def test_babs_submit_allows_cg_jobs(babs_project_subjectlevel, monkeypatch):
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    running_df = pd.DataFrame(
        {
            'job_id': [1],
            'task_id': [1],
            'state': ['CG'],
            'time_used': ['0:01'],
            'time_limit': ['5-00:00:00'],
            'nodes': [1],
            'cpus': [1],
            'partition': ['normal'],
            'name': ['test_array_job'],
        }
    )
    monkeypatch.setattr(babs_proj, 'get_currently_running_jobs_df', lambda: running_df)
    monkeypatch.setattr(babs_proj, 'get_job_status_df', _minimal_status_df)

    submit_calls = []

    def _mock_submit_array(analysis_path, queue, total_jobs):
        submit_calls.append((analysis_path, queue, total_jobs))
        return 123

    monkeypatch.setattr('babs.interaction.submit_array', _mock_submit_array)

    babs_proj.babs_submit(count=1)

    assert submit_calls


def test_babs_submit_allows_running_skips_jobs(babs_project_subjectlevel, monkeypatch, capsys):
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    running_df = pd.DataFrame(
        {
            'job_id': [10],
            'task_id': [1],
            'state': ['R'],
            'time_used': ['0:01'],
            'time_limit': ['5-00:00:00'],
            'nodes': [1],
            'cpus': [1],
            'partition': ['normal'],
            'name': ['test_array_job'],
            'sub_id': ['sub-01'],
        }
    )
    monkeypatch.setattr(babs_proj, 'get_currently_running_jobs_df', lambda: running_df)
    monkeypatch.setattr(babs_proj, 'get_job_status_df', _status_df_for_submit)

    submit_calls = []

    def _mock_submit_array(analysis_path, queue, total_jobs):
        submit_calls.append((analysis_path, queue, total_jobs))
        return 123

    monkeypatch.setattr('babs.interaction.submit_array', _mock_submit_array)

    babs_proj.babs_submit(skip_running_jobs=True)

    captured = capsys.readouterr()
    assert submit_calls
    assert submit_calls[0][2] == 2
    assert 'Skipping running/pending jobs from job IDs' in captured.out
    assert '10' in captured.out


def test_get_currently_running_jobs_df_multiple_job_ids(babs_project_subjectlevel, monkeypatch):
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    status_df = pd.DataFrame(
        {
            'sub_id': ['sub-01', 'sub-02'],
            'submitted': [True, True],
            'has_results': [False, False],
            'is_failed': [False, False],
            'job_id': [10, 20],
            'task_id': [1, 2],
        }
    )
    monkeypatch.setattr(babs_proj, 'get_job_status_df', lambda: status_df)
    monkeypatch.setattr(babs_proj, 'get_latest_submitted_jobs_df', pd.DataFrame)

    calls = []

    def _mock_request_all_job_status(queue, job_id):
        calls.append(job_id)
        task_id = 1 if job_id == 10 else 2
        return pd.DataFrame(
            {
                'job_id': [job_id],
                'task_id': [task_id],
                'state': ['R'],
                'time_used': ['0:01'],
                'time_limit': ['5-00:00:00'],
                'nodes': [1],
                'cpus': [1],
                'partition': ['normal'],
                'name': ['test_array_job'],
            }
        )[scheduler_status_columns]

    monkeypatch.setattr('babs.base.request_all_job_status', _mock_request_all_job_status)

    running_df = babs_proj.get_currently_running_jobs_df()

    assert set(calls) == {10, 20}
    assert set(running_df['sub_id']) == {'sub-01', 'sub-02'}


# -- babs_status_wait tests --


def _make_status_df(submitted, has_results, is_failed):
    """Build a status DataFrame from parallel lists of booleans."""
    n = len(submitted)
    return pd.DataFrame(
        {
            'sub_id': [f'sub-{i:02d}' for i in range(1, n + 1)],
            'submitted': submitted,
            'has_results': has_results,
            'is_failed': is_failed,
            'job_id': [100 + i if s else -1 for i, s in enumerate(submitted)],
            'task_id': [i + 1 if s else -1 for i, s in enumerate(submitted)],
            'state': [''] * n,
            'time_used': [''] * n,
            'time_limit': [''] * n,
            'nodes': [0] * n,
            'cpus': [0] * n,
            'partition': [''] * n,
            'name': [''] * n,
        }
    )


def _empty_running_df():
    return pd.DataFrame(columns=scheduler_status_columns)


def _patch_wait(monkeypatch, babs_proj, status_dfs):
    """Patch a BABSInteraction for babs_status_wait testing.

    Parameters
    ----------
    status_dfs : list[pd.DataFrame]
        Sequence of DataFrames returned by successive get_job_status_df calls.
    """
    call_count = {'n': 0}

    def _get_status():
        idx = min(call_count['n'], len(status_dfs) - 1)
        call_count['n'] += 1
        return status_dfs[idx]

    monkeypatch.setattr(babs_proj, '_update_results_status', lambda: None)
    monkeypatch.setattr(babs_proj, 'get_currently_running_jobs_df', _empty_running_df)
    monkeypatch.setattr(babs_proj, 'get_job_status_df', _get_status)
    monkeypatch.setattr('babs.interaction.report_job_status', lambda *a, **kw: None)
    monkeypatch.setattr('babs.interaction.time.sleep', lambda s: None)

    return call_count


def test_status_wait_all_succeeded(babs_project_subjectlevel, monkeypatch, capsys):
    """All submitted jobs already have results — should exit immediately."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    df = _make_status_df(
        submitted=[True, True],
        has_results=[True, True],
        is_failed=[False, False],
    )
    call_count = _patch_wait(monkeypatch, babs_proj, [df])

    babs_proj.babs_status_wait(interval=1)

    assert call_count['n'] == 1
    captured = capsys.readouterr()
    assert '2 succeeded' in captured.out
    assert '0 failed' in captured.out


def test_status_wait_all_failed(babs_project_subjectlevel, monkeypatch):
    """All submitted jobs failed — should exit with sys.exit(1)."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    df = _make_status_df(
        submitted=[True, True],
        has_results=[False, False],
        is_failed=[True, True],
    )
    _patch_wait(monkeypatch, babs_proj, [df])

    with pytest.raises(SystemExit, match='1'):
        babs_proj.babs_status_wait(interval=1)


def test_status_wait_mixed_results(babs_project_subjectlevel, monkeypatch, capsys):
    """Some succeeded, some failed — should exit(1)."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    df = _make_status_df(
        submitted=[True, True],
        has_results=[True, False],
        is_failed=[False, True],
    )
    _patch_wait(monkeypatch, babs_proj, [df])

    with pytest.raises(SystemExit, match='1'):
        babs_proj.babs_status_wait(interval=1)


def test_status_wait_loops_until_done(babs_project_subjectlevel, monkeypatch, capsys):
    """Jobs still running on first check, done on second — should loop once."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    df_running = _make_status_df(
        submitted=[True, True],
        has_results=[False, False],
        is_failed=[False, False],
    )
    df_done = _make_status_df(
        submitted=[True, True],
        has_results=[True, True],
        is_failed=[False, False],
    )
    call_count = _patch_wait(monkeypatch, babs_proj, [df_running, df_done])

    babs_proj.babs_status_wait(interval=1)

    assert call_count['n'] == 2
    captured = capsys.readouterr()
    assert '2 succeeded' in captured.out


def test_status_wait_no_submitted_jobs(babs_project_subjectlevel, monkeypatch, capsys):
    """No jobs submitted — should exit(1)."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    df = _make_status_df(
        submitted=[False, False],
        has_results=[False, False],
        is_failed=[False, False],
    )
    _patch_wait(monkeypatch, babs_proj, [df])

    with pytest.raises(SystemExit, match='1'):
        babs_proj.babs_status_wait(interval=1)


def test_status_wait_report_called_each_iteration(babs_project_subjectlevel, monkeypatch):
    """report_job_status should be called on every iteration."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    df_running = _make_status_df(
        submitted=[True],
        has_results=[False],
        is_failed=[False],
    )
    df_done = _make_status_df(
        submitted=[True],
        has_results=[True],
        is_failed=[False],
    )

    report_calls = []

    monkeypatch.setattr(babs_proj, '_update_results_status', lambda: None)
    monkeypatch.setattr(babs_proj, 'get_currently_running_jobs_df', _empty_running_df)

    call_count = {'n': 0}

    def _get_status():
        idx = min(call_count['n'], 1)
        call_count['n'] += 1
        return [df_running, df_done][idx]

    monkeypatch.setattr(babs_proj, 'get_job_status_df', _get_status)
    monkeypatch.setattr(
        'babs.interaction.report_job_status',
        lambda *a, **kw: report_calls.append(a),
    )
    monkeypatch.setattr('babs.interaction.time.sleep', lambda s: None)

    babs_proj.babs_status_wait(interval=1)

    assert len(report_calls) == 2


def test_status_wait_keyboard_interrupt(babs_project_subjectlevel, monkeypatch, capsys):
    """Ctrl-C should print a message and exit(130)."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    df_running = _make_status_df(
        submitted=[True],
        has_results=[False],
        is_failed=[False],
    )

    monkeypatch.setattr(babs_proj, '_update_results_status', lambda: None)
    monkeypatch.setattr(babs_proj, 'get_currently_running_jobs_df', _empty_running_df)
    monkeypatch.setattr(babs_proj, 'get_job_status_df', lambda: df_running)
    monkeypatch.setattr('babs.interaction.report_job_status', lambda *a, **kw: None)
    monkeypatch.setattr(
        'babs.interaction.time.sleep',
        lambda s: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    with pytest.raises(SystemExit) as exc_info:
        babs_proj.babs_status_wait(interval=1)

    assert exc_info.value.code == 130
    captured = capsys.readouterr()
    assert 'Interrupted' in captured.out
