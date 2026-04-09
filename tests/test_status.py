"""Tests for babs.status — data model, CSV I/O, and update logic."""

import os

import pytest

from babs.scheduler import report_job_status
from babs.status import (
    JobStatus,
    SchedulerState,
    create_initial_statuses,
    read_job_status_csv,
    update_from_branches,
    update_from_scheduler,
    write_job_status_csv,
)

# -- SchedulerState -----------------------------------------------------------


class TestSchedulerState:
    def test_from_slurm_state_known_states(self):
        assert SchedulerState.from_slurm_state('PD') == SchedulerState.PENDING
        assert SchedulerState.from_slurm_state('R') == SchedulerState.RUNNING
        assert SchedulerState.from_slurm_state('CG') == SchedulerState.COMPLETING
        assert SchedulerState.from_slurm_state('CF') == SchedulerState.CONFIGURING

    def test_from_slurm_state_unknown_raises(self):
        with pytest.raises(ValueError, match='Unknown SLURM scheduler state'):
            SchedulerState.from_slurm_state('BOGUS')


# -- JobStatus properties -----------------------------------------------------


class TestJobStatusProperties:
    def _make(self, state=SchedulerState.NOT_SUBMITTED, has_results=False, ses_id=None):
        return JobStatus(
            sub_id='sub-01',
            ses_id=ses_id,
            scheduler_state=state,
            has_results=has_results,
            job_id=None,
            task_id=None,
            time_used='',
            time_limit='',
            nodes=0,
            cpus=0,
            partition='',
            name='',
        )

    def test_not_submitted(self):
        job = self._make(SchedulerState.NOT_SUBMITTED)
        assert not job.submitted
        assert not job.is_failed

    def test_running_not_failed(self):
        job = self._make(SchedulerState.RUNNING)
        assert job.submitted
        assert not job.is_failed

    def test_pending_not_failed(self):
        job = self._make(SchedulerState.PENDING)
        assert job.submitted
        assert not job.is_failed

    def test_done_with_results_not_failed(self):
        job = self._make(SchedulerState.DONE, has_results=True)
        assert job.submitted
        assert not job.is_failed

    def test_done_without_results_is_failed(self):
        job = self._make(SchedulerState.DONE, has_results=False)
        assert job.submitted
        assert job.is_failed

    def test_key_subject_only(self):
        job = self._make()
        assert job.key == ('sub-01',)

    def test_key_with_session(self):
        job = self._make(ses_id='ses-A')
        assert job.key == ('sub-01', 'ses-A')


# -- CSV round-trip ------------------------------------------------------------


