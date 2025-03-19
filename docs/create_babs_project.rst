******************************
Step II: Create a BABS project
******************************

Initialize a BABS project using ``babs init``
===============================================

After you've prepared the three things BABS requires (details see here: :doc:`preparation`),
you can initialize a BABS project using ``babs init``. Please follow our documentation
:doc:`babs-init` describing how to use ``babs init``.

If the BIDS App you'll use requires TemplateFlow, please make sure you've set up the
environment variable ``TEMPLATEFLOW_HOME`` before running ``babs init``. See
:ref:`advanced_manual_singularity_run` --> the bullet point regarding "TemplateFlow" for more.

If ``babs init`` fails, by default BABS will remove ("clean up") the partially created BABS project.
To fix the problem, please read the error messages from ``babs init``.
After identifying where the problem is (potential places are listed below),
please fix the problem and rerun ``babs init``.

* Problems in ``babs init`` command?
* Problems in input BIDS dataset(s)?
* Problems in container DataLad dataset?
* Problems in container configuration YAML file?

If ``babs init`` finishes without error, you'll see this message at the end:

.. code-block:: console

    `babs init` was successful!


Sanity checks and diagnosis via ``babs check-setup``
====================================================

After ``babs init`` is done, please use ``babs check-setup`` to check everything is good.

``babs check-setup`` will perform these steps:

    1. Print out configurations of the BABS project;
    2. Perform sanity checks in this BABS project;
    3. Submit a test job to make sure necessary packages (e.g., `DataLad`) are installed in the designated environment.

Although the 3rd step is optional (only done when ``--job-test`` is specified),
we highly recommend doing so before you ``babs submit`` real jobs,
as real jobs often take much longer time and are harder to tell if the error comes from BIDS App itself,
or some setups in the BABS project.

Very importantly, ``babs check-setup`` can also be used as a diagnostic tool - its printed messages are helpful for debugging.
If you have trouble using ``babs init`` and hope to ask in a `GitHub issue <https://github.com/PennLINC/babs/issues>`_,
please try running ``babs check-setup`` and copy the printed messages in the GitHub issue.
