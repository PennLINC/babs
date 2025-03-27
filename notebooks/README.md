# Notebooks folder

## Example container configuration YAML files

Here we provide a few example container configuration YAML files
for different use cases. With customization, these YAML files can be applied to Slurm clusters.
Note that because of inevitable differences across clusters, these YAML files
require customization before you apply it to your cluster.
We provide hints in the YAML files (e.g., `[FIX ME]`) for how to customize it.
For more, please refer to [the documentation for how to prepare a container configuration YAML file](https://pennlinc-babs.readthedocs.io/en/stable/preparation_config_yaml_file.html).

Please also note that, these YAML files were prepared for specific
versions of the BIDS Apps. If there are changes in the BIDS App itself (e.g., argument names) in different BIDS App versions, please change the YAML files accordingly.
In addition, please check if the function of the YAML files (especially the `bids_app_args` section) fits your purpose.

* Naming convention: `eg_<bidsapp-0-0-0>_<task>.yaml`
    * `<bidsapp-0-0-0>`: BIDS App name and version
    * `<task>`:  How this BIDS App is applied? Regular application? Or some specific use case?

| example YAML file | BIDS App | BIDS App version | for what | input BIDS dataset(s) | Notes |
| :-- | :--|:-- | :-- |:-- | :-- |
| [link](eg_toybidsapp-0-0-7_rawBIDS-walkthrough.yaml) | toy BIDS App | 0.0.7 | for testing BABS on a *raw* BIDS dataset | one raw BIDS dataset | This is used in the [example walkthrough](https://pennlinc-babs.readthedocs.io/en/stable/walkthrough.html); please refer to that doc for how to customize this YAML file.  ||
| [link](eg_toybidsapp-0-0-7_zipped.yaml) | toy BIDS App | 0.0.7 | for testing BABS on a *zipped* BIDS derivatives dataset | one zipped BIDS derivatives dataset |  |
| [link](eg_qsiprep-1-0-0_regular.yaml) | QSIPrep | 1.0.0 | regular use of QSIPrep | one raw BIDS dataset | This does not include `qsirecon` workflow |
| [link](eg_qsirecon-1-0-1.yaml) | QSIRecon | 1.0.1 | regular use of QSIRecon | one QSIPrep derivatives dataset | For processing QSIPrep outputs |
| [link](eg_fmriprep-24-1-1_regular.yaml) | fMRIPrep | 24.1.1 | regular use of fMRIPrep | one raw BIDS dataset |  |
| [link](eg_fmriprep-24-1-1_anatonly.yaml) | fMRIPrep | 24.1.1 | fMRIPrep `--anat-only` | one raw BIDS dataset |  |
| [link](eg_fmriprep-24-1-1_ingressed-fs.yaml) | fMRIPrep | 24.1.1 | fMRIPrep with FreeSurfer results ingressed | one raw BIDS dataset + one zipped BIDS derivatives dataset of FreeSurfer results | For 2nd input dataset, you may use results from fMRIPrep `--anat-only` |
| [link](eg_xcpd-0-10-6_linc.yaml) | XCP-D | 0.10.6 | XCP-D with LINC mode | one zipped BIDS derivatives dataset of fMRIPrep results | Includes multiple atlases for connectivity analysis |
| [link](eg_mriqc-24-0-2.yaml) | MRIQC | 24.0.2 | regular use of MRIQC | one raw BIDS dataset | For quality control metrics |
| [link](eg_aslprep-0-7-5.yaml) | ASLPrep | 0.7.5 | regular use of ASLPrep | one raw BIDS dataset | For processing arterial spin labeling (ASL) data |

## Other files
- Example initial subject list for toy BIDS datasets:
  - [initial_sub_list_multi-ses.csv](initial_sub_list_multi-ses.csv)
  - [initial_sub_list_single-ses.csv](initial_sub_list_single-ses.csv)
