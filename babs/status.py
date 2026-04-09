"""Job status data model and CSV I/O for babs status."""

import csv
import re
from dataclasses import dataclass, replace
from enum import Enum


class SchedulerState(Enum):
    """States a job can be in relative to the scheduler.

    PENDING through CONFIGURING use SLURM squeue state codes as values
    for backward compatibility with the existing job_status.csv format.

    TODO: decouple SLURM state codes from the BABS data model so the
    CSV stores scheduler-agnostic values instead of SLURM strings.
    """

    NOT_SUBMITTED = 'NOT_SUBMITTED'
    PENDING = 'PD'  # SLURM squeue state
    RUNNING = 'R'  # SLURM squeue state
    COMPLETING = 'CG'  # SLURM squeue state
    CONFIGURING = 'CF'  # SLURM squeue state
    DONE = 'DONE'
    # future: COMPLETED, FAILED, CANCELLED, TIMEOUT (from sacct)

    @classmethod
    def from_slurm_state(cls, state_str: str) -> 'SchedulerState':
        """Convert a SLURM squeue state string to a SchedulerState."""
        for member in cls:
            if member.value == state_str:
                return member
        raise ValueError(f'Unknown SLURM scheduler state: {state_str!r}')


@dataclass
class JobStatus:
    """Status of a single job (one subject, optionally one session)."""

    sub_id: str
    ses_id: str | None
    scheduler_state: SchedulerState
    has_results: bool
    job_id: int | None
    task_id: int | None
    time_used: str
    time_limit: str
    nodes: int
    cpus: int
    partition: str
    name: str

    @property
    def is_failed(self) -> bool:
        return self.scheduler_state == SchedulerState.DONE and not self.has_results

    @property
    def submitted(self) -> bool:
        return self.scheduler_state != SchedulerState.NOT_SUBMITTED

    @property
    def key(self) -> tuple:
        if self.ses_id is not None:
            return (self.sub_id, self.ses_id)
        return (self.sub_id,)


# -- CSV I/O -----------------------------------------------------------------

_CSV_COLUMNS_SUBJECT = [
    'sub_id',
    'submitted',
    'is_failed',
    'state',
    'time_used',
    'time_limit',
    'nodes',
    'cpus',
    'partition',
    'name',
    'job_id',
    'task_id',
    'has_results',
]

_CSV_COLUMNS_SESSION = [
    'sub_id',
    'ses_id',
    'submitted',
    'is_failed',
    'state',
    'time_used',
    'time_limit',
    'nodes',
    'cpus',
    'partition',
    'name',
    'job_id',
    'task_id',
    'has_results',
]

_STATE_TO_CSV = {
    SchedulerState.NOT_SUBMITTED: '',
    SchedulerState.PENDING: 'PD',
    SchedulerState.RUNNING: 'R',
    SchedulerState.COMPLETING: 'CG',
    SchedulerState.CONFIGURING: 'CF',
    SchedulerState.DONE: '',
}

_SLURM_SQUEUE_STATES = {'PD', 'R', 'CG', 'CF'}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() == 'true'


def _parse_optional_int(value: str) -> int | None:
    value = value.strip()
    if value in ('', 'NA', 'nan'):
        return None
    return int(float(value))


def _job_status_from_row(row: dict) -> JobStatus:
    """Construct a JobStatus from a CSV row dict.

    ``is_failed`` and ``submitted`` columns are ignored on read —
    they are derived properties on JobStatus.
    """
    ses_id = row.get('ses_id', '').strip() or None
    state_str = row.get('state', '').strip()
    submitted = _parse_bool(row.get('submitted', 'False'))
    if state_str in _SLURM_SQUEUE_STATES:
        scheduler_state = SchedulerState.from_slurm_state(state_str)
    elif submitted:
        scheduler_state = SchedulerState.DONE
    else:
        scheduler_state = SchedulerState.NOT_SUBMITTED

    return JobStatus(
        sub_id=row['sub_id'].strip(),
        ses_id=ses_id,
        scheduler_state=scheduler_state,
        has_results=_parse_bool(row.get('has_results', 'False')),
        job_id=_parse_optional_int(row.get('job_id', '')),
        task_id=_parse_optional_int(row.get('task_id', '')),
        time_used=row.get('time_used', '').strip(),
        time_limit=row.get('time_limit', '').strip(),
        nodes=int(float(row.get('nodes', '0').strip() or '0')),
        cpus=int(float(row.get('cpus', '0').strip() or '0')),
        partition=row.get('partition', '').strip(),
        name=row.get('name', '').strip(),
    )


def read_job_status_csv(path: str) -> dict[tuple, JobStatus]:
    """Read job_status.csv and return a dict keyed by (sub_id,) or (sub_id, ses_id)."""
    statuses: dict[tuple, JobStatus] = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            job = _job_status_from_row(row)
            statuses[job.key] = job
    return statuses


def _job_status_to_row(job: JobStatus, session_level: bool) -> dict:
    """Convert a JobStatus to a CSV row dict."""
    row = {
        'sub_id': job.sub_id,
        'submitted': str(job.submitted),
        'is_failed': str(job.is_failed),
        'state': _STATE_TO_CSV[job.scheduler_state],
        'time_used': job.time_used,
        'time_limit': job.time_limit,
        'nodes': str(job.nodes),
        'cpus': str(job.cpus),
        'partition': job.partition,
        'name': job.name,
        'job_id': str(job.job_id) if job.job_id is not None else '',
        'task_id': str(job.task_id) if job.task_id is not None else '',
        'has_results': str(job.has_results),
    }
    if session_level:
        row['ses_id'] = job.ses_id or ''
    return row


