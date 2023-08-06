# Notebooks folder

## Example container configuration YAML files
* Naming convention: `eg_<bidsapp-0-0-0>_<task>_<system>_<cluster_name>.yaml`
    * `<bidsapp-0-0-0>`: BIDS App name and version
    * `<task>`:  For what application of BIDS App? Full run? Sloppy mode?
    * `<system>`: `sge` or `slurm`
    * `<cluster_name>`: name of example cluster where the YAML file was tested


### Example container configuration YAML files
Here we provide a few example container configuration YAML files
for different use cases. With customization, these YAML files can be applied to both SGE and Slurm clusters.
Note that because of inevitable differences across clusters, these YAML files
require customization before you apply it to your cluster.
We provide hints in the YAML files (e.g., `[FIX ME]`) for how to customize it.
For more, please refer to [the documentation for how to prepare a container configuration YAML file](https://pennlinc-babs.readthedocs.io/en/stable/preparation_config_yaml_file.html).

Please also note that, these YAML files were prepared for specific
versions of the BIDS Apps. If there are changes in the BIDS App itself (e.g., argument names) in different BIDS App versions, please change the YAML files accordingly.
In addition, please check if the function of the YAML files (especially the `singularity_run` section) fits your purpose.

* Naming convention: `eg_<bidsapp-0-0-0>_<task>.yaml`
    * `<bidsapp-0-0-0>`: BIDS App name and version
    * `<task>`:  How this BIDS App is applied? Regular application? Or some specific use case?

| example YAML file | BIDS App | BIDS App version | for what | input BIDS dataset(s) | Notes | 
| :-- | :--|:-- | :-- |:-- | :-- |
| [link](eg_toybidsapp-0-0-7_rawBIDS-walkthrough_sge_cubic.yaml) | toy BIDS App | 0.0.7 | for testing BABS on a raw BIDS dataset | one raw BIDS dataset | This is used in the [example walkthrough](https://pennlinc-babs.readthedocs.io/en/stable/walkthrough.html); please refer to that doc for how to customize this YAML file.  ||
| [link](eg_toybidsapp-0-0-7_zipped.yaml) | toy BIDS App | 0.0.7 | for testing BABS on a zipped BIDS derivatives dataset | one zipped BIDS derivatives dataset |  |
| [link](xxxx) | QSIPrep | 0.18.1 | regular use of QSIPrep | one raw BIDS dataset |  |

### BIDS App links
| BIDS App | Function | Docker Hub | Docs | Notes | 
| :-- | :--|:-- | :-- |:-- |
| fMRIPrep | Preprocessing fMRI data | ___ | ___ | The default output layout changed in `21.0.0`. BABS YAML files for new BIDS layout and legacy layout are different. |
| QSIPrep | Preprocessing dMRI data | [Docker Hub](https://hub.docker.com/r/pennbbl/qsiprep) | ____ | |
| XCP-D | Post-processing fMRI data | ____ | _____ | The 0.4.0 version is labeled as `04.0` on Docker Hub. |
| toy BIDS App | Quick test of BABS | ____ | _____ | |
| fmriprep-fake | Mimics fMRIPrep output layout and generates fake derivatives, for quick test | [Docker Hub](https://hub.docker.com/r/djarecka/fmriprep_fake); Version 0.1.2 is available [here](https://hub.docker.com/r/chenyingzhao/fmriprep_fake) | see its [GitHub repo](https://github.com/djarecka/fmriprep-fake) |  |

* fMRI = functional MRI
* dMRI = diffusion MRI
