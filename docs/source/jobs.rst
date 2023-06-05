***************************************
Step III: Job submission and job status
***************************************

.. contents:: Table of Contents

.. _list_included_subjects:

List of included subjects (and sessions) to process
=====================================================
``babs-init`` follows the steps below to determine the final list of included subjects (and sessions) to process:

#. Determine an initial list:

    * If ``--list-sub-file`` in ``babs-init`` is provided by the user, use it as initial list
    * If not, BABS will list the subjects and sessions from the first input dataset, and use it as initial list

#. Filter the initial list: Remove subjects (and sessions) which do not have the required files
   that are defined in :ref:`required_files` in ``--container-config-yaml-file``
   provided when running ``babs-init``.

Now, BABS gets the final included subjects (and sessions) to process.
It saves this list into a CSV file, named ``sub_final_inclu.csv`` (for single-session dataset)
or ``sub_ses_final_inclu.csv`` (for multiple-session dataset),
is located at ``/path/to/my_BABS_project/analysis/code``.

.. TODO: describe other saved csv files for e.g., exclusions

Recommended workflow of job submission and status checking
==============================================================
Processing large-scale datasets and handling hundreds or even thousands of jobs
could be tough for many data analysts. We hope BABS could help this process.
For best experience, we recommend using ``babs-submit`` and ``babs-status`` in the following steps;
in short, it's a iteration between ``babs-submit`` and ``babs-status``:

#. Check how many jobs to run: run ``babs-status --project_root /path/to/my_BABS_project``.
   This will return a summary that includes number of jobs to complete.
   See :ref:`list_included_subjects` for how BABS determines this list of jobs to complete.
#. Fill section **alert_log_messages** in the YAML file:

    * You may submit several exemplar jobs with ``babs-submit``, then check job status
      with ``babs-status`` to see if they're failed, and in failed jobs' log files
      (usually in ``stdout`` and ``stderr`` files), what could be alert messages for the failure.
    * You may also refer to the example YAML files we provide (link: ______________).
    * No worry if you could not cover all alert messages at once;
      you can add/change this section **alert_log_messages** in the YAML file anytime you want,
      and simply call::
        
        babs-status \
            --project-root /path/to/my_BABS_project \
            --container-config-yaml-file /path/to/updated_yaml_file.yaml
        
      to ask BABS to find updated list of alert messages.
    * For more details about this section, please refer to :ref:`alert_log_messages`.

#. You may start to iteratively call ``babs-submit`` and ``babs-status`` until all jobs finish.
   See below for tips of each function.

Tips of ``babs-submit``
------------------------------
You have several choices when running ``babs-submit``:

