#!/bin/bash
# Built-in babs `zip` hook: archive a BIDS App output folder, commit the
# archive, and remove the granular outputs it replaces.
#
# Copied verbatim at `babs init` into `code/hooks/zip.sh`. Runs at the
# `post_run` splice point (cwd = the job's dataset clone) as a separate
# process: `subid` (and `sesid` at session level) arrive via the exported
# splice-point contract; what to zip arrives as arguments:
#
#   zip.sh <path> [<name>]
#
# <path> is the folder to zip, relative to the dataset root. <name> is the
# archive-name stem (the X in ${subid}[_${sesid}]_X.zip), defaulting to
# <path>'s basename. The archive is written to the dataset root and contains
# the folder itself (not its parents), matching the layout of babs zips to
# date.
set -e -u -x

path="$1"
name="${2:-$(basename "$path")}"
zip_dir="$(dirname "$path")"
zip_folder="$(basename "$path")"

# subid is exported by the splice-point subshell in participant_job.sh;
# sesid only at session level, so its presence encodes the processing level.
# shellcheck disable=SC2154
ZIP_ID="${subid}${sesid:+_${sesid}}"
ZIP_NAME="${ZIP_ID}_${name}.zip"

# Zip real file content, not annex symlinks:
datalad unlock "${path}"

# cd into the parent so the archive contains the folder at its top level;
# OLDPWD (the dataset root) is where the archive lands.
datalad run \
	--explicit \
	--output "${ZIP_NAME}" \
	-m "Zip ${path} for ${ZIP_ID}" \
	-- \
	"cd ${zip_dir} && 7z a \"\${OLDPWD}/${ZIP_NAME}\" ${zip_folder}"

# `datalad run --explicit` does not track deletions, so the granular outputs
# are removed in a separate commit (workaround for datalad/datalad#7822,
# since fixed upstream).
# TODO research which datalad version shipped the datalad/datalad#7822 fix;
# once babs's minimum supported datalad is at or above it, fold this removal
# into the datalad run above and drop this step.
git rm -rf -q --sparse "${path}"
git commit -m "Remove ${path} for ${ZIP_ID} (zipped)"
