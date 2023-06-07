*****************************
Developers and contributors
*****************************

============================
For potential contributors
============================
We welcome and appreciate any contributions to ``BABS``!
If you hope to contribute to ``BABS``, please make a pull request to
our :ref:`GitHub repository <https://github.com/PennLINC/babs>`.
It will be great to your commits pass all the checks,
including the Circle CI tests, spelling checks, and docs building.

===================================
Container configuration YAML file
===================================
.. # currently we only support the option of "singularity_run"
.. # In the future, we might:
..     # Priority: cli_call > singularity_run > cli_options
..         # If anything provided at higher level, the lower levels will be ignored.

Developer's notes:

* It's safe to include escape character ``\`` in values for keyword ``customized_text``
  in the section ``cluster_resources``.

    * However for this section,
      adding ``\`` might not be what you want or not necessary at all, or even cause error:
    * Please note that when adding job submission options,
      there is different between how to add it to job submission command in command line
      (e.g., ``qsub`` on SGE clusters)
      and how to add it to a script's header (or preambles).

        * In command line (e.g., ``qsub``),
          ``\`` is needed for an exclamation mark ``!`` (e.g., in ``-l hostname=\!compute-fed*``),
          as ``!`` has a meaning in bash;
        * However here, in a header (or preamble) of a script to be submitted,
          ``\`` is not necessary, as there will be ``#`` at the beginning.
          Instead, you should just have ``#$ -l hostname=!compute-fed*`` (without ``\``) to keyword ``customized_text``
          in the section ``cluster_resources``. If you do add ``\``, it may even cause error,
          e.g., on Penn Med CUBIC cluster::

            Unable to run job: Parse error on position 2 of the expression "\!compute-fed*"
