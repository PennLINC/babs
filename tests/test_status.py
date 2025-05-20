import random
from dataclasses import asdict

import pandas as pd

from babs.status import JobStatus, ResultStatus, StatusCollection, _load_jobs, _load_results


def make_inclusion_df(n_subjects: int, n_sessions: int, output_csv: str) -> None:
    if n_sessions == 0:
        df = pd.DataFrame(
            {
                'sub_id': [f'sub-{i:02d}' for i in range(n_subjects)],
            }
        )
    else:
        sub_ids = []
        ses_ids = []
        for subid in range(n_subjects):
            for sesid in range(n_sessions):
                sub_ids.append(f'sub-{subid:02d}')
                ses_ids.append(f'ses-{sesid:02d}')
        df = pd.DataFrame(
            {
                'sub_id': sub_ids,
                'ses_id': ses_ids,
            }
        )
    df.to_csv(output_csv, index=False)


def test_status_sessionlevel_collection():
    n_subjects = 10
    n_sessions = 2
    output_csv = 'inclusion.csv'
    make_inclusion_df(n_subjects, n_sessions, output_csv)
    status_collection = StatusCollection(output_csv)
    assert len(status_collection.jobs) == n_subjects * n_sessions
    assert len(status_collection.results) == n_subjects * n_sessions


def test_status_subjectlevel_collection():
    n_subjects = 10
    n_sessions = 0
    output_csv = 'inclusion.csv'
    make_inclusion_df(n_subjects, n_sessions, output_csv)
    status_collection = StatusCollection(output_csv)
    assert len(status_collection.jobs) == n_subjects
    assert len(status_collection.results) == n_subjects


def check_equal(
    status_collection_1: StatusCollection,
    status_collection_2: StatusCollection,
    jobs_or_results: str,
):
    status_ids_1 = {status_id.key for status_id in status_collection_1.status_ids}
    status_ids_2 = {status_id.key for status_id in status_collection_2.status_ids}
    assert status_ids_1 == status_ids_2

    for status_id in status_ids_1:
        if jobs_or_results == 'results':
            item1 = status_collection_1.results[status_id]
            item2 = status_collection_2.results[status_id]
        else:
            item1 = status_collection_1.jobs[status_id]
            item2 = status_collection_2.jobs[status_id]

        assert asdict(item1) == asdict(item2)


def test_update_status_collection_with_jobs(tmp_path_factory):
    n_subjects = 10
    n_sessions = 2
    output_csv = 'inclusion.csv'
    make_inclusion_df(n_subjects, n_sessions, output_csv)
    status_collection = StatusCollection(output_csv)

    # choose 4 random status_ids to add results to
    changed_status_ids = random.sample(status_collection.status_ids, 4)
    updated_keys = {status_id.key for status_id in changed_status_ids}
    update_jobs = []
    for jobnum, status_id in enumerate(changed_status_ids):
        update_jobs.append(
            JobStatus(
                sub_id=status_id.sub_id,
                ses_id=status_id.ses_id,
                job_id=1,
                task_id=jobnum + 1,
                state='running',
                time_used='1:00:00',
                time_limit='2:00:00',
                nodes=1,
                cpus=1,
                partition='standard',
                name='test',
            )
        )
    status_collection.update_jobs(update_jobs)
    for jobnum, status_id in enumerate(changed_status_ids):
        assert status_collection.jobs[status_id.key].job_id == 1
        assert status_collection.jobs[status_id.key].task_id == jobnum + 1
        assert status_collection.jobs[status_id.key].state == 'running'
        assert status_collection.jobs[status_id.key].time_used == '1:00:00'
        assert status_collection.jobs[status_id.key].time_limit == '2:00:00'
        assert status_collection.jobs[status_id.key].nodes == 1
        assert status_collection.jobs[status_id.key].cpus == 1
        assert status_collection.jobs[status_id.key].partition == 'standard'
        assert status_collection.jobs[status_id.key].name == 'test'

    jobs_dir = tmp_path_factory.mktemp('jobs')
    status_collection.write_results(str(jobs_dir))

    new_status_collection = StatusCollection(
        pd.read_csv(output_csv), jobs=str(jobs_dir / 'jobs.csv')
    )
    check_equal(status_collection, new_status_collection, 'jobs')

    loaded_jobs = _load_jobs(str(jobs_dir / 'jobs.csv'))
    assert len(loaded_jobs) == len(status_collection.jobs)

    pd_loaded_jobs = _load_jobs(pd.read_csv(str(jobs_dir / 'jobs.csv')))
    assert len(pd_loaded_jobs) == len(status_collection.jobs)


def test_update_status_collection_with_results(tmp_path_factory):
    n_subjects = 10
    n_sessions = 2
    output_csv = 'inclusion.csv'
    make_inclusion_df(n_subjects, n_sessions, output_csv)
    status_collection = StatusCollection(output_csv)

    # choose 4 random status_ids to add results to
    changed_status_ids = random.sample(status_collection.status_ids, 4)
    updated_keys = {status_id.key for status_id in changed_status_ids}
    update_results = []
    for status_id in changed_status_ids:
        update_results.append(
            ResultStatus(
                sub_id=status_id.sub_id,
                ses_id=status_id.ses_id,
                result_location='branch',
                is_failed=False,
                has_results=True,
                submitted=True,
            )
        )
    status_collection.update_results(update_results)
    for status_id in changed_status_ids:
        assert status_collection.results[status_id.key].result_location == 'branch'
        assert not status_collection.results[status_id.key].is_failed
        assert status_collection.results[status_id.key].has_results

    # Find some status_ids that should not have results
    unchanged_status_ids = [
        status_id
        for status_id in status_collection.status_ids
        if status_id.key not in updated_keys
    ]
    for status_id in unchanged_status_ids:
        assert not status_collection.results[status_id.key].has_results

    results_dir = tmp_path_factory.mktemp('results')
    status_collection.write_results(str(results_dir))

    new_status_collection = StatusCollection(
        pd.read_csv(output_csv), results=str(results_dir / 'results.csv')
    )
    check_equal(status_collection, new_status_collection, 'results')

    loaded_results = _load_results(str(results_dir / 'results.csv'))
    assert len(loaded_results) == len(status_collection.results)

    pd_loaded_results = _load_results(pd.read_csv(str(results_dir / 'results.csv')))
    assert len(pd_loaded_results) == len(status_collection.results)
