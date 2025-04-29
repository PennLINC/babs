*********************************
Step IV: After jobs have finished
*********************************

.. contents:: Table of Contents

Step 3.1. Merge the results and provenance
==========================================

Once all jobs have finished, the results will be on different branches.
Please use ``babs merge`` to merge the results and provenance
from all the successfully finished jobs:

.. code-block:: bash

    babs merge /path/to/my_BABS_project

See :ref:`babs_merge_cli` for details.

If ``babs merge`` finishes successfully, you'll see::

    `babs merge` was successful!

Otherwise, there were some warnings or errors.

Step 3.2. Get the results
=========================

Now you can get the results out by cloning the output RIA:

.. code-block:: bash

    datalad clone \
        ria+file:///absolute/path/to/my_BABS_project/output_ria#~data \
        my_BABS_project_outputs

Please replace ``/absolute/path/to/my_BABS_project`` with the full path to your BABS project root directory.
Here ``my_BABS_project_outputs`` is an example clone of the output RIA.

Now, in ``my_BABS_project_outputs``, you should be able to see zip files containing the results
for all subjects (and sessions). You can access the contents of one zip file via::

    datalad get zip_file_name.zip

And you can unzip it via::

    unzip zip_file_name.zip

What if my input data changes?
==============================

If your input data changes, you can use ``babs update-input-data`` to update the job status dataframe.

.. _babs_update_input_data:

Updating Input Data
-------------------

The ``babs update-input-data`` command allows you to update the job status dataframe when your input data changes.
This is useful when:

- New subjects or sessions are added to your input dataset
- Existing subjects or sessions are removed from your input dataset
- The data for existing subjects or sessions is updated

The command will:

1. Check if there are any unmerged results branches (you must run ``babs merge`` first)
2. Update the job status dataframe to reflect the current state of your input data
3. Save the updated job status dataframe

Usage:

.. code-block:: bash

    babs update-input-data /path/to/my_BABS_project [--dataset-name DATASET_NAME] [--initial-inclusion-df INITIAL_INCLUSION_DF]

Arguments:

- ``/path/to/my_BABS_project``: Path to your BABS project root directory
- ``--dataset-name DATASET_NAME``: Name of the dataset to update (default: 'BIDS')
- ``--initial-inclusion-df INITIAL_INCLUSION_DF``: Path to a CSV file containing the initial inclusion list (optional)

See section :ref:`babs_update_input_data` for details.
