#########################################
Developer's notes on ``babs-status``
#########################################

============================================================
Logic flow of ``babs_status()`` method of ``BABS`` class
============================================================

Source code: ``babs/babs.py`` -> ``class BABS()`` --> ``def babs_status()``

* create ``job_status.csv`` if it does not exist yet
* get 'alert_log_messages' configs
* get username (to be used by ``qacct`` job accounting)
* get list of branches in output RIA with ``git branch -a`` (NOTE: this is quick, even for tons of branches)
* with ``job_status.csv`` file opened:

    * get original ``df_job``
    * make new one ``df_job_updated`` (copy of original one)
    * request ``qstat`` for **all** jobs: ``df_all_job_status``
    * for each job that has been submitted but not ``is_done``:

        * get basic information of this job
        * get last line of ``stdout`` file
        * check if any alert message in the log files (based on 'alert_log_messages')
        * if there is a branch of current job in output RIA, the job is done, and update ``df_job_updated``
        * if not, the job is pending/running/failed/eqw:

            * if the job is in the queue ``df_all_job_status``, i.e., is pending/running/eqw:

                * if ``r``:

                    * if ``--resubmit-job`` for this job & ``--reckless``: resubmit
                    * else: update ``df_job_updated``

                * if ``qw``:

                    * resubmit if 'pending' in ``flags_resubmit``, or request specifically: resubmit and update ``df_job_updated``
    
                * if ``eqw``: just update the job state code/category in ``df_job_updated``

                    * currently does not support resubmission, until this is tested

            * else, i.e., not in the queue, so failed:

                * update ``df_job_updated``
                * resubmit if 'failed' in ``flags_resubmit``, or request specifically: resubmit and update ``df_job_updated``
                * if did not resubmit:

                    * if ``--job-account`` and no alert messages in logs:

                        * do ``qacct``, and update 'job_account' column.

    * for each job that marked as "is_done" in previous round:

        * if ``--resubmit-job`` for this job & ``--reckless``: resubmit
        * else:

            * get last line of ``stdout`` file. Purpose: when marked as 'is_done' (got branch in output RIA), the job hasn't been finished yet, and needs to do ``datalad drop`` etc before echoing 'SUCCESS'. This is to make sure that we can get 'SUCCESS' for 'last_line_stdout_file' for 'is_done' jobs.
            * check if any alert message in the log files (based on 'alert_log_messages'); Purpose: update it for successful jobs too in case user updates the configs in yaml file

    * for jobs that haven't been submitted yet:

        * if ``--resubmit-job`` is requested, check if any requested jobs are not submitted yet; if so, throw out a warning

    * save ``df_jobs_updated``
    * summarize the job status and report

Summary:
- 'alert_log_messages' is detected in all submitted jobs, no matter 'is_done' in previous round or not