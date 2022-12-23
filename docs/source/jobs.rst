******************************
Job submission and job status
******************************

Example job status summary (from ``babs-status``):
----------------------------------------------------

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
    287 job(s) are running;
    2 job(s) are failed.

    Among all failed job(s):
    2 job(s) have alert message: 'BABS: No alert keyword found in log files.';

    Among job(s) that are failed and don't have alert keyword in log files:
    2 job(s) have job account of: 'qacct: failed: 37  : qmaster enforced h_rt, h_cpu, or h_vmem limit';

    All log files are located in folder: /path/to/my/BABS/project/analysis/logs

Explanation on ``job_status.csv``
------------------------------------
Provide some explanations _______________