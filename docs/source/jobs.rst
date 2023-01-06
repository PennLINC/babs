******************************
Job submission and job status
******************************

.. contents:: Table of Contents

List of included subjects (and sessions) to run
=====================================================
This csv is located at: __________-
TODO: describe how this final list is got!

Recommended workflow of job submission and status checking
==============================================================
Processing large-scale datasets and handling hundreds or even thousands of jobs could be tough for many data analysts. We hope BABS could help this process.
For best experience, we recommend using ``babs-submit`` and ``babs-status`` in the following steps; in short, it's a iteration between ``babs-submit`` and ``babs-status``:

#. Check how many jobs to run: run ``babs-status --project_root /path/to/my_BABS_project``. This will return a summary that includes number of jobs to complete.
#. Fill section **keywords_alert** in the YAML file:

    * You may submit several exemplar jobs with ``babs-submit``, then check job status with ``babs-status`` to see if they're failed, and in failed jobs' log files (usually in ``*.o*`` and ``*.e*`` files), what could be alerting keywords for the failure.
    * You may also refer to the example YAML files we provide (link: ______________).
    * No worry if you could not cover all alerting keywords at once; you can add/change this section **keywords_alert** in the YAML file anytime you want, and simply call ``babs-status --project-root /path/to/my_BABS_project --container-config-yaml-file /path/to/updated_yaml_file.yaml`` to ask BABS to find updated list of alerting keywords.
    * For more details about this section, please refer to :ref:`keywords_alert`.

#. You may start to iteratively call ``babs-submit`` and ``babs-status`` until all jobs are finished. See below for tips of each function.

Tips of ``babs-submit``
------------------------------
You have several choices when running ``babs-submit``:

* Submit one or several specific jobs by ``--job``;
* Submit N jobs (from the top of the list, jobs haven't been submitted yet) by ``--count N``;
* If your clusters allow, and you're confident to run BIDS App on all remaining subjects (and sessions), you may submit all remaining jobs by ``--all``. After then, only thing you need to do is to run ``babs-status`` once a while until all jobs are finished.

Tips of ``babs-status``
------------------------------
* Recommended way to check job status: when running ``babs-status``,

    * To save time, you may run ``babs-status --project-root /path/to/my_BABS_project --container-config-yaml-file /path/to/my_yaml_file.yaml``, i.e., YAML file provided but without ``--job-account``. With the YAML file provided, this may take ~1.5 min for ~2500 jobs.
    * If time allows, and there are failed jobs without alert messages, you may add ``--job-account``, i.e., ``babs-status --project-root /path/to/my_BABS_project --container-config-yaml-file /path/to/my_yaml_file.yaml --job-account``. This may take longer time (e.g., ~0.5h for ~250 failed jobs without alerting keywords; also depending on the speed of the cluster)
* You can also resubmit jobs that are failed or pending. See ``--resubmit`` and ``--resubmit-job`` in :doc:`babs-status` for more.

TODO: remove ``stalled``; remove ``--reckless`` until it's tested.

.. warning::
    Do NOT kill ``babs-submit`` or ``babs-status`` (especially with ``--resubmit*``) when it's running! Otherwise, new job IDs may not be captured or saved into the ``job_status.csv``!


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
    1 job(s) have alert message: '.o file: fMRIPrep failed';
    2 job(s) have alert message: 'BABS: No alert keyword found in log files.';

    Among job(s) that are failed and don't have alert keyword in log files:
    2 job(s) have job account of: 'qacct: failed: 37  : qmaster enforced h_rt, h_cpu, or h_vmem limit';

    All log files are located in folder: /path/to/my/BABS/project/analysis/logs


As you can see, in the summary ``Job status``, there are multiple sections:

#. Overall summary of number of jobs to complete, submitted, finished, pending, running, or failed
#. Summary of failed jobs, based on the provided section **keywords_alert** in ``--container-config-yaml-file``, BABS tried to find any alert message that includes the user-defined alerting keywords
#. If there are jobs that are failed but don't have defined alert keyword, and ``--job-account`` is requested, BABS will then run job account and try to extract more information and summarize. For each of these jobs, BABS runs job account command (e.g., ``qacct`` on SGE clusters). BABS pulls out the code and message from ``failed`` section in ``qacct``. In above case, the 2 jobs are failed due to runtime exceeding the user-defined one, ``hard_runtime_limit: "48:00:00"``, i.e., ``-l h_rt:48:00:00``.

Finally, you can find the log files (``*.o*``, ``*.e*``) in the path provided in the last line of the printed message.


Explanation on ``job_status.csv``
=======================================
As described above, BABS ``babs-status`` has provided a summary of all the jobs.
This summary is based on ``job_status.csv`` (located at: ``/path/to/my_BABS_project/analysis/code``).
If you hope to dig out more information, you may take a look at this CSV file.


.. note::
    This ``job_status.csv`` file won't exist until the first time running ``babs-submit`` or ``babs-status``.

.. warning::
    Do NOT make changes to ``job_status.csv`` by yourself! Changes that are not made by ``babs-submit`` or ``babs-status`` may cause conflicts or confusions to BABS on the job status.

Below is the description for each column in this file.

Provide some explanations _______________