class TestCSVRoundTrip:
    def _sample_statuses(self):
        return {
            ('sub-01',): JobStatus(
                sub_id='sub-01',
                ses_id=None,
                scheduler_state=SchedulerState.DONE,
                has_results=True,
                job_id=123,
                task_id=1,
                time_used='1:30:00',
                time_limit='5-00:00:00',
                nodes=1,
                cpus=4,
                partition='normal',
                name='my_job',
            ),
            ('sub-02',): JobStatus(
                sub_id='sub-02',
                ses_id=None,
                scheduler_state=SchedulerState.NOT_SUBMITTED,
                has_results=False,
                job_id=None,
                task_id=None,
                time_used='',
                time_limit='',
                nodes=0,
                cpus=0,
                partition='',
                name='',
            ),
        }

    def test_round_trip_subject_level(self, tmp_path):
        original = self._sample_statuses()
        path = str(tmp_path / 'job_status.csv')
        write_job_status_csv(path, original)
        loaded = read_job_status_csv(path)

        assert set(loaded.keys()) == set(original.keys())
        for key in original:
            assert loaded[key].sub_id == original[key].sub_id
            assert loaded[key].scheduler_state == original[key].scheduler_state
            assert loaded[key].has_results == original[key].has_results
            assert loaded[key].job_id == original[key].job_id
            assert loaded[key].is_failed == original[key].is_failed
            assert loaded[key].submitted == original[key].submitted

    def test_round_trip_session_level(self, tmp_path):
        original = {
            ('sub-01', 'ses-A'): JobStatus(
                sub_id='sub-01',
                ses_id='ses-A',
                scheduler_state=SchedulerState.RUNNING,
                has_results=False,
                job_id=456,
                task_id=2,
                time_used='0:10',
                time_limit='2:00:00',
                nodes=1,
                cpus=2,
                partition='gpu',
                name='gpu_job',
            ),
        }
        path = str(tmp_path / 'job_status.csv')
        write_job_status_csv(path, original)
        loaded = read_job_status_csv(path)

        job = loaded[('sub-01', 'ses-A')]
        assert job.ses_id == 'ses-A'
        assert job.scheduler_state == SchedulerState.RUNNING
        assert job.submitted

    def test_derived_columns_written_but_ignored_on_read(self, tmp_path):
        """is_failed and submitted are written to CSV but recomputed on read."""
        path = str(tmp_path / 'job_status.csv')
        statuses = {
            ('sub-01',): JobStatus(
                sub_id='sub-01',
                ses_id=None,
                scheduler_state=SchedulerState.DONE,
                has_results=False,
                job_id=1,
                task_id=1,
                time_used='',
                time_limit='',
                nodes=0,
                cpus=0,
                partition='',
                name='',
            ),
        }
        write_job_status_csv(path, statuses)

        # Verify is_failed=True is written
        with open(path) as f:
            content = f.read()
        assert 'True' in content  # is_failed column

        # On read, is_failed is derived, not read from CSV
        loaded = read_job_status_csv(path)
        assert loaded[('sub-01',)].is_failed is True

    def test_empty_statuses_no_file(self, tmp_path):
        path = str(tmp_path / 'job_status.csv')
        write_job_status_csv(path, {})
        assert not os.path.exists(path)


# -- update_from_branches ------------------------------------------------------


class TestUpdateFromBranches:
    def _initial_statuses(self):
        return {
            ('sub-01',): JobStatus(
                sub_id='sub-01',
                ses_id=None,
                scheduler_state=SchedulerState.DONE,
                has_results=False,
                job_id=None,
                task_id=None,
                time_used='',
                time_limit='',
                nodes=0,
                cpus=0,
                partition='',
                name='',
            ),
            ('sub-02',): JobStatus(
                sub_id='sub-02',
                ses_id=None,
                scheduler_state=SchedulerState.NOT_SUBMITTED,
                has_results=False,
                job_id=None,
                task_id=None,
                time_used='',
                time_limit='',
                nodes=0,
                cpus=0,
                partition='',
                name='',
            ),
        }

    def test_branch_sets_has_results(self):
        statuses = self._initial_statuses()
        updated = update_from_branches(statuses, ['job-100-1-sub-01'])

        assert updated[('sub-01',)].has_results is True
        assert updated[('sub-01',)].job_id == 100
        assert updated[('sub-01',)].task_id == 1

    def test_no_match_leaves_unchanged(self):
        statuses = self._initial_statuses()
        updated = update_from_branches(statuses, ['job-100-1-sub-99'])

        assert updated[('sub-01',)].has_results is False
        assert updated[('sub-02',)].has_results is False

    def test_non_matching_branch_names_ignored(self):
        statuses = self._initial_statuses()
        updated = update_from_branches(statuses, ['main', 'not-a-job'])

        assert updated == statuses

    def test_session_level_branches(self):
        statuses = {
            ('sub-01', 'ses-A'): JobStatus(
                sub_id='sub-01',
                ses_id='ses-A',
                scheduler_state=SchedulerState.DONE,
                has_results=False,
                job_id=None,
                task_id=None,
                time_used='',
                time_limit='',
                nodes=0,
                cpus=0,
                partition='',
                name='',
            ),
        }
        updated = update_from_branches(statuses, ['job-200-1-sub-01-ses-A'])

        assert updated[('sub-01', 'ses-A')].has_results is True
        assert updated[('sub-01', 'ses-A')].job_id == 200

    def test_already_has_results_preserved(self):
        """A job that already has_results=True keeps it even with no matching branch."""
        statuses = {
            ('sub-01',): JobStatus(
                sub_id='sub-01',
                ses_id=None,
                scheduler_state=SchedulerState.DONE,
                has_results=True,
                job_id=50,
                task_id=1,
                time_used='1:00',
                time_limit='5-00:00:00',
                nodes=1,
                cpus=1,
                partition='normal',
                name='old_job',
            ),
        }
        updated = update_from_branches(statuses, [])

        assert updated[('sub-01',)].has_results is True
        assert updated[('sub-01',)].job_id == 50

    def test_empty_statuses_with_branches(self):
        """Branches for unknown subjects are ignored."""
        updated = update_from_branches({}, ['job-100-1-sub-99'])
        assert len(updated) == 0


