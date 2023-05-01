
Different scenarios:

| Instances     | 1st input dataset | 2nd input datasets    |
| :---:                  |    :----:             |         :---: |
| fMRIPrep     | raw BIDS, unzipped       | -   |
| QSIPrep   | raw BIDS, unzipped        | -      |
| XCP-D   | BIDS derivatives, zipped <br> (as positional argu `fmri_dir`)        | -      |
| fMRIPrep with FS ingressed   | raw BIDS, unzipped <br> (as positional argu `bids_dir`)        | BIDS derivatives, zipped <br> (as named argu `--fs-subjects-dir`)     |

BABS will make sure fMRIPrep, QSIPrep, XVP-D are perfect; if any other BIDS App rises, we will make it compatible then (roadmap)

No matter 1 or more input dataset(s), the input dataset will be cloned to `inputs/data/<input_ds_name>` - to be consistent. Also, `<input_ds_name>` is required.

What we need to know re: `XCP-D`:
* 1st input dataset:
  * give it a name: `fmriprep_outputs`  
  * it's zipped, [babs will detect whether it's zipped or not] so we need extra info:
  * zipped foldername suffix --> this can be got from `input_ds_name` --> detect the full name of the zipped foldername; BABS will have a sanity check: If there is no matched one, warning!
  * in this zipped folder, after unzipping, what's the relative path to the data as input? `fmriprep` which is from `input_ds_name`
    * no need, sanity check: unzip one and see if the foldername is `fmriprep`; finally `datalad drop`
  * where does this input data go? positional argu, or named argu?
    * ask the user to tell us, if more than one input ds


What we need to know re: fMRIPrep with FS ingressed:
* 1st input dataset:
  * give it a name: `BIDS`  # required, as >1 input dataset; the input dataset will be cloned to `inputs/data/BIDS`
  * it's raw BIDS dataset   
  * used as positional argu: user tell us in `singularity_run`
* 2nd input dataset:
  * give it a name: `freesurfer`
  * it's zipped,
  * zipped foldername suffix: we detect based on `freesurfer`
  * in this zipped folder, after unzipping, what's the relative path to the data as input? `freesurfer` --> this means that the path in babs is `inputs/data/freesurfer/freesurfer`   # first `freesurfer` is from the name user gives;
  * used as named argu: user tell us in `singularity_run` after that speicfic argu flag. see ppt. We'll teach user how to write this.
    * over-engineered: If it's named argu, probably another placeholder in `singularity_run`, e.g. `$INPUT_DATASET_#2`
