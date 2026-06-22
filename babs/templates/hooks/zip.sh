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
# OLDPWD (the dataset root, where `bash -c` starts) is where the archive
# lands. Two subtleties:
#  - the command runs via `bash -c` because datalad execs the words after
#    `--` directly (no shell), so the `&&` needs an explicit shell;
#  - the braces in ${{OLDPWD}} are doubled to escape datalad run's own
#    {placeholder} syntax -- datalad collapses them to ${OLDPWD}, which the
#    job's shell then expands (it stays literal in the run record, so
#    `datalad rerun` re-resolves it -- no absolute path is baked in).
datalad run \
	--explicit \
	--output "${ZIP_NAME}" \
	-m "Zip ${path} for ${ZIP_ID}" \
	-- \
	bash -c "cd ${zip_dir} && 7z a \"\${{OLDPWD}}/${ZIP_NAME}\" ${zip_folder}"

# `datalad run --explicit` does not track deletions, so the granular outputs
# are removed in a separate commit (workaround for datalad/datalad#7822,
# fixed in datalad 1.3.4).
# TODO babs currently pins datalad >= 0.17.2, so the #7822 fix is not
# guaranteed at runtime. Once babs raises its minimum supported datalad to
# >= 1.3.4, fold this removal into the datalad run above and drop this step.
git rm -rf -q --sparse "${path}"
git commit -m "Remove ${path} for ${ZIP_ID} (zipped)"
