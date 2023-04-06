
# The following should be pasted into the merge_outputs.sh script
datalad clone ${outputsource} merge_ds
cd merge_ds
NBRANCHES=$(git branch -a | grep job- | sort | wc -l)  # no need to sort; then count line
echo "Found $NBRANCHES branches to merge"

# find the default branch's name: master or main: - added by Chenying
git_default_branchname=$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')
# ^^ `origin` is listed in `git remote` in `merge_ds`
echo "git default branch's name: ${git_default_branchname}"

# get git commit SHASUM before merging:
gitref=$(git show-ref ${git_default_branchname} | cut -d ' ' -f1 | head -n 1)    # changed to 'main'

# check if each branch is different from previous one:
#   query all branches for the most recent commit and check if it is identical.
#   Write all branch identifiers for jobs without outputs into a file.
#   `cut -d` is just to cut into strings
#   here `x` in  `x"$()" = x"$()"` is just to avoid error if the two strings to be compared are both empty
for i in $(git branch -a | grep job- | sort); do [ x"$(git show-ref $i \
  | cut -d ' ' -f1)" = x"${gitref}" ] && \
  echo $i; done | tee code/noresults.txt | wc -l
# save `noresults.txt` as a csv or so, and if not empty, throw out a warning of that

for i in $(git branch -a | grep job- | sort); \
  do [ x"$(git show-ref $i  \
     | cut -d ' ' -f1)" != x"${gitref}" ] && \
     echo $i; \
done | tee code/has_results.txt   # this is saved to `merge_ds/analysis/code/`

mkdir -p code/merge_batches   # this line can be deleted
num_branches=$(wc -l < code/has_results.txt)
CHUNKSIZE=5000   # default should be 2000, not 5000; smaller chunk is, more merging commits which is fine!
set +e
num_chunks=$(expr ${num_branches} / ${CHUNKSIZE})
if [[ $num_chunks == 0 ]]; then
    num_chunks=1
fi
set -e
for chunknum in $(seq 1 $num_chunks)
do
    # NOTE: we don't need `startnum` or `endnum`
    startnum=$(expr $(expr ${chunknum} - 1) \* ${CHUNKSIZE} + 1)
    endnum=$(expr ${chunknum} \* ${CHUNKSIZE})
    batch_file=code/merge_branches_$(printf %04d ${chunknum}).txt
    [[ ${num_branches} -lt ${endnum} ]] && endnum=${num_branches}
    branches=$(sed -n "${startnum},${endnum}p;$(expr ${endnum} + 1)q" code/has_results.txt)
    echo ${branches} > ${batch_file}
    # what's in `${batch_file}`: job branches names concat-ed with space:
    # `remotes/origin/job-2187000-sub-01-ses-A remotes/origin/job-2187001-sub-01-ses-B ...`

    # below is the only command necessary:
    git merge -m "merge results batch ${chunknum}/${num_chunks}" $(cat ${batch_file})

done

# If i want to test it on HBN BABS project: 
#   just not to run commands from here including `git push`

# Push the merge back
git push

# Get the file availability info - important!
#   `git annex fsck` = file system check
#   We've done the git merge of the symlinks of the files,
#   now we need to match the symlinks with the data content in `output-storage`:
#   `--fast`: just use the existing MD5, not to re-create a new one
git annex fsck --fast -f output-storage

# Double check: there should not be file content that's not in `output-storage`:
#   This should not print anything - never has this error yet
MISSING=$(git annex find --not --in output-storage)

# translate into python: check if `$MISSING` is empty:
if [[ ! -z "$MISSING" ]]
then
    echo Unable to find data for $MISSING
    exit 1
fi

# stop tracking clone `merge_ds`, i.e., not to get data from this `merge_ds` sibling
git annex dead here

# `datalad push` includes:
#   pushing to `git` branch in output RIA: has done with `git push`;
#   pushing to `git-annex` branch in output RIA: hasn't done after `git annex fsck`
#   `--data nothing`: don't transfer data from this local annex `merge_ds`
datalad push --data nothing
echo SUCCESS
