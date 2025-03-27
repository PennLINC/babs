****************
How to test BABS
****************

After some changes in the source code, it's important to test BABS and evaluate if it's behaving as expected.
There are two general steps to test BABS:

1. Run pytest, which can be automatically run by CircleCI
2. Manual tests on an HPC cluster (SLURM)

The reason that BABS requires some manual tests is that, it is challenging to mimic a HPC job scheduler's behaviors
in a container required by CircleCI. However, we are working on building a container to do so,
and we welcome other researchers to help this too - please
see `issue #113 <https://github.com/PennLINC/babs/issues/113>`_ for more.

==============
Step 1. pytest
==============

The pytest of BABS can be done manually or automatically on CircleCI, without the need of being on an HPC cluster.

-------------------
Manually run pytest
-------------------

The easiest way to run pytest is to run the ``tests/pytest_in_docker.sh`` script
from the root directory of BABS.
This will build a docker container that has a running SLURM job scheduler system.
It will also install the local copy of BABS and run the pytests in the container.

-----------------------------
Automatic pytest via CircleCI
-----------------------------

Whenever there is a commit to GitHub, CircleCI tests will be triggered, and it will automatically run the pytest.

==============================================
Step 2. Manual tests on an HPC cluster (SLURM)
==============================================

Currently pytest does not cover ``babs submit``, ``babs status`` and ``babs merge``.
Therefore, we need to manually test them on an HPC cluster with a SLURM job scheduler system.

There are two general steps in manual testing:

* Step 2.1 Tests using a toy BIDS data and the toy BIDS App
* Step 2.2 Real application using a large-scale dataset and a real BIDS App

Note that here we provide a comprehensive list of tests, which would be important to go through before a new release
(if there are major changes in job submissions/status checking).
However, for minor changes in the source code, comprehensive testing may not be necessary and more focused tests may be sufficient.
If you are not sure which tests are sufficient, we are happy to discuss.

------------------------------------------------------------------
General guidelines for testing ``babs submit`` and ``babs status``
------------------------------------------------------------------

For Step 2.1 Tests using a toy BIDS data and the toy BIDS App,
if the looping of the jobs (subjects in single-session data, or subject/session pairs in multi-session data) were changed,
you should have two rounds of testing, one using a single-session dataset, the other using a multi-session dataset.
Toy datasets can be found :ref:`here <example_input_BIDS_datasets_for_BABS>`.

You may use the toy BIDS App to test out. See :doc:`here <preparation_container>` for more.

After running each ``babs submit`` or ``babs status`` below,
please check the printed messages and the updated ``job_status.csv``.
This CSV file can be found at: ``analysis/code/job_status.csv`` in a BABS project.
The explanations of this CSV file can be found :ref:`here <detailed_description_of_job_status_csv>`.

----------------------------------------
Step 2.1.1: Testing ``babs check-setup``
----------------------------------------

Comprehensive test checklist (please add ``project_root``):

- [ ] ``babs merge --job-test`` --> see if the information summarized by BABS is correct
  (e.g., information of designated environment and temporary workspace)

-----------------------------------
Step 2.1.2: Testing ``babs submit``
-----------------------------------

Comprehensive test checklist (please add ``project_root``):

- [ ] ``babs submit`` (to submit one job)
- [ ] ``babs submit --job``
- [ ] ``babs submit --count``
- [ ] ``babs submit --all``

-----------------------------------
Step 2.1.3: Testing ``babs status``
-----------------------------------

Comprehensive test checklist (please add ``project_root``):

- [ ] ``babs status``
- [ ] ``babs status --resubmit failed``
- [ ] ``babs status --resubmit pending``
- [ ] ``babs status --resubmit-job <sub_id/ses_id of a failed job>``
- [ ] ``babs status --resubmit-job <sub_id/ses_id of a pending job>``
- [ ] ``babs status --resubmit-job <sub_id/ses_id of a running job>`` --> expect BABS to say not to submit a running job
- [ ] ``babs status --container-config-yaml-file path/to/config.yaml`` for failed job auditing


Please check out :ref:`this page <how_to_test_out_babs_status>`
for how to create failed and pending jobs.

----------------------------------
Step 2.1.4: Testing ``babs merge``
----------------------------------

Comprehensive test checklist (please add ``project_root``):

- [ ] ``babs merge``

---------------------------------------------------------------
Step 2.2: Testing using a large-scale dataset + a real BIDS App
---------------------------------------------------------------
This is to make sure that the updated code also works on a large-scale dataset
and when using a real BIDS App (e.g., fMRIPrep, QSIPrep).
This is especially important to test out when you have updated the workflow of status updates,
i.e., how ``job_status.csv`` is updated, or you revised the source code for generating BABS scripts
and the changes are related to a real BIDS App.

For example, you may use a dataset with hundreds of (or more) subjects or subject/session pairs.
Run BABS commands, and check if the content of generated scripts are as expected.
Then submit a few jobs.
While the jobs are running, use ``babs status`` to check their statuses and see
how long this command takes. It should not take a long time (see :doc:`jobs` for example run time).
Finally, check if you can successfully merge the results + get the zip file content + unzip it.
