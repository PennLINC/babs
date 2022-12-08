# Check the job's log file
- The column 'log_filename' indicates the job's log filename. For SGE cluster, simply replace "*" with "o" or "e" etc.
    - "<jobname>.o<jobid>": standard output stream of the job
    - "<jobname>.e<jobid>": standard error stream of the job
- The log files for a job won't exist before the job starts running.
- The path to the log files are indicated in the sentences of 'Job status' summary when `babs-status`.
- The log files can be printed in the terminal via `cat` (print the entire file), `head` (print first several lines), `tail` (print last several lines), etc
    - `head -10 /path/to/log/file` will print the first 10 lines