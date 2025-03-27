#######################################
Step III: Job submission and job status
#######################################

.. contents:: Table of Contents

.. _list_included_subjects:

***************************************************
List of included subjects (and sessions) to process
***************************************************

``babs init`` follows the steps below to determine the final list of included subjects (and sessions) to process:

#. Determine an initial list:

    * If ``--list-sub-file`` in ``babs init`` is provided by the user, use it as initial list
    * If not, BABS will list the subjects and sessions from the first input dataset, and use it as initial list

#. Filter the initial list: Remove subjects (and sessions) which do not have the required files
   that are defined in :ref:`required_files` in ``--container-config``
   provided when running ``babs init``.

Now, BABS gets the final included subjects (and sessions) to process.
It saves this list into a CSV file, named ``sub_final_inclu.csv`` (for single-session dataset)
or ``sub_ses_final_inclu.csv`` (for multiple-session dataset),
is located at ``/path/to/my_BABS_project/analysis/code``.

.. TODO: describe other saved csv files for e.g., exclusions

**********************************************************
Recommended workflow of job submission and status checking
**********************************************************

Processing large-scale datasets and handling hundreds or even thousands of jobs
can be tough. We hope BABS can help this process.
We recommend using ``babs submit`` and ``babs status`` in the following way;
in short, it's a iteration between ``babs submit`` and ``babs status``:

#. Check how many jobs need to run: run ``babs status /path/to/my_BABS_project``.
   This will return a summary that includes the number of jobs that are expected to complete.
   See :ref:`list_included_subjects` for how BABS determines this list of jobs to complete.
#. You may submit several exemplar jobs with ``babs submit``, then check job status
   with ``babs status`` to see if they finish successfully.
#. If there are failed jobs, you can use ``babs status`` to perform failed job auditing.

    * See :ref:`here <check-job-status-and-failed-job-auditing>` for example commands,
      and :ref:`here <setup-section-alert-log-messages>` for how to set it up.
    * Please make sure the job failures are related to subject- or session-specific problems,
      but not issues like "no enough memory or space" that other jobs could also encounter.
      Once you're sure about this, feel free to move on.

#. You may start to iteratively call ``babs submit`` and ``babs status`` until all jobs finish.
   See below for tips of each function.

=======================
Tips of ``babs submit``
=======================
You have several choices when running ``babs submit``:

