# Notebooks folder

## Example container configuration YAML files
* Naming convention: `eg_<bidsapp-0-0-0>_<task>_<system>_<cluster_name>.yaml`
    * `<bidsapp-0-0-0>`: BIDS App name and version
    * `<task>`:  For what application of BIDS App? Full run? Sloppy mode?
    * `<system>`: `sge` or `slurm`
    * `<cluster_name>`: name of example cluster where the YAML file was tested
* YAML files that have section **alert_log_messages** (not a full list):
    * [eg_fmriprep-20-2-3_anatonly_sge_cubic.yaml](eg_fmriprep-20-2-3_anatonly_sge_cubic.yaml)
