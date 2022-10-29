This docs show how to prepare inputs following BABS's requirements.

# Input dataset(s)
## If single-ses
TODO: not to restrict this!! `particpant_job.sh` should get the appropriate zip filename

* if zipped, must follow the pattern of `sub-*_<name>*.zip`, where `<name>` is the name of this input dataset.
    * there should not be `ses-*` in this zip filename.
    * all zip filename must follow the same pattern, i.e., the characters between `<name>` and `.zip` must be consistent across all zip files.

## How does BABS determine whether it's a zipped or unzipped input dataset?
* If there are both zipped file (`sub-*.zip`) and unzipped folders (`sub-*`), then it is considered as a zipped input dataset.
    * therefore, if you have an unzipped dataset, please do not include zipped files called `sub-*.zip`.