* Submit one or several specific jobs by ``--job``;
* Submit N jobs (from the top of the list, jobs haven't been submitted yet) by ``--count N``;
* If your clusters allow, and you're confident to run BIDS App on all remaining subjects (and sessions),
  you may submit all remaining jobs by ``--all``.
  After then, only thing you need to do is to run ``babs status`` once a while until all jobs finish.

=======================
Tips of ``babs status``
=======================

.. _check-job-status-and-failed-job-auditing:

Recommended way to check job status (including failed job auditing)
-------------------------------------------------------------------

To check job status and perform failed job auditing,
you can use two options of ``babs status`` here:

* To save time,
  you may run::

    babs status \
        /path/to/my_BABS_project \
        --container-config /path/to/my_yaml_file.yaml

  i.e., using **alert_log_messages** in the YAML file for failed job auditing.
  See :ref:`the section below <setup-section-alert-log-messages>`
  for how to set up this section **alert_log_messages**.
  With the YAML file provided, this may take ~1.5 min for ~2500 jobs.

.. _setup-section-alert-log-messages:

Set up section ``alert_log_messages`` for failed job auditing
--------------------------------------------------------------

If there are failed jobs, you may be wondering why they failed.
A direct way to investigate is to check their log files, but it will take a lot of time to go through
all failed jobs' log files. ``babs status`` supports failed job auditing and summary
by searching pre-defined alert messages in the failed jobs' log files.
These alert messages are defined by you in the
section **alert_log_messages** in the container's configuration YAML file.

* In this section, please define some alert messages that might be found in the failed jobs' log files,
  Example alert message could be ``Excessive topologic defect encountered``.
  This is helpful for debugging.

* You may also refer to the example YAML files we provide
  in `folder "notebooks/" <https://github.com/PennLINC/babs/blob/main/notebooks/README.md>`_.
* Do not worry if you do not cover all alert messages on the first try;
  you can add/change this section **alert_log_messages** in the YAML file anytime you want,
  and simply call::

    babs status \
        /path/to/my_BABS_project \
        --container-config /path/to/updated_yaml_file.yaml

  to ask BABS to find updated list of alert messages.
* For more details about this section, please refer to :ref:`alert_log_messages`.

.. developer's note: cannot use relative path like: `here <../../notebooks/README.md>`_
..  After render by readthedocs online, "https://pennlinc-babs--103.org.readthedocs.build/" would be added to this path
..  making it a broken link. Although the rendered path looks fine when building the docs *locally*

Job resubmission
----------------

You can also resubmit jobs that are failed or pending.
See ``--resubmit`` and ``--resubmit-job`` in :doc:`babs-status` for more.

.. warning::
    Do NOT kill ``babs submit`` or ``babs status`` (especially with ``--resubmit*``)
    when it's running! Otherwise, new job IDs may not be captured or saved into the ``job_status.csv``!

.. _example_job_status_summary:

***********************************************
Example job status summary from ``babs status``
***********************************************

..  code-block:: console
    :linenos:

    $ babs status \
        /path/to/my_BABS_project \
        --container_config /path/to/config.yaml

    Did not request resubmit based on job states (no `--resubmit`).

    Job status:
    There are in total of 2565 jobs to complete.
    2565 job(s) have been submitted; 0 job(s) haven't been submitted.
    Among submitted jobs,
    697 job(s) are successfully finished;
    1543 job(s) are pending;
    260 job(s) are running;
    65 job(s) are failed.

    Among all failed job(s):
    1 job(s) have alert message: 'stdout file: Numerical result out of range';
    56 job(s) have alert message: 'BABS: No alert message found in log files.';
    1 job(s) have alert message: 'stdout file: fMRIPrep failed';
    7 job(s) have alert message: 'stdout file: Excessive topologic defect encountered';

    Among job(s) that are failed and don't have alert message in log files:
    56 job(s) have job account of: 'qacct: failed: 37  : qmaster enforced h_rt, h_cpu, or h_vmem limit';

    All log files are located in folder: /path/to/my_BABS_project/analysis/logs


As you can see, in the summary ``Job status``, there are multiple sections:

#. Line #9-16: Overall summary of number of jobs to complete,
   as well as their breakdowns: number of jobs submitted/finished/pending/running/failed;
#. Line #18-22: Summary of failed jobs, based on the provided section **alert_log_messages** in
   ``--container-config-yaml-file``, BABS tried to find user-defined alert messages in failed jobs' log files;


Finally, you can find the log files (``stdout``, ``stderr``) in the path provided
in the last line of the printed message (line #27).


*********************************
Explanation on ``job_status.csv``
*********************************
As described above, BABS ``babs status`` has provided a summary of all the jobs.
This summary is based on ``job_status.csv`` (located at: ``/path/to/my_BABS_project/analysis/code``).
If you hope to dig out more information, you may take a look at this CSV file.

.. note::
    This ``job_status.csv`` file won't exist until the first time running ``babs submit`` or ``babs status``.

.. warning::
    Do NOT make changes to ``job_status.csv`` by yourself!
    Changes that are not made by ``babs submit`` or ``babs status`` may cause conflicts
    or confusions to BABS on the job status.

==========================
Loading ``job_status.csv``
==========================

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

.. _detailed_description_of_job_status_csv:

==========================================
Detailed description of ``job_status.csv``
==========================================

Each row in the ``job_status.csv`` is for a job, i.e., of a subject (single-session dataset),
or of a session of a subject (multiple-session dataset).

Below is description of each column.
Note: ``np.nan`` means numpy's NaN if loading the CSV file into Python.

* ``sub_id`` (and ``ses_id`` in multiple-session dataset): string, the subject ID (and session ID)
  for a job.
* ``has_submitted``: bool (True or False), whether a job has been submitted.
* ``job_id``: integer (usually positive), ID of a job. Before a job is submitted, ``job_id = -1``.
* ``job_state_category``: string or ``np.nan``, the category of a job's state,
  e.g., "pending", "running", etc. Before a job is submitted,
  ``job_state_category = np.nan``.
* ``job_state_code``: string or ``np.nan``, the code of a job's state,
  e.g., "qw",  "r", etc. Before a job is submitted, ``job_state_code = np.nan``.
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
  The path to the log files are indicated in the last line of printed message from ``babs status``.
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
    * This column of all submitted jobs will be updated every time ``babs status`` is called.
      It will be updated based on current ``--container-config`` (if provided).
      if ``--container-config`` is not provided,
      column ``alert_message`` will be reset to ``np.nan``.
    * If a job hasn't been submitted, or ``--container-config`` was not specified
      in ``babs status``, ``alert_message = np.nan``.


******************************************
FAQ for job submission and status checking
******************************************

Q: In printed messages from ``babs status``, what if the number of submitted jobs
does not match with the total number of jobs summarized under "Among submitted jobs"?

A: This should happen infrequently. Those "missing" jobs may in some uncommon or brief states
that BABS does not recognize. Please wait for a bit moment, and rerun ``babs status``.

.. developer's notes: if calling `babs status` immediately after `babs submit` on MSI SLURM cluster,
..  you may see this. This is because jobs are in atypical states `CF` (configuring).
..  Just wait several sec and rerun `babs status`.

Q: A job is done (i.e., ``is_done = True`` in ``job_status.csv``),
but column ``last_line_stdout_file`` is not ``SUCCESS``?

A: This should be an edge case. Simply run ``babs status`` again,
and it might be updated with 'SUCCESS'.


********
See also
********
:doc:`babs-submit`

:doc:`babs-status`
