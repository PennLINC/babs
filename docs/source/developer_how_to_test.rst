*****************************
How to test BABS
*****************************

After some changes in the source code, it's important to test BABS and evaluate if it's behaving as expected.
There are two general steps to test BABS:

1. Run pytest, which can be automatically run by CircleCI
2. Manual tests on an HPC cluster (SGE or Slurm)

The reason that BABS requires some manual tests is that, it is challenging to mimic a HPC job scheduler's behaviors
in a container required by CircleCI. However, we are working on building a container to do so,
and we welcome other researchers to help this too - please
see `issue #113 <https://github.com/PennLINC/babs/issues/113>`_ for more.

================
Step 1. pytest
================

The pytest of BABS can be done manually or automatically on CircleCI, without the need of being on an HPC cluster.

------------------------------------
Manually run pytest
------------------------------------

Currently, the pytest could be run on Linux system (preferred) as well as Mac M1 chip system.

* If you run pytest on a local computer, please make sure Docker has been launched and running;
* If you run pytest on HPC clusters, please make sure Singularity software has been loaded.

Before you run pytest, please install BABS in the following way so that necessary packages
for our testing infrastructure will also be installed::
    
    cd <path/to/babs>    # change dir to the root of cloned `babs` github repository
    pip install -e .[tests]

At present, the pytest of BABS only covers testing ``babs-init`` and ``babs-check-setup``,
due to challenges of running tests interactively with a job scheduler.

You should run all pytest. After running pytest, you should not receive error messages.
Warning messages are fine.

To run all tests in pytest::

    cd <path/to/babs>    # change dir to the root of cloned `babs` github repository
    pytest -sv    # `-sv` is optional, and it means verbose + print messages

If you have access to multiple CPUs, you may speed up the testing by running tests in parallel::

    pytest -sv -n 2   # using 2 CPUs

All pytest are defined in ``tests/test_*.py``. To run tests defined in a specific file::

    pytest -sv tests/<test_*.py>   # replace `<test_*.py>` with the actual file name

To run tests for a specific case (defined in ``@pytest.mark.parametrize()``)::

    pytest -sv tests/<test_*.py>::<test_function_name>[toybidsapp-BIDS-single-ses-False-False]
    # please replace `<*>` with actual file or function names;
    # `[*]` is the combination of the parameters; above is just an example.

    # e.g.: pytest -sv tests/test_babs_init.py::test_babs_init[toybidsapp-BIDS-single-ses-False-False]

All command-line flags of ``pytest`` can be found `here <https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags>`_

--------------------------------
Automatic pytest via CircleCI
--------------------------------

Whenever there is a commit to GitHub, CircleCI tests will be triggered, and it will automatically run the pytest.

=======================================================
Step 2. Manual tests on an HPC cluster (SGE or Slurm)
=======================================================

Currently pytest does not cover ``babs-submit``, ``babs-status`` and ``babs-merge``.
Therefore, we need to manually test them on an HPC cluster with SGE or Slurm job scheduler system.

--------------------------------------------------------------------
General guidelines for testing ``babs-submit`` and ``babs-status``
--------------------------------------------------------------------

In theory, we should test on both SGE and Slurm systems. However, researchers may not have access
to both systems. Therefore, if you make a pull request, please let us know which HPC job scheduler system
you've used to test.

You should use a single-session dataset and a multi-session dataset to go through the comprehensive test checklist.
Toy datasets can be found :ref:`here <example_input_BIDS_datasets_for_BABS>`.

You may use the toy BIDS App to test out. See :doc:`here <preparation_container>` for more.

After running each command below, please check the printed messages and the updated ``job_status.csv``.
The first 6 lines of ``job_status.csv`` will be printed;
this CSV file can be found at: ``analysis/code/job_status.csv`` in a BABS project.
The explanations of this CSV file can be found :ref:`here <detailed_description_of_job_status_csv>`.

------------------------------------
Testing ``babs-submit``
------------------------------------

Comprehensive test checklist (please add ``--project-root``):

- [ ] ``babs-submit`` (submitting one job)
- [ ] ``babs-submit --job``
- [ ] ``babs-submit --count``

------------------------------------
Testing ``babs-status``
------------------------------------

Comprehensive test checklist (please add ``--project-root``):

- [ ] ``babs-status``

------------------------------------
Testing ``babs-merge``
------------------------------------