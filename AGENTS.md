# AGENTS.md

This file gives AI coding agents the extra operating rules for this repository.
It is not a replacement for the contributor guide.

## Mandatory First Step

Read `CONTRIBUTING.md` before making code changes, commits, or pull requests.
That file is the source of truth for repository layout, setup, commands, CI,
testing, docs, release evidence, and undocumented conventions.

Do not guess project conventions. If a workflow is not documented in
`CONTRIBUTING.md` or repository files, say so instead of inventing one.

## Work From Local Evidence

Before changing an area, inspect the current source, tests, and docs that own
that behavior. In particular:

- CLI changes usually involve `babs/cli.py`, implementation modules, tests, and
  matching `docs/babs-*.rst` pages.
- Scheduler, status, submit, and merge changes require extra care because BABS
  is built around DataLad, git-annex, Singularity/Apptainer, and SLURM.
- Generated script or YAML changes should be checked against `babs/templates/`,
  packaged YAML files, examples, and relevant tests.
- Documentation changes should account for `README.rst` being included by
  `docs/index.rst`.

## Agent Change Discipline

- Check the worktree before editing and do not overwrite unrelated user changes.
- Keep edits scoped to the requested behavior.
- Update tests and documentation when behavior, CLI flags, generated outputs, or
  example configuration semantics change.
- Use the tools and commands documented in `CONTRIBUTING.md`; do not substitute
  unrelated workflows.
- If Docker, SLURM, Singularity/Apptainer, DataLad credentials, or other
  external requirements are unavailable, report the limitation clearly.
- Do not claim tests, linting, docs builds, package builds, or manual SLURM
  checks passed unless they were actually run.

## Do Not Invent

Do not infer or invent project conventions that are not explicitly documented in
`CONTRIBUTING.md` or present in repository files. This includes branch naming,
commit/PR format, ownership, release/changelog process, scheduler setup, or
tooling stacks.

If a convention is missing, state that it is undocumented and ask for guidance
instead of guessing.
