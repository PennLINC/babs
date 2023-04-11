***************************************
Step III: After jobs are finished
***************************************

.. contents:: Table of Contents

Step 3.1. Merge the results and provenance
=============================================

After all jobs are finished, as the results are on different branches,
please use ``babs-merge`` to merge the results and provenance
from all the successfully finished jobs:

.. code-block:: bash

    babs-merge \
        --project-root /path/to/my_BABS_project

See :ref:`babs_merge_cli` for details.

If ``babs-merge`` finishes successfully, you'll see::
    
    `babs-merge` was successful!

Otherwise, there were some warnings or errors.