* Submit one or several specific jobs by ``--job``;
* Submit N jobs (from the top of the list, jobs haven't been submitted yet) by ``--count N``;
* If your clusters allow, and you're confident to run BIDS App on all remaining subjects (and sessions),
  you may submit all remaining jobs by ``--all``.
  After then, only thing you need to do is to run ``babs-status`` once a while until all jobs finish.

Tips of ``babs-status``
------------------------------
* Recommended way to check job status: when running ``babs-status``,

    * To save time,
      you may run::
        
        babs-status \
            --project-root /path/to/my_BABS_project \
            --container-config-yaml-file /path/to/my_yaml_file.yaml
        
      i.e., YAML file provided but without ``--job-account``.
      With the YAML file provided, this may take ~1.5 min for ~2500 jobs.
    * If time allows, and there are failed jobs without alert messages,
      you may add ``--job-account``::
        
        babs-status \
            --project-root /path/to/my_BABS_project \
            --container-config-yaml-file /path/to/my_yaml_file.yaml \
            --job-account
            
      This may take longer time (e.g., ~0.5h for ~250 failed jobs without alert messages;
      also depending on the speed of the cluster).
* You can also resubmit jobs that are failed or pending.
  See ``--resubmit`` and ``--resubmit-job`` in :doc:`babs-status` for more.

.. warning::
    Do NOT kill ``babs-submit`` or ``babs-status`` (especially with ``--resubmit*``)
    when it's running! Otherwise, new job IDs may not be captured or saved into the ``job_status.csv``!

.. _example_job_status_summary:

Example job status summary from ``babs-status``
======================================================

.. code-block:: console

    $ babs-status \
        --project_root /path/to/my/BABS/project \
        --container_config_yaml_file /path/to/config.yaml \
        --job-account

    Did not request resubmit based on job states (no `--resubmit`).
    `--job-account` was requested; `babs-status` may take longer time...

    Job status:
    There are in total of 2565 jobs to complete.
    2565 job(s) have been submitted; 0 job(s) haven't been submitted.
    Among submitted jobs,
    376 job(s) are successfully finished;
    1900 job(s) are pending;
    286 job(s) are running;
    3 job(s) are failed.

    Among all failed job(s):
    1 job(s) have alert message: 'stdout file: fMRIPrep failed';
    2 job(s) have alert message: 'BABS: No alert message found in log files.';

    Among job(s) that are failed and don't have alert message in log files:
    2 job(s) have job account of: 'qacct: failed: 37  : qmaster enforced h_rt, h_cpu, or h_vmem limit';

    All log files are located in folder: /path/to/my/BABS/project/analysis/logs

TODO: change above with updated version of job auditing (after changing the YAML file section name to ``alert_log_messages``)


As you can see, in the summary ``Job status``, there are multiple sections:

#. Overall summary of number of jobs to complete, submitted, finished, pending, running, or failed;
#. Summary of failed jobs, based on the provided section **alert_log_messages** in
   ``--container-config-yaml-file``, BABS tried to find any alert message
   that includes the user-defined alert messages;
#. If there are jobs that are failed but don't have defined alert message,
   and ``--job-account`` is requested, BABS will then run job account
   and try to extract more information and summarize.
   For each of these jobs, BABS runs job account command (e.g., ``qacct`` on SGE clusters).
   BABS pulls out the code and message from ``failed`` section in ``qacct``.
   In above case, the 2 jobs are failed due to runtime exceeding the user-defined one,
   ``hard_runtime_limit: "48:00:00"``, i.e., ``-l h_rt:48:00:00``.

Finally, you can find the log files (``stdout``, ``stderr``) in the path provided
in the last line of the printed message.


Explanation on ``job_status.csv``
=======================================
As described above, BABS ``babs-status`` has provided a summary of all the jobs.
This summary is based on ``job_status.csv`` (located at: ``/path/to/my_BABS_project/analysis/code``).
If you hope to dig out more information, you may take a look at this CSV file.

.. note::
    This ``job_status.csv`` file won't exist until the first time running ``babs-submit`` or ``babs-status``.

.. warning::
    Do NOT make changes to ``job_status.csv`` by yourself!
    Changes that are not made by ``babs-submit`` or ``babs-status`` may cause conflicts
    or confusions to BABS on the job status.

Loading ``job_status.csv``
--------------------------------------

To take a look at ``job_status.csv``, you may load it into Python.
Below is an example python script of reading ``job_status.csv``::

    import numpy as np
    import pandas as pd

    fn_csv = "/path/to/my_BABS_project/analysis/code/job_status.csv"  # change this path
    df = pd.read_csv(csv_path,
                     dtype={"job_id": 'int',
                            'has_submitted': 'bool',
                            'is_done': 'bool'
                            })

    # print:
    with pd.option_context('display.max_rows', None,
                           'display.max_columns', None,
                           'display.width', 120):   # default is 80 characters
        print(df.head())   # print the first 5 rows

You can also slice ``df`` and extract only failed jobs, only jobs whose ``alert_message``
matches with a specific string, etc.


Detailed description of ``job_status.csv``
---------------------------------------------------

Each row in the ``job_status.csv`` is for a job, i.e., of a subject (single-session dataset),
or of a session of a subject (multiple-session dataset).

Below is description of each column.
Note: ``np.nan`` means numpy's NaN if loading the CSV file into Python.

* ``sub_id`` (and ``ses_id`` in multiple-session dataset): string, the subject ID (and session ID)
  for a job.
* ``has_submitted``: bool (True or False), whether a job has been submitted.
* ``job_id``: integer (usually positive), ID of a job. Before a job is submitted, ``job_id = -1``.
* ``job_state_category``: string or ``np.nan``, the category of a job's state,
  e.g., "pending", "running", etc on SGE clusters. Before a job is submitted,
  ``job_state_category = np.nan``.
* ``job_state_code``: string or ``np.nan``, the code of a job's state,
  e.g., "qw",  "r", etc on SGE clusters. Before a job is submitted, ``job_state_code = np.nan``.
* ``duration``: string or ``np.nan``, the runtime of a running job since it starts running,
  e.g., ``0:00:14.733701`` (i.e., 14.733701 sec). If a job is not running
  (not submitted, pending, finished, etc), ``duration = np.nan``.
* ``is_done``: bool (True or False), whether a job has been successfully finished,
  i.e., there is a result branch of this job in the output RIA.
* ``is_failed``: bool (True or False) or ``np.nan``, whether a job is failed.
  If a job has been submitted and it's out of job queues,
  but there is no result branch in the output RIA,
  this job is failed. Before a job is submitted, ``is_failed = np.nan``.
* ``log_filename``: string or ``np.nan``, the filename of the log file in the format of
  ``<jobname>.*<jobid>``, e.g., ``fmr_sub-xx.*11111``.
  Replace ``.*`` with ``.o`` or ``.e`` to get corresponding log filename.
  The path to the log files are indicated in the last line of printed message from ``babs-status``.
  Before a job is submitted, ``log_filename = np.nan``.

    * The log files can be printed in the terminal via ``cat`` (printing the entire file),
      ``head`` (printing first several lines), ``tail`` (printing last several lines), etc.
    * Also note that if a job hasn't started running, although its ``log_filename`` is a valid string,
      the log files won't exist until the job starts running.
* ``last_line_stdout_file``: string or ``np.nan``, the last line of current ``stdout`` file.
  Before a job is submitted, ``last_line_stdout_file = np.nan``.
* ``alert_message``: string or ``np.nan``, a message from BABS that whether BABS found any
  alert messages (defined in **alert_log_messages** in the YAML file) in the log files.

    * Example ``alert_message``: ``'stdout file: fMRIPrep failed'`` (alert messages found);
      ``BABS: No alert message found in log files.`` (alert messages not found).
    * This column of all submitted jobs will be updated every time ``babs-status`` is called.
      It will be updated based on current ``--container-config-yaml-file`` (if provided).
      if ``--container-config-yaml-file`` is not provided,
      column ``alert_message`` will be reset to ``np.nan``.
    * If a job hasn't been submitted, or ``--container-config-yaml-file`` was not specified
      in ``babs-status``, ``alert_message = np.nan``.
* ``job_account``: string or ``np.nan``, information extracted by running job account.
  This is designed for failed jobs that don't have alert message in the log files. More detailed explanation of how and what information is get by BABS can be found in :ref:`example_job_status_summary`. Other details about this column:

    * This column is only updated when ``--job-account`` is requested in ``babs-status``
      but ``--resubmit failed`` is not requested
    * For other jobs (not failed, or failed jobs but alert messages were found),
      ``job_account = np.nan``
    * if ``babs-status`` was called again, but without ``--job-account``,
      the previous round's ``job_account`` column will be kept, unless the job was resubmitted.
      This is because the job ID did not change, so job account information should not change for a finished job.


FAQ for job submission and status checking
=============================================

Q: In ``job_status.csv``, why column ``alert_message`` is updated every time ``babs-status`` is called,
whereas column ``job_account`` is only updated when ``--job-account`` is called?

A:

    #. ``alert_message`` is got from log files, which are dynamic as the jobs progress;
       also, ``alert_log_messages`` in the yaml file can also be changed in each ``babs-status`` call.
       On the other hand, only failed jobs have ``job_account`` with actual contents,
       and job account won't change after a job is finished (though failed).
    #. Updating ``alert_message`` is quick, whereas running job account
       (e.g., calling ``qacct`` on SGE clusters) is slow

Q: A job is done (i.e., ``is_done = True`` in ``job_status.csv``),
but column ``last_line_stdout_file`` is not ``SUCCESS``?

A: This should be an edge case. Simply run ``babs-status`` again,
and it might be updated with 'SUCCESS'.
