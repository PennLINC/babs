# `datalad-status`
## Logic flow of method `datalad_status()` of class BABS

* create `job_status.csv` if it does not exist yet
* get 'alert_log_messages' configs
* get username (to be used by `qacct` job accounting)
* get list of branches in output RIA with `git branch -a` (NOTE: this is quick, even for tons of branches)
* with `job_status.csv` file opened:
    * get original `df_job`
    * make new one `df_job_updated` (copy of original one)
    * request `qstat` for **all** jobs: `df_all_job_status`
    * for each job that has been submitted but not `is_done`:
        * get basic information of this job
        * get last line of `stdout` file
        * check if any alert message in the log files (based on 'alert_log_messages')
        * if there is a branch of current job in output RIA, the job is done, and update `df_job_updated`
        * if not, the job is pending/running/failed/eqw:
            * if the job is in the queue `df_all_job_status`, i.e., is pending/running/eqw:
                * if `r`:
                    * if `--resubmit-job` for this job & `--reckless`: resubmit
                    * else: update `df_job_updated`
                * if `qw`:
                    * resubmit if 'pending' in `flags_resubmit`, or request specifically: resubmit and update `df_job_updated`
                * if `eqw`: just update the job state code/category in `df_job_updated`
                    * currently does not support resubmission, until this is tested
            * else, i.e., not in the queue, so failed:
                * update `df_job_updated`
                * resubmit if 'failed' in `flags_resubmit`, or request specifically: resubmit and update `df_job_updated`
                * if did not resubmit:
                    * if `--job-account` and no alert messages in logs:
                        * do `qacct`, and update 'job_account' column.

    * for each job that marked as "is_done" in previous round:
        * if `--resubmit-job` for this job & `--reckless`: resubmit
        * else:
            * get last line of `stdout` file. Purpose: when marked as 'is_done' (got branch in output RIA), the job hasn't been finished yet, and needs to do `datalad drop` etc before echoing 'SUCCESS'. This is to make sure that we can get 'SUCCESS' for 'last_line_stdout_file' for 'is_done' jobs.
            * check if any alert message in the log files (based on 'alert_log_messages'); Purpose: update it for successful jobs too in case user updates the configs in yaml file

    * for jobs that haven't been submitted yet:
        * if `--resubmit-job` is requested, check if any requested jobs are not submitted yet; if so, throw out a warning

    * save `df_jobs_updated`
    * summarize the job status and report

Summary:
- 'alert_log_messages' is detected in all submitted jobs, no matter 'is_done' in previous round or not

## Resubmit based on job's status:
Note: currently, `babs-status` CLI does not support `--reckless`

| job status | what to do if resubmit is requested | progress | tested? |
| :-- | :--|:-- | :-- |
| not submitted | warning: `babs-submit` first | added | edge case, not tested yet |
| submitted, qw | resubmit | added | tested with multi-ses data |
| submitted, running | with `--reckless`, resubmit; else, warning, not to resubmit | added | edge case, not tested yet |
| submitted, eqw | 1) CLI does not allow `resubmit stalled`; 2) if `--resubmit-job` of a stalled job, warning, not to resubmit | added | not tested yet, as cannot enter eqw... |
| submitted, failed | resubmit | added | tested with multi-ses data |
| submitted, is_done | with `--reckless`, resubmit; else, warning, not to resubmit | added, one TODO | not tested yet |


# Example `job_status.csv`
## When just initialized:
```
sub_id,ses_id,has_submitted,job_id,job_state_category,job_state_code,duration,is_done,is_failed,log_filename,last_line_stdout_file,alert_message,job_account
sub-01,ses-A,False,-1,,,,False,,,,,
```
when `print(df)` by python:
```
   sub_id ses_id  has_submitted  job_id  job_state_category  job_state_code  \
0  sub-01  ses-A          False      -1                 NaN             NaN

   duration  is_done  is_failed  log_filename  last_line_stdout_file  alert_message  job_account
0       NaN    False        NaN           NaN               NaN            NaN          NaN
```
(`0` at the beginning: index of pd.DataFrame)

# Testing
## Create pending, failed, or stalled jobs
Change/Add these in `participant_job.sh`:
- failed: see next section
- pending: increase `-l h_vmem` and `-l s_vmem`; increase `-pe threaded N`
- stalled (`eqw`): skip this for now. See Bergman email 12/20/22

After these changes, `datalad save -m "message"` and `datalad push --to input`

## Create failed cases for testing `babs-status` failed job auditing
* Add `sleep 3600` to `container_zip.sh`; make sure you `datalad save` the changes
* Change hard runtime limit to 20min (on SGE: `-l h_rt=0:20:00`)
* Create failed cases:
    * when the job is pending, manually kill it
        * For Slurm cluster: you'll see normal msg from `State` column of `sacct` msg when `--job-account`
        * For SGE cluster: you'll see warning that `qacct` failed for this job - this is normal. See PR #98 for more details.
    * when the job is running, manually kill it
    * wait until the job is running out of time, killed by the cluster
        * if you don't want to wait for that long, just set the hard runtime limit to very low value, e.g., 20 sec
* Perform job auditing using `--container-config-yaml-file`:
    * add some msg into the `alert_log_messages`, which can be seen in the "failed" jobs - for testing purpose
        * although they can be normal msg seen in successful jobs
* Perform job auditing using `--job-account` (and `--container-config-yaml-file`):
    * delete the `alert_log_messages` from the yaml file;
    * Now, you should see job account for these failed jobs

# Terminology

- "<jobname>.o<jobid>": standard output stream of the job
- "<jobname>.e<jobid>": standard error stream of the job