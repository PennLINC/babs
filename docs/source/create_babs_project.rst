******************************
Step I: Create a BABS project
******************************

Initialize a BABS project using ``babs-init``
===============================================

After you've prepared the three things BABS requires (details see here: :doc:`preparation`), 
now you can initialize a BABS project using ``babs-init``.

If anything failed along the way of ``babs-init``,
please fix the problems in the inputs according to the printed messages.
Depend on the what you've changed, you should rerun ``babs-init`` or re-create a BABS project:

* **Case 1**: If you've changed the path to/contents in any input dataset,
  or the path to/contents in container BIDS App DataLad dataset:

  * You should remove the current BABS project by following steps below, 
    and then create a new one with ``babs-init``.

.. code-block:: console

    # How to remove a BABS project:

    cd <project_root>/analysis   # replace <project_root> with the absolute path to the BABS project

    # Remove input dataset(s):
    datalad remove -d inputs/data/<input_ds_name>   # replace <input_ds_name> with your input dataset's name
    # Repeat the command above until all input datasets have been removed
    # if above command leads to "drop impossible" due to modified content, add `--reckless modification` at the end

    git annex dead here
    datalad push --to input
    datalad push --to output
    pwd
    cd ../..   # outside of <project_root>
    rm -rf <project_root>

* **Case 2**: If you only changed the container's configuration YAML file (used in `--container-config-yaml-file`):

  * You can simply rerun ``babs-init`` until it finishes without error.

You should repeat above steps until ``babs-init`` finishes without error,
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
