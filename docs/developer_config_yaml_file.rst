=======================================================
Developer's notes on container configuration YAML file
=======================================================
.. # currently we only support the option of "bids_app_args"
.. # In the future, we might:
..     # Priority: cli_call > bids_app_args > cli_options
..         # If anything provided at higher level, the lower levels will be ignored.

Developer's notes:

* It's safe to include escape character ``\`` in values for keyword ``customized_text``
  in the section ``cluster_resources``.

    * However for this section,
      adding ``\`` might not be what you want or not necessary at all, or even cause an error

