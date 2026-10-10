# Contributing to BABS

## Quick Reference

Common commands from the repository configuration and developer docs:

```bash
# Install this checkout for development
python -m pip install -e .

# Style and formatting
ruff check .
ruff format --check .
ruff check --fix
ruff format

# Spelling and shell scripts
codespell .
git grep -l -E '^#!/bin/(ba|)sh' | grep -v jinja | xargs shellcheck -x

# Docker-backed tests used by the developer docs
bash tests/pytest_in_docker.sh
bash tests/pytest_in_docker.sh -sv tests/test_status.py
bash tests/e2e_in_docker.sh
E2E_DIR=/path/to/output bash tests/e2e_in_docker.sh

# Package build checks
python -m build
python -m twine check dist/*
```

## Repository Layout

- `babs/` contains the Python package.
- `babs/cli.py` defines the `babs` command and subcommands with `argparse`.
- `babs/bootstrap.py`, `babs/check_setup.py`, `babs/interaction.py`,
  `babs/merge.py`, and `babs/update.py` implement the main user workflows.
- `babs/base.py` contains shared BABS project behavior.
- `babs/container.py`, `babs/input_dataset.py`, `babs/input_datasets.py`,
  `babs/scheduler.py`, `babs/status.py`, `babs/system.py`, and `babs/utils.py`
  support datasets, containers, scheduler interaction, status accounting, and
  shared utilities.
- `babs/templates/` contains Jinja templates for generated YAML and shell
  scripts.
- `babs/bids_skeletons/` and `babs/dict_cluster_systems.yaml` contain packaged
  YAML resources used by the code.
- `tests/` contains pytest tests, Docker-backed test scripts, and SLURM E2E
  fixtures under `tests/e2e-slurm/`.
- `docs/` contains the Sphinx documentation. `docs/index.rst` includes
  `README.rst`, so README changes affect the documentation landing page.
- `notebooks/` contains example container configuration YAML files and example
  subject/session CSVs.
- `design/` contains design notes for implementation details and architecture
  changes.
- `docker/`, `Dockerfile`, and `DockerfileSLURM` contain container build inputs
  used for BABS test/development images.
- `.github/` contains GitHub Actions workflows, issue templates, and release
  note category configuration.
- `.circleci/config.yml` contains the CircleCI test and release pipeline.

## Development Environment

BABS minimum supported Python version is defined by `project.requires-python`
in `pyproject.toml`. CI and environment files pin specific Python versions:

- `tox.ini` `envlist` defines the tox test matrix versions.
- `.github/workflows/ruff.yml` defines the Python version for Ruff checks.
- `.readthedocs.yaml` defines the Python version for docs builds.
- `docker/environment.yml` defines the Docker image environment Python version.
- `environment_hpc.yml` defines the HPC environment Python version.

For local development from a checkout, install BABS in editable mode:

```bash
python -m pip install -e .
```

Add only the extras you need:

```bash
python -m pip install -e '.[tests]'  # pytest, coverage, xdist, datalad-osf
python -m pip install -e '.[doc]'    # Sphinx documentation dependencies
python -m pip install -e '.[all]'    # dev, docs, maint, and tests extras
```

The user/HPC installation path is documented in `docs/installation.rst` and
uses `environment_hpc.yml` with `mamba`, `conda`, or `micromamba`:

```bash
mamba env create -f environment_hpc.yml
mamba activate babs
```

That environment installs `babs` from PyPI (see `environment_hpc.yml` for the
exact specifier). For contribution work on this checkout, use editable
installation after activating the environment.

The installation docs also state that `datalad-osf` credentials are needed when
running pytest or using OSF-hosted input DataLad datasets:

```bash
datalad osf-credentials --method userpassword
```

## System Dependencies

BABS is designed for SLURM HPC systems and uses DataLad, git-annex, and
Singularity/Apptainer. The installation docs list commands contributors and
users can run to confirm versions:

```bash
datalad --version
git --version
git-annex version
datalad containers-add --version
datalad osf-credentials --version
pip show babs
```

## Command Line Entry Points

- `babs init`
- `babs check-setup`
- `babs sync-code`
- `babs submit`
- `babs status`
- `babs merge`
- `babs update-input-data`

When changing command line behavior, update the relevant parser in `babs/cli.py`,
the implementation module, tests, and the matching documentation page under
`docs/`.

## Style, Formatting, and Linting

Ruff is the configured linter and formatter. Its settings live in
`pyproject.toml`.

