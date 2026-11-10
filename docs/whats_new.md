# What's New

## Version 0.6.0

This release changes how jobs check out data and containers.
Jobs now clone with `git sparse-checkout`, stage BIDS-inherited metadata automatically,
and get the container image through a `git worktree`.
`babs submit` now fetches container images from a local container dataset before trying the network.
`babs init` supports a BIDS-study layout (set `analysis_path: "."` in the config yaml file),
resolves container images from their datalad registration so ReproNim/containers works out of the box,
and writes a BIDS-friendly `.gitattributes`.
New options: `babs init --throttle`, `--shared-group` and `--no-ignore`; `babs status --wait` and `--json`.
`babs-unzip` has been removed; use `unzip` instead.

### What's Changed
#### 🛠 Breaking Changes
* Remove `babs-unzip` by @tien-tong in https://github.com/PennLINC/babs/pull/400
#### 🎉 Exciting New Features
* Add `--throttle` option to `babs init` for SLURM array job throttling by @tien-tong in https://github.com/PennLINC/babs/pull/321
* Allow submission when all running jobs are in CG state by @tien-tong in https://github.com/PennLINC/babs/pull/332
* Allow resubmission of failed, non-running jobs when other jobs are running by @tien-tong in https://github.com/PennLINC/babs/pull/335
* Use `git sparse-checkout` in `participant_job` for more efficient dataset cloning by @tien-tong in https://github.com/PennLINC/babs/pull/337
* Add --wait flag to babs status by @asmacdo in https://github.com/PennLINC/babs/pull/354
* Add `babs init --shared-group <GROUP>` by @tien-tong in https://github.com/PennLINC/babs/pull/368
* Adding an option to fit BIDS-study layout (updated) by @djarecka in https://github.com/PennLINC/babs/pull/369
* Get container before `babs submit` if missing by @tien-tong in https://github.com/PennLINC/babs/pull/380
* Stage BIDS-inherited metadata for every job; common_paths for explicit extras by @asmacdo in https://github.com/PennLINC/babs/pull/385
* Add `babs init --no-ignore` to make logs/ gitignore opt-out by @asmacdo in https://github.com/PennLINC/babs/pull/386
* Add `babs status --json` for machine-readable status by @asmacdo in https://github.com/PennLINC/babs/pull/389
* Write a BIDS-friendly .gitattributes at babs init by @asmacdo in https://github.com/PennLINC/babs/pull/393
* Resolve container image paths from datalad by @asmacdo in https://github.com/PennLINC/babs/pull/399
* collect duct logs/resource stats for singularity runs by @asmacdo in https://github.com/PennLINC/babs/pull/413
* Use `git worktree` to get containers by @tien-tong in https://github.com/PennLINC/babs/pull/418
#### 🐛 Bug Fixes
* Fix `babs merge` error when deleting merge_ds by @tien-tong in https://github.com/PennLINC/babs/pull/322
* Use conda to install niworkflows and scipy instead of pip by @tsalo in https://github.com/PennLINC/babs/pull/340
* Fix `babs init --list_sub_file` by @tien-tong in https://github.com/PennLINC/babs/pull/345
* Fix writable check for NFS/ACL filesystems by @asmacdo in https://github.com/PennLINC/babs/pull/348
* Fix `babs merge` by @tien-tong in https://github.com/PennLINC/babs/pull/351
* Do specify which branch to push by @yarikoptic in https://github.com/PennLINC/babs/pull/352
* Fix `containers` set up in `participant_job.sh.jinja2` by @tien-tong in https://github.com/PennLINC/babs/pull/363
* allow full BIDS-acceptable chars as derivative names by @asmacdo in https://github.com/PennLINC/babs/pull/394
* Drop `session` from the fmap BIDS filter so session-level *prep runs can start by @asmacdo in https://github.com/PennLINC/babs/pull/395
* Drop the `numpy < 2.0` pin by @asmacdo in https://github.com/PennLINC/babs/pull/405
* check-setup: validate input datasets at their configured path_in_babs by @yibeichan in https://github.com/PennLINC/babs/pull/407
#### Other Changes
* Remove mentions of babs submit --all by @tsalo in https://github.com/PennLINC/babs/pull/341
* Fix test scripts to work on any machine by @asmacdo in https://github.com/PennLINC/babs/pull/346
* babs-status: replace pandas with dataclasses by @asmacdo in https://github.com/PennLINC/babs/pull/359
* Allow running individual tests with custom options by @asmacdo in https://github.com/PennLINC/babs/pull/360
* Update codecov by @tien-tong in https://github.com/PennLINC/babs/pull/391
* Pin ruff 0.16.0 by @tien-tong in https://github.com/PennLINC/babs/pull/398
* docs: ReproNim/containers as the container dataset (follow-up to #399) by @asmacdo in https://github.com/PennLINC/babs/pull/414
* Add instruction to get containers

**Full Changelog**: https://github.com/PennLINC/babs/compare/0.5.4...0.6.0

## Version 0.5.4

### What's Changed
#### 🎉 Exciting New Features
* Add BABS chaining to run 2 BIDS apps in a pipeline by @tien-tong in https://github.com/PennLINC/babs/pull/316
#### 🐛 Bug Fixes
* Fix `babs submit --select` argument parsing by @singlesp in https://github.com/PennLINC/babs/pull/312
#### Other Changes
* Update installation.rst by @yibeichan in https://github.com/PennLINC/babs/pull/309
* Update eg_aslprep-0-7-5.yaml by @B-Sevchik in https://github.com/PennLINC/babs/pull/304
* Fix coverage by @tien-tong in https://github.com/PennLINC/babs/pull/318
* Edit nordic-fmriprep pipeline

**Full Changelog**: https://github.com/PennLINC/babs/compare/0.5.3...0.5.4

## Version 0.5.3

* Fix `subject_selection_flag` by @tientong98 in https://github.com/PennLINC/babs/pull/308
* Add freesurfer-post support by @tientong98 in https://github.com/PennLINC/babs/pull/306
* Update documentation and example configurations

## Version 0.5.2

* Fix `babs sync-code` by @smeisler in https://github.com/PennLINC/babs/pull/299
* Fix jinja space rendering issue for `participant_job.sh` by @tientong98 in https://github.com/PennLINC/babs/pull/301


## Version 0.5.1

*  Fix sync-code by @smeisler in  https://github.com/PennLINC/babs/pull/297


## Version 0.5.0

This version got test coverage over 80% and adds the `update-input-data` action. 
It adds back the `sync-code` function too.

* Add more CI tests by @mattcieslak in https://github.com/PennLINC/babs/pull/292
* add back sync-code by @mattcieslak in https://github.com/PennLINC/babs/pull/293
* add babs update-input-data by @mattcieslak in https://github.com/PennLINC/babs/pull/294



## Version 0.4.0

Arguments and default behavior for `babs submit` and `babs status` have changed.
The specification of input datasets all happens in the config yaml file now (the `--datasets` option is removed).
See the walkthrough example for an up-to-date example of BABS in action.

### What's Changed
#### 🛠 Breaking Changes
* Fix walkthrough test by @mattcieslak in https://github.com/PennLINC/babs/pull/286
#### 🎉 Exciting New Features
* Add codecov again by @mattcieslak in https://github.com/PennLINC/babs/pull/289
#### 🐛 Bug Fixes
* update e2e to use new CLIs by @mattcieslak in https://github.com/PennLINC/babs/pull/288
#### Other Changes
* Make InputDataset handle individual input dataset checking/querying by @mattcieslak in https://github.com/PennLINC/babs/pull/277
* Refactor babs init to use the InputDataset class by @mattcieslak in https://github.com/PennLINC/babs/pull/284
* RF the slurm-interacting code by @mattcieslak in https://github.com/PennLINC/babs/pull/287
* Test BABS on upenn cluster + update docs with simbids examples by @mattcieslak in https://github.com/PennLINC/babs/pull/290
* Subclass BABS for different interactions by @mattcieslak in https://github.com/PennLINC/babs/pull/291

**Full Changelog**: https://github.com/PennLINC/babs/compare/0.3.0...0.4.0

## Version 0.3.0

Critical bugfix for 0.2.0 and adds the ability to add small files to the BABS project
so they can be tracked by git and accessed during the BIDS app run.

### What's Changed
#### Other Changes
* Fix SLURM JOB_ID bug by @mattcieslak in https://github.com/PennLINC/babs/pull/267
* Add imported_files section to config files by @mattcieslak in https://github.com/PennLINC/babs/pull/266
* Update docs to reflect changes in 0.3 by @mattcieslak in https://github.com/PennLINC/babs/pull/268


**Full Changelog**: https://github.com/PennLINC/babs/compare/0.2.0...0.3.0


## Version 0.2.0

### What's Changed

This release is the result of a major refactor of the codebase. The most important changes are that
`babs` is a standalone command and the `babs-*` commands are now subcommands of `babs`. Please
switch and scripts that use `babs-<command>` to use `babs <command>` instead. There are also
a number of arguments that have been renamed and/or removed. Please refer to the `--help` output
for the latest information.

The config yaml format has also changed. See examples of valid configurations in the `notebooks`
directory.

#### Breaking Changes
* Change `babs init` parameter `--input` to `--datasets` by @tsalo in [#230](https://github.com/PennLINC/babs/pull/230)
* Convert `--project-root` to a positional argument by @tsalo in [#235](https://github.com/PennLINC/babs/pull/235)
* Change `--container-config-yaml-file` to `--container-config` by @tsalo in [#243](https://github.com/PennLINC/babs/pull/243)
* Change `--type-system` parameter to `--queue` by @tsalo in [#234](https://github.com/PennLINC/babs/pull/234)
* Remove `--job-account` argument by @tsalo in [#251](https://github.com/PennLINC/babs/pull/251)
* Change `--type-session` parameter to `--processing-level` by @tsalo in [#233](https://github.com/PennLINC/babs/pull/233)

#### Exciting New Features
* Convert CLIs to subcommands by @tsalo in [#210](https://github.com/PennLINC/babs/pull/210)
* Add a yml file for creating a mamba environment on an hpc by @mattcieslak in [#217](https://github.com/PennLINC/babs/pull/217)
* Use jinja templates for creating scripts/yamls by @mattcieslak in [#231](https://github.com/PennLINC/babs/pull/231)
* Add `babs sync-code` by @tientong98 in [#236](https://github.com/PennLINC/babs/pull/236)
* Add section for adding singularity args by @mattcieslak in [#250](https://github.com/PennLINC/babs/pull/250)

#### Bug Fixes
* [FIX] Output RIA path not found error by @tientong98 in [#178](https://github.com/PennLINC/babs/pull/178)
* Replace `pkg_resources` with `importlib.metadata` by @tientong98 in [#211](https://github.com/PennLINC/babs/pull/211)

#### Other Changes
* add backoff strategy for job polling by @asmacdo in [#165](https://github.com/PennLINC/babs/pull/165)
* Introducing e2e slurm tests by @asmacdo in [#169](https://github.com/PennLINC/babs/pull/169)
* [DOCS] Add examples of --list_sub_file/--list-sub-file by @tientong98 in [#181](https://github.com/PennLINC/babs/pull/181)
* [DOCS] Add examples of --list_sub_file/--list-sub-file - Fixed rendering issues by @tientong98 in [#183](https://github.com/PennLINC/babs/pull/183)
* update installation instructions with method to provide OSF credentials by @B-Sevchik in [#186](https://github.com/PennLINC/babs/pull/186)
* Add participant selection flag to `babs-init` config yaml file by @tientong98 in [#187](https://github.com/PennLINC/babs/pull/187)
* Support SLURM array jobs in `babs-submit` by @tientong98 in [#188](https://github.com/PennLINC/babs/pull/188)
* Add a new docker build and fix CI tests by @mattcieslak in [#189](https://github.com/PennLINC/babs/pull/189)
* Restyle with ruff by @mattcieslak in [#190](https://github.com/PennLINC/babs/pull/190)
* Add back containerized slurm to the CI by @mattcieslak in [#191](https://github.com/PennLINC/babs/pull/191)
* Fix shellcheck by @mattcieslak in [#198](https://github.com/PennLINC/babs/pull/198)
* More e2e fixes by @mattcieslak in [#201](https://github.com/PennLINC/babs/pull/201)
* Add default value for project_root by @smeisler in [#194](https://github.com/PennLINC/babs/pull/194)
* containall, writable-tmpfs, absolute paths by @smeisler in [#197](https://github.com/PennLINC/babs/pull/197)
* Adding --participant-label as the default subject selection flag if $SUBJECT_SELECTION_FLAG wasn't specified in YAML by @tientong98 in [#202](https://github.com/PennLINC/babs/pull/202)
* Do shellcheck all the shell scripts by @yarikoptic in [#203](https://github.com/PennLINC/babs/pull/203)
* Fix RTD build by @mattcieslak in [#216](https://github.com/PennLINC/babs/pull/216)
* Fix style issues in documentation by @tsalo in [#214](https://github.com/PennLINC/babs/pull/214)
* Make temporary directory in `babs-submit` by @smeisler in [#207](https://github.com/PennLINC/babs/pull/207)
* change how subject ID and session ID are parsed from the jobs CSV by @mattcieslak in [#227](https://github.com/PennLINC/babs/pull/227)
* Add ${TEMPLATEFLOW_HOME} in singularity run cmd  by @tientong98 in [#225](https://github.com/PennLINC/babs/pull/225)
* Add user and developer argument groups to babs merge arg parser by @singlesp in [#239](https://github.com/PennLINC/babs/pull/239)
* Update example config yamls by @singlesp in [#232](https://github.com/PennLINC/babs/pull/232)
* Add customized text to aslprep yaml by @singlesp in [#246](https://github.com/PennLINC/babs/pull/246)
* don't shellcheck jinja templates by @mattcieslak in [#245](https://github.com/PennLINC/babs/pull/245)
* Pass CI tests with jinja templates by @mattcieslak in [#249](https://github.com/PennLINC/babs/pull/249)
* Add CITATION.cff and update citations in README by @tsalo in [#252](https://github.com/PennLINC/babs/pull/252)
* Remove commented-out code by @tsalo in [#253](https://github.com/PennLINC/babs/pull/253)
* Make a separate system module by @singlesp in [#256](https://github.com/PennLINC/babs/pull/256)
* Move InputDatasets class into dataset module by @tsalo in [#258](https://github.com/PennLINC/babs/pull/258)
* Move Container and InputDatasets into new files by @mattcieslak in [#259](https://github.com/PennLINC/babs/pull/259)
* Remove unused functions and variables flagged by vulture by @tsalo in [#260](https://github.com/PennLINC/babs/pull/260)
* RF: Add easily-testable script creation by @mattcieslak in [#262](https://github.com/PennLINC/babs/pull/262)
* Add tests for function in utils module by @tsalo in [#261](https://github.com/PennLINC/babs/pull/261)

#### New Contributors
* @tientong98 made their first contribution in [#178](https://github.com/PennLINC/babs/pull/178)
* @B-Sevchik made their first contribution in [#186](https://github.com/PennLINC/babs/pull/186)
* @smeisler made their first contribution in [#194](https://github.com/PennLINC/babs/pull/194)
* @singlesp made their first contribution in [#239](https://github.com/PennLINC/babs/pull/239)

**Full Changelog**: [https://github.com/PennLINC/babs/compare/0.0.8...0.2.0](https://github.com/PennLINC/babs/compare/0.0.8...0.2.0)


## Version 0.1.0

### What's Changed

#### Exciting New Features
* Convert CLIs to subcommands by @tsalo in [#210](https://github.com/PennLINC/babs/pull/210)
* Add a yml file for creating a mamba environment on an hpc by @mattcieslak in [#217](https://github.com/PennLINC/babs/pull/217)

#### Bug Fixes
* [FIX] Output RIA path not found error by @tientong98 in [#178](https://github.com/PennLINC/babs/pull/178)
* Replace `pkg_resources` with `importlib.metadata` by @tientong98 in [#211](https://github.com/PennLINC/babs/pull/211)

#### Other Changes
* add backoff strategy for job polling by @asmacdo in [#165](https://github.com/PennLINC/babs/pull/165)
* Introducing e2e slurm tests by @asmacdo in [#169](https://github.com/PennLINC/babs/pull/169)
* [DOCS] Add examples of --list_sub_file/--list-sub-file by @tientong98 in [#181](https://github.com/PennLINC/babs/pull/181)
* [DOCS] Add examples of --list_sub_file/--list-sub-file - Fixed rendering issues by @tientong98 in [#183](https://github.com/PennLINC/babs/pull/183)
* update installation instructions with method to provide OSF credentials by @B-Sevchik in [#186](https://github.com/PennLINC/babs/pull/186)
* Add participant selection flag to `babs-init` config yaml file by @tientong98 in [#187](https://github.com/PennLINC/babs/pull/187)
* Support SLURM array jobs in `babs-submit` by @tientong98 in [#188](https://github.com/PennLINC/babs/pull/188)
* Add a new docker build and fix CI tests by @mattcieslak in [#189](https://github.com/PennLINC/babs/pull/189)
* Restyle with ruff by @mattcieslak in [#190](https://github.com/PennLINC/babs/pull/190)
* Add back containerized slurm to the CI by @mattcieslak in [#191](https://github.com/PennLINC/babs/pull/191)
* Fix shellcheck by @mattcieslak in [#198](https://github.com/PennLINC/babs/pull/198)
* More e2e fixes by @mattcieslak in [#201](https://github.com/PennLINC/babs/pull/201)
* Add default value for project_root by @smeisler in [#194](https://github.com/PennLINC/babs/pull/194)
* containall, writable-tmpfs, absolute paths by @smeisler in [#197](https://github.com/PennLINC/babs/pull/197)
* Adding --participant-label as the default subject selection flag if $SUBJECT_SELECTION_FLAG wasn't specified in YAML by @tientong98 in [#202](https://github.com/PennLINC/babs/pull/202)
* Do shellcheck all the shell scripts by @yarikoptic in [#203](https://github.com/PennLINC/babs/pull/203)
* Fix RTD build by @mattcieslak in [#216](https://github.com/PennLINC/babs/pull/216)
* Fix style issues in documentation by @tsalo in [#214](https://github.com/PennLINC/babs/pull/214)
* Make temporary directory in `babs-submit` by @smeisler in [#207](https://github.com/PennLINC/babs/pull/207)
* change how subject ID and session ID are parsed from the jobs CSV by @mattcieslak in [#227](https://github.com/PennLINC/babs/pull/227)
* Add ${TEMPLATEFLOW_HOME} in singularity run cmd  by @tientong98 in [#225](https://github.com/PennLINC/babs/pull/225)

#### New Contributors
* @tientong98 made their first contribution in [#178](https://github.com/PennLINC/babs/pull/178)
* @B-Sevchik made their first contribution in [#186](https://github.com/PennLINC/babs/pull/186)
* @mattcieslak made their first contribution in [#189](https://github.com/PennLINC/babs/pull/189)
* @smeisler made their first contribution in [#194](https://github.com/PennLINC/babs/pull/194)

**Full Changelog**: [https://github.com/PennLINC/babs/compare/0.0.8...0.1.0](https://github.com/PennLINC/babs/compare/0.0.8...0.1.0)
