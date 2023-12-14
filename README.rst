
BABS: BIDS App Bootstrap
===============================

.. image:: https://readthedocs.org/projects/pennlinc-babs/badge/?version=latest
  :target: http://pennlinc-babs.readthedocs.io/en/latest/?badge=latest
  :alt: Documentation Status
.. image:: https://circleci.com/gh/PennLINC/babs/tree/main.svg?style=svg
  :target: https://circleci.com/gh/PennLINC/babs/tree/main
.. image:: https://zenodo.org/badge/456981533.svg
   :target: https://zenodo.org/badge/latestdoi/456981533
   :alt: DOI

Full documentation at https://pennlinc-babs.readthedocs.io

About
---------
BIDS App Bootstrap (BABS) is a reproducible, generalizable, and
scalable Python package for BIDS App analysis of large datasets.
It uses `DataLad <https://www.datalad.org/>`_ and adopts
the `FAIRly big framework <https://doi.org/10.1038/s41597-022-01163-2>`_.
Currently, BABS supports jobs submissions and audits on Sun Grid Engine (SGE) and Slurm
high performance computing (HPC) clusters.

Please cite our paper if you use BABS:

    Zhao, C., Jarecka, D., Covitz, S., Chen, Y., Eickhoff, S. B.,
    Fair, D. A., Franco, A. R., Halchenko, Y. O., Hendrickson, T. J., Hoffstaedter, F.,
    Houghton, A., Kiar, G., Macdonald, A., Mehta, K., Milham, M. P.,
    Salo, T., Hanke, M., Ghosh, S. S., Cieslak, M. & Satterthwaite, T. D. (2024).
    A reproducible and generalizable software workflow
    for analysis of large-scale neuroimaging data collections using BIDS Apps.
    *Imaging Neuroscience*. Accepted.

Currently, the paper has been accepted for publication in *Imaging Neuroscience*.
The *bioRxiv* version can be found `here <https://doi.org/10.1101/2023.08.16.552472>`_.


BABS programs
---------------------

.. image:: https://github.com/PennLINC/babs/raw/main/docs/source/_static/babs_cli.png
.. Note: this image is taken from the main branch, so it's normal that docs built from branches is not up-to-date.
..  If using relative path, e.g., `_static/babs_cli.png`, although readthedocs front page would look good, GitHub front page cannot find that image!!! 

Schematic of BABS workflow
----------------------------
.. image:: https://github.com/PennLINC/babs/raw/main/docs/source/_static/babs_workflow.png
.. Note: this image is taken from the main branch, so it's normal that docs built from branches is not up-to-date.

Background and Significance
-------------------------------

Neuroimaging research faces a crisis of reproducibility.
With massive sample sizes and greater data complexity, this problem becomes more acute.
The BIDS Apps - the software operating on BIDS data - have provided a substantial advance.
However, even using BIDS Apps, a full audit trail of data processing is a necessary prerequisite for fully reproducible research.
Obtaining a faithful record of the audit trail is challenging - especially for large datasets.
Recently, the `FAIRly big framework <https://doi.org/10.1038/s41597-022-01163-2>`_
was introduced as a way to facilitate reproducible processing of large-scale data
by leveraging `DataLad <https://www.datalad.org/>`_ - a version control system for data management.
However, the current implementation of this framework remains challenging to general users. 

BABS was developed to address these challenges
and to facilitate the reproducible application of BIDS Apps to large-scale datasets.
