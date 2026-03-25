# Design: `datalad containers-run` support in BABS

Issue: https://github.com/PennLINC/babs/issues/328

## Goal

Use `datalad containers-run` instead of direct `singularity run` for BIDS app
execution. This provides:

- **Dynamic container path discovery** — `datalad containers-list` reads the
  path from the container dataset's `.datalad/config`, so BABS works with any
  container dataset layout (not just the hardcoded
  `containers/.datalad/environments/{name}/image`).
- **Provenance tracking** — datalad records exactly which container ran and how.
- **Compatibility with repronim/containers** — which uses
  `images/bids/{name}.sif` instead of the default datalad-containers layout.

## How it works

### During `babs init`

1. Clone container dataset as subdataset of analysis (unchanged)
2. `datalad containers-list` discovers the image path in the container dataset
3. `datalad containers-add` registers the container at the analysis level with:
   - The discovered image path (relative to analysis)
   - A `call_fmt` built from the user's `singularity_args` config
4. `datalad get` fetches the container image content so it's available for job
   symlinks

### During job execution (`participant_job.sh`)

Three-step flow replaces the single `datalad run` that called a combined
singularity+zip script:

1. **`datalad containers-run`** — runs the BIDS app. Container is accessed via
   a PROJECT_ROOT symlink to the analysis dataset's fetched image.
2. **`datalad run`** — calls a zip-only script (no longer contains singularity
   invocation or output removal).
3. **`git rm --sparse`** — removes raw outputs. Needed because `datalad run
   --explicit` doesn't track file deletions. The `--sparse` flag is required
   because outputs are outside the sparse-checkout cone.

## Prior work

