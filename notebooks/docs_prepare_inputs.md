This docs show how to prepare inputs following BABS's requirements.

# Input dataset(s)

## If zipped
* For each input dataset: for each subject (in single-ses data), or each session (in multi-ses data), there should only be one zipped file whose filename contains input dataset's name
* The name of the folder within the zip file must be the input dataset's name, and this applies to all the subjects in this input dataset
* If it's single-ses, the zip filename should follow the pattern of `sub-*_<name>*.zip`, where `<name>` is the name of this input dataset.
    * can have `ses-*`
* If it's multi-ses, the zip filename should follow the pattern of `sub-*_ses-*_<name>*.zip`

## How does BABS determine whether it's a zipped or unzipped input dataset?
* If there are both zipped file (`sub-*.zip`) and unzipped folders (`sub-*`), then it is considered as a zipped input dataset.
    * therefore, if you have an unzipped dataset, please do not include zipped files called `sub-*.zip`.