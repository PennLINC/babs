"""Tests for interaction behaviors."""

import pandas as pd
import pytest

from babs.interaction import BABSInteraction
from babs.status import JobStatus, SchedulerState
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


def test_babs_status_configures_shared_group_runtime(babs_project_subjectlevel, monkeypatch):
    """`babs status` should run shared-group runtime safeguards first."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    called = []
    # Replace the runtime guard with a tracer so we can assert it was invoked.
    monkeypatch.setattr(
        babs_proj,
        'ensure_shared_group_runtime_ready',
        lambda: called.append(True),
    )
    # Stub downstream work; this test verifies guard invocation only.
    monkeypatch.setattr(babs_proj, '_update_results_status', lambda: {})
    monkeypatch.setattr('babs.interaction.report_job_status', lambda *_args, **_kwargs: None)

    babs_proj.babs_status()

    assert called == [True]


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


def test_get_latest_submitted_jobs_df_missing_job_id_column(babs_project_subjectlevel):
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    # Simulate interrupted submit that wrote pre-submit schema only.
    pd.DataFrame({'sub_id': ['sub-01'], 'task_id': [1]}).to_csv(
        babs_proj.job_submit_path_abs, index=False
    )

    latest_df = babs_proj.get_latest_submitted_jobs_df()

    assert latest_df.columns.tolist() == ['sub_id', 'job_id', 'task_id']
    assert latest_df['sub_id'].tolist() == ['sub-01']
    assert latest_df['task_id'].tolist() == [1]
    assert latest_df['job_id'].isna().all()


# -- babs_status_wait tests --


def _make_statuses(submitted, has_results):
    """Build a statuses dict from parallel lists of booleans."""
    statuses = {}
    for i, (sub, res) in enumerate(zip(submitted, has_results, strict=True)):
        sub_id = f'sub-{i + 1:02d}'
        if sub and not res:
            state = SchedulerState.DONE
        elif sub:
            state = SchedulerState.DONE
        else:
            state = SchedulerState.NOT_SUBMITTED
        job = JobStatus(
            sub_id=sub_id,
            ses_id=None,
            scheduler_state=state,
            has_results=res,
            job_id=100 + i if sub else None,
            task_id=i + 1 if sub else None,
            time_used='',
            time_limit='',
            nodes=0,
            cpus=0,
            partition='',
            name='',
        )
        statuses[job.key] = job
    return statuses


def _patch_wait(monkeypatch, babs_proj, statuses_list):
    """Patch a BABSInteraction for babs_status_wait testing.

    Parameters
    ----------
    statuses_list : list[dict]
        Sequence of statuses dicts returned by successive _update_results_status calls.
    """
    call_count = {'n': 0}

    def _update():
        idx = min(call_count['n'], len(statuses_list) - 1)
        call_count['n'] += 1
        return statuses_list[idx]

    monkeypatch.setattr(babs_proj, '_update_results_status', _update)
    monkeypatch.setattr('babs.interaction.report_job_status', lambda *a, **kw: None)
    monkeypatch.setattr('babs.interaction.time.sleep', lambda s: None)

    return call_count


def test_status_wait_all_succeeded(babs_project_subjectlevel, monkeypatch, capsys):
    """All submitted jobs already have results — should exit immediately."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    statuses = _make_statuses(submitted=[True, True], has_results=[True, True])
    call_count = _patch_wait(monkeypatch, babs_proj, [statuses])

    babs_proj.babs_status_wait(interval=1)

    assert call_count['n'] == 1
    captured = capsys.readouterr()
    assert '2 succeeded' in captured.out
    assert '0 failed' in captured.out


def test_status_wait_all_failed(babs_project_subjectlevel, monkeypatch):
    """All submitted jobs failed — should exit with sys.exit(1)."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    statuses = _make_statuses(submitted=[True, True], has_results=[False, False])
    _patch_wait(monkeypatch, babs_proj, [statuses])

    with pytest.raises(SystemExit, match='1'):
        babs_proj.babs_status_wait(interval=1)


def test_status_wait_mixed_results(babs_project_subjectlevel, monkeypatch, capsys):
    """Some succeeded, some failed — should exit(1)."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    statuses = _make_statuses(submitted=[True, True], has_results=[True, False])
    _patch_wait(monkeypatch, babs_proj, [statuses])

    with pytest.raises(SystemExit, match='1'):
        babs_proj.babs_status_wait(interval=1)


def test_status_wait_loops_until_done(babs_project_subjectlevel, monkeypatch, capsys):
    """Jobs still running on first check, done on second — should loop once."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)

    # First poll: running
    running = {}
    for i in range(2):
        sub_id = f'sub-{i + 1:02d}'
        job = JobStatus(
            sub_id=sub_id,
            ses_id=None,
            scheduler_state=SchedulerState.RUNNING,
            has_results=False,
            job_id=100 + i,
            task_id=i + 1,
            time_used='',
            time_limit='',
            nodes=0,
            cpus=0,
            partition='',
            name='',
        )
        running[job.key] = job

    # Second poll: done
    done = _make_statuses(submitted=[True, True], has_results=[True, True])

    call_count = _patch_wait(monkeypatch, babs_proj, [running, done])

    babs_proj.babs_status_wait(interval=1)

    assert call_count['n'] == 2
    captured = capsys.readouterr()
    assert '2 succeeded' in captured.out


def test_status_wait_no_submitted_jobs(babs_project_subjectlevel, monkeypatch, capsys):
    """No jobs submitted — should return cleanly (exit 0)."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)
    statuses = _make_statuses(submitted=[False, False], has_results=[False, False])
    _patch_wait(monkeypatch, babs_proj, [statuses])

    babs_proj.babs_status_wait(interval=1)
    captured = capsys.readouterr()
    assert 'No jobs have been submitted' in captured.out


def test_status_wait_report_called_each_iteration(babs_project_subjectlevel, monkeypatch):
    """report_job_status should be called on every iteration."""
    babs_proj = BABSInteraction(project_root=babs_project_subjectlevel)

    running = {}
    sub_id = 'sub-01'
    job = JobStatus(
        sub_id=sub_id,
        ses_id=None,
        scheduler_state=SchedulerState.RUNNING,
        has_results=False,
        job_id=100,
        task_id=1,
        time_used='',
        time_limit='',
        nodes=0,
        cpus=0,
        partition='',
        name='',
    )
    running[job.key] = job

    done = _make_statuses(submitted=[True], has_results=[True])

    report_calls = []

    call_count = {'n': 0}

    def _update():
        idx = min(call_count['n'], 1)
        call_count['n'] += 1
        return [running, done][idx]

    monkeypatch.setattr(babs_proj, '_update_results_status', _update)
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

    running = {}
    job = JobStatus(
        sub_id='sub-01',
        ses_id=None,
        scheduler_state=SchedulerState.RUNNING,
        has_results=False,
        job_id=100,
        task_id=1,
        time_used='',
        time_limit='',
        nodes=0,
        cpus=0,
        partition='',
        name='',
    )
    running[job.key] = job

    monkeypatch.setattr(babs_proj, '_update_results_status', lambda: running)
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