def write_job_status_csv(path: str, statuses: dict[tuple, JobStatus]) -> None:
    """Write job statuses to job_status.csv."""
    if not statuses:
        return

    session_level = any(job.ses_id is not None for job in statuses.values())
    columns = _CSV_COLUMNS_SESSION if session_level else _CSV_COLUMNS_SUBJECT

    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for job in statuses.values():
            writer.writerow(_job_status_to_row(job, session_level))


# -- Update functions ---------------------------------------------------------

# Branch name pattern: job-<job_id>-<task_id>-<sub_id>[-<ses_id>]
_BRANCH_PATTERN = re.compile(
    r'job-(?P<job_id>\d+)-?(?P<task_id>\d+)?[-]'
    r'(?P<sub_id>sub-[^-]+)(?:-(?P<ses_id>ses-[^-]+))?'
)


def update_from_branches(
    statuses: dict[tuple, JobStatus],
    branches: list[str],
) -> dict[tuple, JobStatus]:
    """Update statuses with results information from branch names.

    Branches that don't match any existing status key are ignored
    (they may belong to subjects not in the inclusion list).
    """
    # Parse branches into a lookup of key -> (job_id, task_id)
    branch_results: dict[tuple, tuple[int | None, int | None]] = {}
    for branch in branches:
        match = _BRANCH_PATTERN.match(branch)
        if not match:
            continue
        sub_id = match.group('sub_id')
        ses_id = match.group('ses_id')
        job_id = int(match.group('job_id')) if match.group('job_id') else None
        task_id = int(match.group('task_id')) if match.group('task_id') else None
        key = (sub_id, ses_id) if ses_id else (sub_id,)
        branch_results[key] = (job_id, task_id)

    updated = {}
    for key, job in statuses.items():
        if key in branch_results:
            branch_job_id, branch_task_id = branch_results[key]
            updated[key] = replace(
                job,
                has_results=True,
                job_id=branch_job_id if branch_job_id is not None else job.job_id,
                task_id=branch_task_id if branch_task_id is not None else job.task_id,
            )
        else:
            updated[key] = job
    return updated


def update_from_scheduler(
    statuses: dict[tuple, JobStatus],
    raw_squeue: str,
) -> dict[tuple, JobStatus]:
    """Update statuses with live scheduler information from raw squeue output.

    Parses squeue output (pipe-delimited: job_id|state|time|limit|nodes|cpus|partition|name),
    joins with existing statuses via (job_id, task_id), and updates scheduler fields.

    Jobs that were previously RUNNING/PENDING but are no longer in squeue
    transition to DONE.
    """
    # Parse squeue output into a lookup of (job_id, task_id) -> fields
    squeue_by_id: dict[tuple[int, int], dict] = {}
    for line in raw_squeue.strip().splitlines():
        if not line.strip():
            continue
        parts = line.strip().split('|')
        if len(parts) != 8:
            continue
        raw_job_id = parts[0]  # format: array_id_task_id
        id_parts = raw_job_id.split('_')
        if len(id_parts) != 2:
            raise ValueError(f'Expected array job format "jobid_taskid", got {raw_job_id!r}')
        job_id = int(id_parts[0])
        task_id = int(id_parts[1])
        squeue_by_id[(job_id, task_id)] = {
            'state': parts[1],
            'time_used': parts[2],
            'time_limit': parts[3],
            'nodes': int(parts[4]),
            'cpus': int(parts[5]),
            'partition': parts[6],
            'name': parts[7],
        }

    # Build reverse lookup: key -> (job_id, task_id) for matching
    key_to_ids: dict[tuple, tuple[int, int]] = {}
    for key, job in statuses.items():
        if job.job_id is not None and job.task_id is not None:
            key_to_ids[key] = (job.job_id, job.task_id)

    updated = {}
    for key, job in statuses.items():
        ids = key_to_ids.get(key)
        squeue_info = squeue_by_id.get(ids) if ids else None

        if squeue_info is not None:
            # Job is in the scheduler
            updated[key] = replace(
                job,
                scheduler_state=SchedulerState.from_slurm_state(squeue_info['state']),
                time_used=squeue_info['time_used'],
                time_limit=squeue_info['time_limit'],
                nodes=squeue_info['nodes'],
                cpus=squeue_info['cpus'],
                partition=squeue_info['partition'],
                name=squeue_info['name'],
            )
        elif job.submitted:
            # Was submitted, not in scheduler anymore -> DONE
            updated[key] = replace(job, scheduler_state=SchedulerState.DONE)
        else:
            updated[key] = job
    return updated


# -- Initialization -----------------------------------------------------------


def create_initial_statuses(
    sub_ses_list: list[dict],
) -> dict[tuple, JobStatus]:
    """Create initial JobStatus entries from a list of subject/session dicts.

    Parameters
    ----------
    sub_ses_list : list of dict
        Each dict has 'sub_id' and optionally 'ses_id'.
    """
    statuses: dict[tuple, JobStatus] = {}
    for entry in sub_ses_list:
        sub_id = entry['sub_id']
        ses_id = entry.get('ses_id')
        job = JobStatus(
            sub_id=sub_id,
            ses_id=ses_id,
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
        )
        statuses[job.key] = job
    return statuses