An initial proof-of-concept was developed before upstream's sparse-checkout PR
(#337) landed: https://github.com/asmacdo/babs/pull/6

That POC was validated end-to-end on a SLURM cluster (Discovery) with both
handmade container datasets and repronim/containers. Key findings from that
work:

- **Concurrent `datalad get` failures** — when multiple jobs run simultaneously,
  they all try to fetch the same container image. Git-annex uses transfer locks,
  causing all but one job to fail. This is a known git-annex bug:
  https://git-annex.branchable.com/bugs/concurrent_get_from_separate_clones_fails/
  The POC solved this with ephemeral clones for the containers subdataset.

- **Ephemeral clones work for containers but not inputs** — container images are
  resolved on the host before singularity launches, so annex symlinks outside
  `$PWD` are fine. Input data needs to be accessible inside the container with
  `--containall -B $PWD`, so symlinks outside `$PWD` break.

- **`datalad run --explicit` doesn't track deletions** — discovered and
  documented as an upstream issue. The workaround (separate `git rm` step) is
  carried forward into this implementation.

The current implementation was recreated from scratch on top of the
sparse-checkout changes, using the POC as reference. The PROJECT_ROOT symlink
approach (from upstream) combined with `datalad get` of the image during init
avoids the concurrent get problem entirely — jobs never call `datalad get` for
the container image, they just follow the symlink to the pre-fetched content.
Ephemeral clones remain a potential future alternative.

## Problems encountered

### `git sparse-checkout` interaction

The upstream sparse-checkout PR (#337) changed job clones to use
`--no-checkout` + `git sparse-checkout`. This caused two issues:

- **`.datalad/config` not checked out** — cone mode doesn't include
  dot-directories by default. Fixed by adding `.datalad` to the sparse-checkout
  set. Without it, `containers-run` fails with "No known containers."

- **`git rm` blocked by sparse-checkout** — outputs created by `containers-run`
  are outside the cone, so `git rm` refuses to touch them. Fixed with
  `git rm --sparse`.

### Container image access in job clones

Job clones don't have the container image content — they clone from input RIA
with `--no-checkout`. The existing PROJECT_ROOT symlink approach works: symlink
from the job clone's container path to the analysis dataset's copy. But this
requires the analysis dataset to have the actual content (not just an annex
pointer), so `datalad get` during init is necessary.

### `--containall` requires `--pwd $PWD` and `-B $PWD`

When users specify `--containall` in `singularity_args`, singularity disables
auto-binding of `$PWD` and sets the working directory to `$HOME` inside the
container. This breaks relative paths to inputs/outputs. The `call_fmt` built
during init always includes `-B $PWD --pwd $PWD` to handle this.

### datalad `{placeholder}` conflicts with shell `${variables}`

`datalad run` interprets `{name}` as a substitution placeholder, which
conflicts with shell variable expansion like `${subid}`. The POC initially
tried inlining zip commands in `datalad run` but this caused placeholder
conflicts. The solution is a separate zip script called by `datalad run`.

In the jinja2 templates, shell variables use `{%raw%}/${subid}{%endraw%}`
blocks to prevent jinja2 from interpreting them, and datalad sees the literal
`${subid}` which it passes through to bash.

### `datalad run --explicit` doesn't track deletions

When outputs are deleted inside a `datalad run --explicit` command, datalad
doesn't record the deletion — only additions/modifications are tracked. This is
why raw output removal is a separate `git rm` step outside of datalad run.

This was fixed upstream in https://github.com/datalad/datalad/pull/7823 but
we keep the `git rm` workaround to avoid requiring the latest datalad version.

## Open questions

### Pipeline support

Pipeline currently uses a separate code path (`_bootstrap_pipeline_scripts`)
that hardcodes container paths and generates a combined script
(`pipeline_zip.sh`) with direct `singularity run` calls per step.

Questions:
- Should pipeline be "a pipeline of 1"? i.e., unify single-app and pipeline
  into one code path where single-app is just a pipeline with one step.
- If not unified, pipeline needs the same `containers-list` / `containers-add`
  treatment per container step.
- Pipeline currently puts all singularity invocations in one script called by
  one `datalad run`. With `containers-run`, each step would be a separate
  `datalad containers-run` call — better provenance but different structure.

### Reusing `call_fmt` / `cmdexec` from container datasets

Currently we build `call_fmt` from the user's `singularity_args` config:
```
singularity run -B $PWD --pwd $PWD {user_args} {img} {cmd}
```

Some container datasets (like repronim/containers) already define `cmdexec` in
their `.datalad/config`. Should we reuse that instead of building our own?

Related: datalad-container's freeze script approach
(https://github.com/datalad/datalad-container/issues/287) could provide a
standardized way to handle this.

### Container image fetch during init

`datalad get` of the container image during `babs init` ensures the symlink
approach works at job time. But this makes init slow if the image isn't already
local (e.g., pulling a multi-GB .sif from a remote).

Options:
- Accept the cost during init (current approach)
- Advise users to `datalad get` the image in their source container dataset
  before running `babs init`, so the fetch is a fast local copy
- Add a separate `babs prepare` step for data orchestration that runs after
  init but before submit

### Container access mechanism

Currently using PROJECT_ROOT symlink (inherited from upstream). This depends on:
- `PROJECT_ROOT` environment variable propagating through SLURM
- Shared filesystem visible from compute nodes

An alternative is ephemeral clones (`datalad get -n --reckless ephemeral
containers`), which removes these dependencies but requires changing the clone
source from input RIA to the analysis dataset path. Deferred for now.

### Backwards-incompatible: features from `bidsapp_run.sh.jinja2` not yet ported

The old `bidsapp_run.sh.jinja2` template had several BABS-managed features that
are not yet in the `containers-run` path. These are **backwards-incompatible**
for users who depend on them and need to be restored or replaced.

- **TemplateFlow bind mount** — BABS read `TEMPLATEFLOW_HOME` from the
  environment and added `-B path:path_in_container` + `--env` to the singularity
  command. Could be restored in BABS, or users could handle this via
  `singularity_args` in their config.

- **FreeSurfer license bind mount** — BABS intercepted `--fs-license-file` from
  `bids_app_args` and converted it to a `-B` bind mount. Same options: restore
  in BABS or let users specify via `singularity_args`.

- **BIDS filter file** — dynamically generated per-job for session-level
  processing, restricting BIDS layout indexing to the current session. This is
  BIDS-app-specific (fmriprep gets `bold`, qsiprep gets `dwi`, etc.) and can't
  be handled by user config alone. Could potentially be supported via a hook or
  user-provided script mechanism (nothing like this exists in BABS today).

- **`${PWD}/` prefix on paths** — the old script passed absolute paths
  (`${PWD}/inputs/data/BIDS`). The `containers-run` path passes relative paths,
  which should work because `call_fmt` includes `--pwd $PWD`. Needs verification
  with BIDS apps that resolve paths differently.

### `--explicit` flag

We use `--explicit` on both `containers-run` and the zip `datalad run`. The
POC required `--explicit` because the old subject pruning (`rm -rf` of other
subjects' directories) dirtied the dataset, and datalad refuses to run on a
dirty dataset without `--explicit`. Upstream's sparse-checkout PR (#337)
eliminated subject pruning, so the dataset should stay clean. `--explicit` may
no longer be strictly necessary — kept for safety, could test removing it.