Run the same checks as the GitHub Actions Ruff workflow:

```bash
ruff check .
ruff format --check .
```

To apply the configured auto-fixes:

```bash
ruff check --fix
ruff format
```

Spelling is checked with codespell. `.codespellrc` skips `versioneer.py`,
`_version.py`, `.git`, and HTML files:

```bash
codespell .
```

Shell scripts are checked in CI with:

```bash
git grep -l -E '^#!/bin/(ba|)sh' | grep -v jinja | xargs shellcheck -x
```

Jinja shell templates are intentionally excluded from the shellcheck command in
the GitHub Actions workflow.

## Tests

The developer testing docs describe two levels of testing:

1. pytest, run manually or automatically in CI;
2. manual tests on an HPC cluster with SLURM for scheduler workflows.

The easiest way to run pytest is the Docker-backed script from the
repository root:

```bash
bash tests/pytest_in_docker.sh
```

Pass pytest arguments through the same script to run a focused test:

```bash
bash tests/pytest_in_docker.sh -sv tests/test_status.py
```

The script runs a privileged `pennlinc/slurm-docker-ci` container (tag pinned
in `tests/pytest_in_docker.sh`), mounts
the checkout at `/babs`, installs `.[tests]`, and runs pytest with coverage for
`babs`.

The end-to-end Docker walkthrough test is:

```bash
bash tests/e2e_in_docker.sh
```

By default, E2E artifacts are written under a temporary `/tmp/babs-e2e-*`
directory. To keep them somewhere specific:

```bash
E2E_DIR=/path/to/output bash tests/e2e_in_docker.sh
```

Pytest does not fully cover `babs submit`,
`babs status`, and `babs merge`, and therefore call for manual SLURM testing.
Tests in this checkout include status, merge, and workflow coverage, so
interpret the manual SLURM guidance as applying especially to changes that
interact with real
scheduler state, job submission, job auditing, result branches, or large
datasets.

A CLI-aligned manual checklist includes:

- `babs check-setup --job-test` to inspect summarized setup information;
- `babs submit`;
- `babs submit --count 5`;
- `babs submit --select sub-01`;
- `babs submit --inclusion-file path/to/inclusion.csv`;
- `babs submit --skip-running-jobs`;
- `babs status`;
- `babs status --wait`;
- `babs status --wait --wait-interval 60`;
- `babs merge`.

## tox

`tox.ini` defines these environment groups:

- default test matrix: `py3{10,11,12}-latest`, `py310-min`, and
  `py3{10,11,12}-pre`;
- `style`;
- `style-fix`;
- `spellcheck`;
- `build` and `build-strict`;
- maintainer-only: `publish` (see `Maintainer Workflows`).

Example commands:

```bash
tox -e style
tox -e style-fix
tox -e spellcheck
tox -e build
```

The test command is configured in `tox.ini` under `[testenv]commands`; check
that file for the configured pytest flags and defaults.

`tox.ini` sets `extras = test`, while `pyproject.toml` defines
`tests`. If tox test environments fail during installation, check this mismatch.

## Documentation

The documentation is built with Sphinx. Configuration is in `docs/conf.py`, and
Read the Docs uses `.readthedocs.yaml` with `fail_on_warning: true`.

Install documentation dependencies:

```bash
python -m pip install -e '.[doc]'
```

Build the docs with the same source/config layout used by Read the Docs:

```bash
python -m sphinx -W -b html docs docs/build/html
```

`docs/Makefile` exists, but it sets the Sphinx source directory to
`source`, while this repository keeps `index.rst` and `conf.py` directly under
`docs/`. Use the direct Sphinx command above unless the Makefile is updated.

When changing the CLI, check pages under `docs/babs-*.rst` and `docs/cli.rst`.
Several CLI pages use `sphinx-argparse` and import parser definitions from
`babs/cli.py`, so parser changes can affect doc builds.

## Continuous Integration

GitHub Actions workflows:

- `.github/workflows/ruff.yml` runs `ruff check .` and
  `ruff format --check .` on push and pull request.
- `.github/workflows/codespell.yml` runs codespell on push and pull request.
- `.github/workflows/shellcheck.yml` installs shellcheck and checks shell
  scripts detected by `git grep`, excluding Jinja templates.
- `.github/workflows/e2e-slurm.yml` is configured with `push.branches-ignore:
  '**'`, so it does not run on pushes unless that workflow is changed.

