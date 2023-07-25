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

============
pytest
============

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

