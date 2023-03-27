**********************
Overview of BABS
**********************


BIDS App Bootstrap (BABS) is a user-friendly Python package for reproducibly
running image processing software and auditing the outcomes of those runs at scale.
BABS features several command-line interface programs (highlighted in blue):

.. image:: https://github.com/PennLINC/babs/raw/enh/docs/docs/source/_static/babs_cli.png
.. ^^ change `enh/docs` to `main` after merging the branch into main!

BABS requires three stuff as inputs (please refer to :doc:`preparation` for details):

1. DataLad dataset of BIDS dataset(s). This could be raw BIDS data, or zipped results from another BABS project.
2. DataLad dataset of containerized BIDS App.
3. A YAML file of parameters for executing the BIDS App etc.

The first step is to set up a BABS project.
With these three inputs, ``babs-init`` initializes a BABS project.
It will clone input dataset(s) and containerized BIDS App. It will also
generate scripts that will later be used internally. These scripts will
complete the FAIRly big workflow framework. ``babs-check-setup`` will then
perform sanity checks and make sure the BABS project is ready for job running.
Details about BABS project initiation and checks are on this page: :doc:`create_babs_project`.

The next step is to run the jobs for subjects (and sessions, if input is a multi-session dataset).
You can iteratively call ``babs-submit`` and ``babs-status`` to submit jobs, check existing
jobs' status, and resubmit the jobs if failed or pending. To make it easy to handle large number
of jobs, ``babs-status`` also checks the job status, audits outcomes of existing runs, and returns a summary
descriptions. Details about job submission and status checking are on this page: :doc:`jobs`. The result for each subject (and session)
will be zipped and pushed to a remote indexed archive (RIA) store as a separate branch.
Most importantly, all provenance is tracked by DataLad, including code, containerized BIDS Apps,
origin of input data, related metadata, and the exact command run.


After all the jobs are done, results from all the jobs will be merged with ``babs-merge``.

To consume the results, ``babs-unzip`` will be used to decompress zipped results and get requested files.
This can be done by the same person who ran the whole data analysis process,
or by any other researchers who have the access to the BABS results (or a clone of the results).