CircleCI workflows:

- `pytest` runs in a `pennlinc/slurm-docker-ci` image (tag pinned in
  `.circleci/config.yml`), installs `.[tests]`, and runs pytest with xdist,
  timeout, JUnit output, coverage XML, and Codecov upload.
- `e2e-slurm` runs `tests/e2e_in_docker.sh`, then stores selected analysis
  artifacts.
- maintainer deployment jobs are documented in `Maintainer Workflows`.

## Docker and HPC Test Images

The repository includes:

- `Dockerfile`, with its base image pinned in the file;
- `DockerfileSLURM`, with its base image pinned in the file;
- `docker/environment.yml`, used by those Dockerfiles;
- `docker/docker-entrypoint.sh`, which simply executes the passed command;
- `environment_hpc.yml`, used by the user-facing HPC installation docs.

The test scripts use the published `pennlinc/slurm-docker-ci` image (tag pinned
in the scripts) rather than building these Dockerfiles as part of the script.

The root `Makefile` has targets named `install`, `setup-user`, and `e2e` that
refer to `tests/e2e-slurm/install-babs.sh`, `tests/e2e-slurm/setup-user.sh`,
and `tests/e2e-slurm/main.sh`. If those scripts are absent in your checkout,
those targets will fail. The `clean` target does exist and removes the `slurm`
container and `.testdata`.

## Examples and Configuration Files

`notebooks/README.md` documents the example container configuration YAML files.
The naming convention there is:

```text
eg_<bidsapp-0-0-0>_<task>.yaml
```

The examples are intended as starting points and often require cluster-specific
customization. When changing config parsing or generated scripts, update
relevant examples under `notebooks/` and documentation under `docs/`.

## Issues and Pull Requests

Contributors should open pull requests against
`https://github.com/PennLINC/babs` and try to pass CircleCI, spelling checks,
and docs builds.

Issue templates exist for:

- bug reports, labeled `bug`;
- feature requests, labeled `enhancement`.

Bug reports ask for:

```bash
pip show babs
datalad --version
git --version
git-annex version
datalad containers-add --version
singularity --version
babs check-setup
```

## Changelog

`docs/whats_new.md` is the project changelog shown in the docs. Entries group
changes under headings such as breaking changes, new features, bug fixes, and
other changes.

## Governance and Project Metadata

The repository includes:

- `LICENSE`;
- `CITATION.cff`;
- `README.rst`;
- GitHub issue templates.

## Before Submitting a Change

Use the smallest relevant check set for the change:

- Python behavior: run the focused pytest command through
  `tests/pytest_in_docker.sh`.
- Scheduler, submission, status, or merge behavior: run relevant Docker E2E
  tests and consider the manual SLURM checklist in
  `docs/developer_how_to_test.rst`.
- Python style: run `ruff check .` and `ruff format --check .`.
- Shell scripts: run the shellcheck command used by GitHub Actions.
- Documentation: build with `python -m sphinx -W -b html docs docs/build/html`.
- Package metadata or included files: run `python -m build` and
  `python -m twine check dist/*`.

## Maintainer Workflows

This section is maintainer-facing.

### Packaging and Build

The package uses Hatchling with `hatch-vcs` for dynamic versioning. Relevant
configuration is in `pyproject.toml`:

- build backend: `hatchling.build`;
- dynamic version source: VCS;
- generated version file: `babs/_version.py`;
- wheel package: `babs`;
- source distribution excludes `.git_archival.txt`;
- wheel excludes `babs/tests/data`.

`MANIFEST.in` includes the license, package YAML files, Jinja templates, and
`babs/_version.py`. If you add packaged YAML or templates under `babs/`, keep
the manifest and Hatch build configuration in sync.

Build and validate distributions:

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

The equivalent tox environment is:

```bash
tox -e build
```

### Release and Publish

- `tox -e publish` and the CircleCI release path upload distributions to PyPI
  with Twine.
- CircleCI `deployable` runs on `main` after `pytest` and `e2e-slurm` succeed.
- CircleCI `deploy_pypi` runs on tags after `deployable`, builds the package,
  and uploads `dist/babs*` to PyPI using `PYPI_PASS`.
- `.github/release.yml` configures GitHub release note categories from labels:
  `breaking-change`, `enhancement`, `deprecation`, `bug`, and wildcard
  `*` for other changes; `ignore-for-release` is excluded.
- Repository tags are used for release publication triggers in CI.
