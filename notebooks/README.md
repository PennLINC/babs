# Notebooks folder

## Example container configuration YAML files

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
| [link](eg_toybidsapp-0-0-7_rawBIDS-walkthrough.yaml) | toy BIDS App | 0.0.7 | for testing BABS on a *raw* BIDS dataset | one raw BIDS dataset | This is used in the [example walkthrough](https://pennlinc-babs.readthedocs.io/en/stable/walkthrough.html); please refer to that doc for how to customize this YAML file.  ||
| [link](eg_toybidsapp-0-0-7_zipped.yaml) | toy BIDS App | 0.0.7 | for testing BABS on a *zipped* BIDS derivatives dataset | one zipped BIDS derivatives dataset |  |
| [link](eg_qsiprep-0-18-1_regular.yaml) | QSIPrep | 0.18.1 | regular use of QSIPrep | one raw BIDS dataset | This does not include `qsirecon` workflow |
| [link](eg_fmriprep-23-1-3_regular.yaml) | fMRIPrep | 23.1.3 | regular use of fMRIPrep | one raw BIDS dataset |  |
| [link](eg_fmriprep-23-1-3_anatonly.yaml) | fMRIPrep | 23.1.3 | fMRIPrep `--anat-only` | one raw BIDS dataset |  |
| [link](eg_fmriprep-23-1-3_ingressed-fs.yaml) | fMRIPrep | 23.1.3 | fMRIPrep with FreeSurfer results ingressed | one raw BIDS dataset + one zipped BIDS derivatives dataset of FreeSurfer results | For 2nd input dataset, you may use results from fMRIPrep `--anat-only` (see example YAML [here](eg_fmriprep-23-1-3_anatonly.yaml)) |
| [link](eg_fmriprep-20-2-3_regular.yaml) | fMRIPrep | 20.2.3 | regular use of fMRIPrep | one raw BIDS dataset |  |
| [link](eg_fmriprep-20-2-3_anatonly.yaml) | fMRIPrep | 20.2.3 | fMRIPrep `--anat-only` | one raw BIDS dataset | Only `freesurfer` folder is saved. |
| [link](eg_fmriprep-20-2-3_ingressed-fs.yaml) | fMRIPrep | 20.2.3 | fMRIPrep with FreeSurfer results ingressed | one raw BIDS dataset + one zipped BIDS derivatives dataset of FreeSurfer results | For 2nd input dataset, you may use results from fMRIPrep `--anat-only` (see example YAML [here](eg_fmriprep-20-2-3_anatonly.yaml)) |
| [link](eg_xcpd-0-4-0_nifti.yaml) | XCP-D | 0.4.0 | for NIfTI images (i.e., without `--cifti`) | one zipped BIDS derivatives dataset of fMRIPrep results | The 0.4.0 version of XCP-D is labeled as `04.0` on Docker Hub.  |


Note that because fMRIPrep changed its default output layout in version `21.0`, here we provide example YAML files for both a recent version (`23.1.3`) and an older version (`20.2.3`). The recent version uses BIDS output layout, whereas the older one uses legacy output layout. This difference reflects in the `zip_folernames` section.

## Other files
- Example initial subject list for toy BIDS datasets:
  - [initial_sub_list_multi-ses.csv](initial_sub_list_multi-ses.csv)
  - [initial_sub_list_single-ses.csv](initial_sub_list_single-ses.csv)