# -- update_from_scheduler -----------------------------------------------------


class TestUpdateFromScheduler:
    def _submitted_statuses(self):
        return {
            ('sub-01',): JobStatus(
                sub_id='sub-01',
                ses_id=None,
                scheduler_state=SchedulerState.RUNNING,
                has_results=False,
                job_id=100,
                task_id=1,
                time_used='0:05',
                time_limit='5-00:00:00',
                nodes=1,
                cpus=1,
                partition='normal',
                name='my_job',
            ),
            ('sub-02',): JobStatus(
                sub_id='sub-02',
                ses_id=None,
                scheduler_state=SchedulerState.PENDING,
                has_results=False,
                job_id=100,
                task_id=2,
                time_used='0:00',
                time_limit='5-00:00:00',
                nodes=1,
                cpus=1,
                partition='normal',
                name='my_job',
            ),
        }

    def test_still_running(self):
        statuses = self._submitted_statuses()
        raw = '100_1|R|0:10|5-00:00:00|1|1|normal|my_job\n'
        updated = update_from_scheduler(statuses, raw)

        assert updated[('sub-01',)].scheduler_state == SchedulerState.RUNNING
        assert updated[('sub-01',)].time_used == '0:10'

    def test_job_left_scheduler_no_results_is_failed(self):
        """The core bug scenario: squeue is empty, job had no results -> DONE -> is_failed."""
        statuses = self._submitted_statuses()
        raw = ''  # nothing in queue
        updated = update_from_scheduler(statuses, raw)

        assert updated[('sub-01',)].scheduler_state == SchedulerState.DONE
        assert updated[('sub-01',)].is_failed is True

    def test_job_left_scheduler_with_results_not_failed(self):
        """Job finished and has results — not failed."""
        statuses = self._submitted_statuses()
        # Give sub-01 results first
        statuses[('sub-01',)] = JobStatus(
            sub_id='sub-01',
            ses_id=None,
            scheduler_state=SchedulerState.RUNNING,
            has_results=True,
            job_id=100,
            task_id=1,
            time_used='0:05',
            time_limit='5-00:00:00',
            nodes=1,
            cpus=1,
            partition='normal',
            name='my_job',
        )
        raw = ''  # nothing in queue
        updated = update_from_scheduler(statuses, raw)

        assert updated[('sub-01',)].scheduler_state == SchedulerState.DONE
        assert updated[('sub-01',)].is_failed is False

    def test_not_submitted_stays_not_submitted(self):
        statuses = {
            ('sub-01',): JobStatus(
                sub_id='sub-01',
                ses_id=None,
                scheduler_state=SchedulerState.NOT_SUBMITTED,
                has_results=False,
                job_id=None,
                task_id=None,
                time_used='',
                time_limit='',
                nodes=0,
                cpus=0,
                partition='',
                name='',
            ),
        }
        raw = ''
        updated = update_from_scheduler(statuses, raw)

        assert updated[('sub-01',)].scheduler_state == SchedulerState.NOT_SUBMITTED
        assert not updated[('sub-01',)].is_failed

    def test_partial_squeue_some_done_some_running(self):
        statuses = self._submitted_statuses()
        # Only sub-02 still in queue
        raw = '100_2|PD|0:00|5-00:00:00|1|1|normal|my_job\n'
        updated = update_from_scheduler(statuses, raw)

        assert updated[('sub-01',)].scheduler_state == SchedulerState.DONE
        assert updated[('sub-01',)].is_failed is True
        assert updated[('sub-02',)].scheduler_state == SchedulerState.PENDING

    def test_non_array_job_id_raises(self):
        """squeue output without array format (no underscore) should raise."""
        statuses = self._submitted_statuses()
        raw = '100|R|0:10|5-00:00:00|1|1|normal|my_job\n'
        with pytest.raises(ValueError, match='Expected array job format'):
            update_from_scheduler(statuses, raw)


