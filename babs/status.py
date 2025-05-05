import os.path as op
from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass
class StatusKey:
    sub_id: str
    ses_id: str | None = None

    def __post_init__(self):
        self.key = (self.sub_id, self.ses_id)


@dataclass
class JobStatus:
    """
    This class is used to get the status of the jobs.
    """

    job_id: int = -1
    task_id: int = -1
    state: str = 'Unknown'
    time_used: str = 'Unknown'
    time_limit: str = 'Unknown'
    nodes: int = 0
    cpus: int = 0
    partition: str = 'Unknown'
    name: str = 'Unknown'
    sub_id: str | None = None
    ses_id: str | None = None


@dataclass
class ResultStatus:
    """
    This class is used to get the status of the results.
    """

    has_results: bool = False
    is_failed: bool = False
    result_location: Literal['branch', 'zip'] | None = None
    submitted: bool = False
    sub_id: str | None = None
    ses_id: str | None = None


class StatusCollection:
    """
    This class is used to get the status of the jobs and results.
    """

    status_ids: list[StatusKey]
    results: dict[tuple[str, str | None], ResultStatus]
    jobs: dict[tuple[str, str | None], JobStatus]

    def __init__(
        self,
        inclusion_df: pd.DataFrame | str,
        results: pd.DataFrame | str | None = None,
        jobs: pd.DataFrame | str | None = None,
    ):
        if isinstance(inclusion_df, str):
            inclusion_df = pd.read_csv(inclusion_df)
        self.status_ids = [
            StatusKey(row['sub_id'], row.get('ses_id', None))
            for row in inclusion_df.to_dict(orient='records')
        ]
        self.status_ids.sort(key=lambda x: x.key)
        self.results = {}
        self.jobs = {}
        self.update_results(results)
        self.update_jobs(jobs)

    def update_jobs(self, new_jobs: pd.DataFrame | str | list[JobStatus] | None = None):
        """
        Update the jobs in the StatusCollection.

        The total number of jobs in this dataframe will always be equal to the
        number of subjects in the inclusion_df.

        Parameters
        ----------
            new_jobs: pd.DataFrame | str | list[JobStatus]
                The new jobs to update the StatusCollection with. If a str, it assumed
                to be the path to a csv file containing the jobs. If a pd.DataFrame,
                it is assumed to have the correct columns and will be converted to a
                dict of JobStatus objects. If a list, it is assumed to be a list of
                JobStatus objects.
        """
        # Ensure we have a list of JobStatus objects
        if isinstance(new_jobs, str) or isinstance(new_jobs, pd.DataFrame):
            job_list = _load_jobs(new_jobs)
        elif isinstance(new_jobs, list):
            job_list = new_jobs
        else:
            job_list = []

        # Create a dictionary of JobStatus objects
        jobs = {}
        for job in job_list:
            key = (job.sub_id, job.ses_id)
            jobs[key] = job
            # Update the results to show that the job has been submitted
            self.results[key].submitted = True

        # For any keys not in the updated, keep the old jobstatus or make an empty new one
        all_keys = {status_id.key for status_id in self.status_ids}
        missing_jobs_keys = all_keys - set(jobs.keys())
        for key in missing_jobs_keys:
            jobs[key] = self.jobs.get(key, JobStatus(sub_id=key[0], ses_id=key[1]))
        self.jobs = jobs

    def update_results(self, new_results: pd.DataFrame | str | list[ResultStatus] | None = None):
        # Ensure we have a list of ResultStatus objects
        if isinstance(new_results, str) or isinstance(new_results, pd.DataFrame):
            result_list = _load_results(new_results)
        elif isinstance(new_results, list):
            result_list = new_results
        else:
            result_list = []

        # Create a dictionary of ResultStatus objects
        results = {}
        for result in result_list:
            key = (result.sub_id, result.ses_id)
            results[key] = result

        # Warn about any keys in results_df that are not in all_keys:
        all_keys = {status_id.key for status_id in self.status_ids}
        missing_results_keys = all_keys - set(results.keys())
        for key in missing_results_keys:
            results[key] = self.results.get(key, ResultStatus(sub_id=key[0], ses_id=key[1]))
        self.results = results

    def write_results(self, output_dir: str):
        # Convert None to pd.NA for writing to CSV
        results_df = pd.DataFrame(self.results.values()).replace({None: pd.NA})
        results_df.to_csv(op.join(output_dir, 'results.csv'), index=False)
        jobs_df = pd.DataFrame(self.jobs.values()).replace({None: pd.NA})
        jobs_df.to_csv(op.join(output_dir, 'jobs.csv'), index=False)


def _load_jobs(new_jobs: pd.DataFrame | str):
    if isinstance(new_jobs, str):
        new_jobs = pd.read_csv(new_jobs)
    # Convert nan to None
    jobs_dict = new_jobs.replace({pd.NA: None, pd.NaT: None}).to_dict(orient='records')
    return [JobStatus(**row) for row in jobs_dict]


def _load_results(new_results: pd.DataFrame | str):
    if isinstance(new_results, str):
        new_results = pd.read_csv(new_results)
    # Convert nan to None
    results_dict = new_results.replace({pd.NA: None, pd.NaT: None}).to_dict(orient='records')
    return [ResultStatus(**row) for row in results_dict]


def results_from_branches(branches: list[str]):
    """
    Get the results from the branches.
    """
    results = []
    for branch in branches:
        results.append(ResultStatus(branch=branch))
