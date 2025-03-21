.. _babs-sync-code:

babs sync-code
=============

.. program:: babs sync-code

Synopsis
--------

.. code-block:: text

    babs sync-code [PROJECT_ROOT] [-m MESSAGE]

Description
----------

The ``babs sync-code`` command saves and pushes code changes from the BABS project's `analysis/code` directory back to the `input` dataset. This is useful when you have made modifications to the code in your BABS project and want to propagate these changes back to the original input dataset.

The command will:
1. Save all changes in the `analysis/code` directory using datalad
2. Push these changes back to the `input` dataset
3. Use a default commit message if none is specified

The following files are automatically excluded from being saved:
- `job_status.csv` and `job_status.csv.lock`
- `job_submit.csv` and `job_submit.csv.lock`

Arguments
---------

.. option:: PROJECT_ROOT

    Absolute path to the root of BABS project.
    For example, '/path/to/my_BABS_project/'.
    If not specified, defaults to the current working directory.

Options
-------

.. option:: -m, --message MESSAGE

    Commit message for datalad save.
    If not specified, defaults to '[babs] sync code changes'.

Examples
--------

1. Basic usage with default options:

   .. code-block:: bash

       babs sync-code

2. Specify a custom project root and commit message:

   .. code-block:: bash

       babs sync-code /path/to/my_babs_project -m "Updated singularity run command"

Notes
-----

- This command must be run from within a valid BABS project
- Changes are saved and pushed from the `analysis/code` directory only
- The command will fail if the `analysis/code` directory does not exist
- Job status and submission files are automatically excluded from being saved

See Also
--------

- :ref:`babs-init`
- :ref:`babs-submit`
- :ref:`babs-status` 