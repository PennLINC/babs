# Providing keywords of alerting messages in log files:
- Detecting is performed in the order provided by the user, i.e., if `o_file` is former, then that's performed earlier; if keyword1 is former, then that's performed earlier.
- "Detected and break": If any keyword is detected, that will be thrown into the `job_status.csv`, and won't detect any further keyword.
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