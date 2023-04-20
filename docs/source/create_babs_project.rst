******************************
Step II: Create a BABS project
******************************

Initialize a BABS project using ``babs-init``
===============================================

After you've prepared the three things BABS requires (details see here: :doc:`preparation`), 
now you can initialize a BABS project using ``babs-init``.

If ``babs-init`` fails, by default it will remove ("clean up") the created, failed BABS project.
What you need to do is to read the error messages and fix the problem (e.g., any problem
in ``babs-init`` command call, in your input dataset(s), in your container DataLad dataset,
or in the container's YAML file, etc). Then rerun ``babs-init`` until it finishes without error,
i.e., printing the message as below at the end:

.. code-block:: console

    `babs-init` was successful!


Sanity checks and diagnosis via ``babs-check-setup``
====================================================

After ``babs-init`` is done, please use ``babs-check-setup`` to check everything is good.

``babs-check-setup`` will perform these steps:

    1. Print out configurations of the BABS project;
    2. Perform sanity checks in this BABS project;
    3. Submit a test job to make sure necessary packages (e.g., `DataLad`) are installed in the designated environment.

Although the 3rd step is optional (only done when ``--job-test`` is specified),
we highly recommend doing so before you ``babs-submit`` real jobs,
as real jobs often take much longer time and are harder to tell if the error comes from BIDS App itself,
or some setups in the BABS project.

Very importantly, ``babs-check-setup`` can also be used as a diagnostic tool - its printed messages are helpful for debugging.
If you have trouble using ``babs-init`` and hope to ask in a `GitHub issue <https://github.com/PennLINC/babs/issues>`_,
please try running ``babs-check-setup`` and copy the printed messages in the GitHub issue.
