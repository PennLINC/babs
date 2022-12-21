# Providing keywords of alerting messages in log files:
- Detecting is performed in the order provided by the user, i.e., if `o_file` is former, then that's performed earlier; if keyword1 is former, then that's performed earlier.
- "Detected and break": 
    - If any keyword is detected, that will be thrown into the `job_status.csv`, and won't detect any further keyword.
    - If keywords have been detected in the first file (say, 'o_file'), then won't detect any keyword in the other log file ('e_file' in this example case)
- Detecting the keywords in the log files (by `keyword in line`) is case-sensitve! 

# Check the job's log file
- The column 'log_filename' indicates the job's log filename. For SGE cluster, simply replace "*" with "o" or "e" etc.
    - "<jobname>.o<jobid>": standard output stream of the job
    - "<jobname>.e<jobid>": standard error stream of the job
- The log files for a job won't exist before the job starts running.
- The path to the log files are indicated in the sentences of 'Job status' summary when `babs-status`.
- The log files can be printed in the terminal via `cat` (print the entire file), `head` (print first several lines), `tail` (print last several lines), etc
    - `head -10 /path/to/log/file` will print the first 10 lines

# `babs-status`
- For jobs labeled as 'is_done = True': 
    - if 'last_line_o_file' is not 'SUCCESS', run `babs-status` again, and it might be updated with 'SUCCESS'. This should be an edge case.

# How to interpret in `job_status.csv`?
Below are explanation by columns:

- `alert_message`: any alert keywords detected in the log files (`.o` or `.e`), where the alert keywords are defined in `babs-status --container-config-yaml-file`
    - All submitted jobs' `alert_message` column will be updated every time `babs-status` is called, based on current `container-config-yaml-file` (if provided)
        - if `--container-config-yaml-file` is not provided, column `alert_message` will be reset to `numpy.nan`
- `job_account`:
    - only updated when `--job-account`, and `--resubmit failed` was not requested
    - `qacct` is only called for failed jobs, but not other jobs (where `numpy.nan` will display)
    - if `babs-status` was called again, but without `--job-account`, the previous round's 'job_account' column will be kept, unless the job was resubmitted.
        - This is because the job ID did not change, so `qacct` should not change for a finished job.

- why `alert_message` is updated every time `babs-status` is called, whereas `job_account` is only updated when `--job-account` is called? This is because:
    1. `alert_message` is got from log files, which are dynamic as the jobs progress; also, `keywords_alert` in the yaml file can also be changed in each `babs-status` call. On the other hand, only failed jobs have `job_account` with actual contents, and job account won't change after a job is finished (though failed).
    1. Updating `alert_message` is quick, whereas calling `qacct` (SGE clusters) is slow