####################################
Developer's notes on ``babs status``
####################################

============================================================
Logic flow of the ``babs_status()`` method of ``BABS`` class
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

        * get basic information about this job
        * get the last line of ``stdout`` file
        * check if there are any alert messages in the log files (based on 'alert_log_messages')
        * if the job has a branch in the output RIA, the job is done, so we update ``df_job_updated``
        * if not, the job is pending/running/failed/eqw:

            * if the job is in the queue ``df_all_job_status``, i.e., is pending/running/eqw:

                * if ``r``:

                    * if ``--resubmit-job`` for this job & ``--reckless``: resubmit
                    * else: update ``df_job_updated``

                * if ``qw``:

                    * resubmit if 'pending' in ``flags_resubmit``, or request specifically: resubmit and update ``df_job_updated``

                * if ``eqw``: just update the job state code/category in ``df_job_updated``

                    * currently does not support resubmission, won't support this feature until it has been tested

            * else, i.e., not in the queue, so failed:

                * update ``df_job_updated``
                * resubmit if 'failed' in ``flags_resubmit``, or request specifically: resubmit and update ``df_job_updated``

    * for each job that marked as "is_done" in previous round:

        * if ``--resubmit-job`` for this job & ``--reckless``: resubmit
        * else:

            * get last line of ``stdout`` file. Purpose: when marked as 'is_done' (has a branch in output RIA), the job hasn't been finished yet, and needs to complete cleanup steps such as datalad dropping the input data before echoing 'SUCCESS'. This is to make sure that we can get 'SUCCESS' for 'last_line_stdout_file' for 'is_done' jobs.
            * check if any alert message in the log files (based on 'alert_log_messages'); Purpose: update it for successful jobs too in case user updates the configs in yaml file

    * for jobs that haven't been submitted yet:

        * if ``--resubmit-job`` is requested, check if any requested jobs have not yet been submitted; if so, throw a warning

    * save ``df_jobs_updated``
    * summarize the job status and report

Summary:
- 'alert_log_messages' is detected in all submitted jobs, no matter 'is_done' in previous round or not


===================================
Resubmissions based on job's status
===================================

Note: currently, ``babs status`` CLI does not support ``--reckless``.

.. list-table:: Current BABS's responses when resubmission is requested
   :header-rows: 1

   * - job status
     - what to do if resubmit is requested
     - progress of implementation in BABS
     - tested?
   * - not submitted
     - warning: ``babs submit`` first
     - added
     - edge case, not tested yet?
   * - submitted, qw
     - resubmit
     - added
     - tested with session data
   * - submitted, running
     - 1. CLI does not allow ``--reckless``;
       2. if ``--resubmit-job`` of a running job, warning, not to resubmit
     - added
     - edge case, not tested yet?
   * - submitted, eqw
     - 1. CLI does not allow ``resubmit stalled``;
       2. if ``--resubmit-job`` of a stalled job, warning, not to resubmit
     - added
     - edge case; not tested yet, as cannot enter eqw...
   * - submitted, failed
     - resubmit
     - added
     - tested with session data
   * - submitted, is_done
     - 1. CLI does not allow ``--reckless``;
       2. if ``--resubmit-job`` of a finished job, warning, not to resubmit
     - added, one TODO
     - edge case, not tested yet?

.. developer's note: CZ remembers she tested those edge cases (except eqw one) on 6/5/23 Mon after
..  handling issue #85, but the terminals were closed so she did not have a log for this

==========================
Example ``job_status.csv``
==========================

When this CSV was just initialized::

    sub_id,ses_id,has_submitted,job_id,job_state_category,job_state_code,duration,is_done,is_failed,log_filename,last_line_stdout_file,alert_message
    sub-01,ses-A,False,-1,,,,False,,,,


when ``print(df)`` by python::

        sub_id ses_id  has_submitted  job_id  job_state_category  job_state_code  \
    0  sub-01  ses-A          False      -1                 NaN             NaN

        duration  is_done  is_failed  log_filename  last_line_stdout_file  alert_message
    0       NaN    False        NaN           NaN               NaN            NaN

Note: ``0`` at the beginning: index of pd.DataFrame

.. _how_to_test_out_babs_status:

===============================
How to test out ``babs status``
===============================

-----------------------------
Create pending or failed jobs
-----------------------------

Change/Add these in ``participant_job.sh``:

- failed: see next section
- pending: Please increase the cluster resources you request,
  e.g., memory, number of CPUs, temporary disk space, etc.

    - on SLurm clusters: increase ``#SBATCH --mem``, ``#SBATCH --tmp``, etc

After these changes, ``datalad save -m "message"`` and ``datalad push --to input``

-------------------------------------------------------------------
Create failed cases for testing ``babs status`` failed job auditing
-------------------------------------------------------------------

* Add ``sleep 3600`` to ``container_zip.sh``; make sure you ``datalad save`` the changes
* Change hard runtime limit to 20min (on SGE: ``-l h_rt=0:20:00``)
* Create failed cases:

    * when the job is pending, manually kill it

        * For SLURM cluster: you'll see normal msg from ``State`` column of ``sacct`` msg
        * For SGE cluster: you'll see warning that ``qacct`` failed for this job - this is normal. See PR #98 for more details.

    * when the job is running, manually kill it
    * wait until the job is running out of time, killed by the cluster

        * if you don't want to wait for that long, just set the hard runtime limit to very low value, e.g., 20 sec

* Perform job auditing using ``--container-config``:

    * add some msg into the ``alert_log_messages``, which can be seen in the "failed" jobs - for testing purpose

        * although they can be normal msg seen in successful jobs

===========
Terminology
===========

- ``<jobname>.o<jobid>``: standard output stream of the job
- ``<jobname>.e<jobid>``: standard error stream of the job