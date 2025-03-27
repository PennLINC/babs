# What's New

## Version 0.3.0

Critical bugfix for 0.2.0 and adds the ability to add small files to the BABS project
so they can be tracked by git and accessed during the BIDS app run.

## What's Changed
### Other Changes
* Fix SLURM JOB_ID bug by @mattcieslak in https://github.com/PennLINC/babs/pull/267
* Add imported_files section to config files by @mattcieslak in https://github.com/PennLINC/babs/pull/266
* Update docs to reflect changes in 0.3 by @mattcieslak in https://github.com/PennLINC/babs/pull/268


**Full Changelog**: https://github.com/PennLINC/babs/compare/0.2.0...pre-0.3.0


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