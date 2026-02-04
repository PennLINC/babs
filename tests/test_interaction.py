"""Tests for interaction behaviors."""

import pandas as pd
import pytest

from babs.interaction import BABSInteraction


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
