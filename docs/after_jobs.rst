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
