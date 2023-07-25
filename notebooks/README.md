# Notebooks folder

## Example container configuration YAML files
* Naming convention: `eg_<bidsapp-0-0-0>_<task>_<system>_<cluster_name>.yaml`
    * `<bidsapp-0-0-0>`: BIDS App name and version
    * `<task>`:  For what application of BIDS App? Full run? Sloppy mode?
    * `<system>`: `sge` or `slurm`
    * `<cluster_name>`: name of example cluster where the YAML file was tested
* YAML files that have section **alert_log_messages** (not a full list):
    * [eg_fmriprep-20-2-3_anatonly_sge_cubic.yaml](eg_fmriprep-20-2-3_anatonly_sge_cubic.yaml)

### List of example container configuration YAML file:

| example YAML file | BIDS App | BIDS App version | for what | input BIDS dataset(s) | cluster system | Notes | 
| :-- | :--|:-- | :-- |:-- | :-- | :-- |
| [link](eg_toybidsapp-0-0-7_rawBIDS_sge_cubic.yaml) | toy BIDS App | 0.0.7 |for processing raw BIDS dataset | one raw BIDS dataset | SGE | |
| [link](eg_toybidsapp-0-0-7_rawBIDS_slurm_msi.yaml) | toy BIDS App | 0.0.7 |for processing raw BIDS dataset | one raw BIDS dataset | Slurm | |
| [link](eg_toybidsapp-0-0-7_zipped_sge_cubic.yaml) | toy BIDS App | 0.0.7 |for processing zipped BIDS derivatives dataset | one zipped BIDS derivatives dataset | SGE | |
| [link](eg_toybidsapp-0-0-7_zipped_slurm_msi.yaml) | toy BIDS App | 0.0.7 |for processing zipped BIDS derivatives dataset | one zipped BIDS derivatives dataset | Slurm | |
| [link](eg_fmriprep-20-2-3_full_sge_cubic.yaml) | fMRIPrep | 20.2.3 | Full run of fMRIPrep | one raw BIDS dataset | SGE | |
| [link](eg_fmriprep-20-2-3_anatonly_sge_cubic.yaml) | fMRIPrep | 20.2.3 | fMRIPrep `--anat-only` mode | one raw BIDS dataset | SGE | |
| [link](eg_fmriprep-20-2-3_ingressed-fs_sge_cubic.yaml) | fMRIPrep | 20.2.3 | fMRIPrep with FreeSurfer results ingressed | one raw BIDS dataset + one zipped BIDS derivatives dataset (of FreeSurfer results) | SGE | |
| [link](eg_fmriprep-20-2-3_sloppy_sge_cubic.yaml) | fMRIPrep | 20.2.3 | fMRIPrep `--sloppy` mode | one raw BIDS dataset | SGE | ⚠️ WARNING: only for testing! ⚠️ |
| [link](eg_fmriprep-20-2-3_sloppy_slurm_msi.yaml) | fMRIPrep | 20.2.3 | fMRIPrep `--sloppy` mode | one raw BIDS dataset | Slurm | ⚠️ WARNING: only for testing! ⚠️ |
| [link](eg_fmriprepfake-0-1-2_full_slurm_msi.yaml) | fmriprep-fake | 0.1.2 | fmriprep-fake, mimicking current *BIDS output layout* of fMRIPrep (v21.0+) | one raw BIDS dataset | Slurm | |
| [link](eg_fmriprepfake-0-1-2_legacy-layout_slurm_msi.yaml) | fmriprep-fake | 0.1.2 | fmriprep-fake, mimicking *legacy output layout* of fMRIPrep (< v21.0) | one raw BIDS dataset | Slurm | |
| [link](eg_fmriprepfake-0-1-2_anatonly_slurm_msi.yaml) | fmriprep-fake | 0.1.2 | fmriprep-fake, using `--anat-only` | one raw BIDS dataset | Slurm | ⚠️ WARNING: For version `0.1.2`, although `--anat-only` is on, the generated files won't be different and will still include fMRI derivatives. |
| [link](eg_qsiprep-0-16-0RC3_sloppy_sge_cubic.yaml) | QSIPrep | 0.16.0RC3 | QSIPrep `--sloppy` mode | one raw BIDS dataset | SGE | ⚠️ WARNING: only for testing! |
| [link](eg_qsiprep-0-16-0RC3_sloppy_slurm_msi.yaml) | QSIPrep | 0.16.0RC3 | QSIPrep `--sloppy` mode | one raw BIDS dataset | Slurm | ⚠️ WARNING: only for testing! |
| [link](eg_xcpd-0-3-0_full_sge_cubic.yaml ) | XCP-D | 0.3.0 | XCP full run | one zipped BIDS derivatives dataset (of fMRIPrep results) | SGE | |

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