# -- create_initial_statuses ---------------------------------------------------


class TestCreateInitialStatuses:
    def test_subject_level(self):
        entries = [{'sub_id': 'sub-01'}, {'sub_id': 'sub-02'}]
        statuses = create_initial_statuses(entries)

        assert len(statuses) == 2
        assert statuses[('sub-01',)].scheduler_state == SchedulerState.NOT_SUBMITTED
        assert not statuses[('sub-01',)].submitted
        assert not statuses[('sub-01',)].has_results
        assert not statuses[('sub-01',)].is_failed

    def test_session_level(self):
        entries = [
            {'sub_id': 'sub-01', 'ses_id': 'ses-A'},
            {'sub_id': 'sub-01', 'ses_id': 'ses-B'},
        ]
        statuses = create_initial_statuses(entries)

        assert len(statuses) == 2
        assert ('sub-01', 'ses-A') in statuses
        assert ('sub-01', 'ses-B') in statuses


# -- report_job_status ---------------------------------------------------------


class TestReportJobStatus:
    def _make(self, state=SchedulerState.NOT_SUBMITTED, has_results=False):
        return JobStatus(
            sub_id='sub-01',
            ses_id=None,
            scheduler_state=state,
            has_results=has_results,
            job_id=None,
            task_id=None,
            time_used='',
            time_limit='',
            nodes=0,
            cpus=0,
            partition='',
            name='',
        )

    def test_all_not_submitted(self, capsys):
        statuses = {
            ('sub-01',): self._make(),
            ('sub-02',): self._make(),
        }
        report_job_status(statuses, '/fake/analysis')
        out = capsys.readouterr().out
        assert '2 jobs' in out
        assert '0 job(s) have been submitted' in out

    def test_mixed_states(self, capsys):
        statuses = {
            ('sub-01',): self._make(SchedulerState.DONE, has_results=True),
            ('sub-02',): self._make(SchedulerState.RUNNING),
            ('sub-03',): self._make(SchedulerState.PENDING),
            ('sub-04',): self._make(SchedulerState.DONE, has_results=False),
            ('sub-05',): self._make(),
        }
        report_job_status(statuses, '/fake/analysis')
        out = capsys.readouterr().out
        assert '5 jobs' in out
        assert '4 job(s) have been submitted' in out
        assert '1 job(s) successfully finished' in out
        assert '1 job(s) are pending' in out
        assert '1 job(s) are running' in out
        assert '1 job(s) failed' in out

    def test_all_done(self, capsys):
        statuses = {
            ('sub-01',): self._make(SchedulerState.DONE, has_results=True),
            ('sub-02',): self._make(SchedulerState.DONE, has_results=True),
        }
        report_job_status(statuses, '/fake/analysis')
        out = capsys.readouterr().out
        assert 'All jobs are completed' in out
