# Remote and optional RIA-store design

## Problem summary

### Issues #401 and #357

[#401](https://github.com/PennLINC/babs/issues/401), *Make RIAs properly
"Remote"*: BABS currently treats `input_ria_path` and `output_ria_path` as
local filesystem paths, then constructs `input_ria_url` and `output_ria_url`
as `ria+file://` URLs. Consequently, a compute environment cannot use a RIA
hosted on another machine, for example over SSH.

The goal is to decouple storage management from computation. The intended
deployment patterns are:

- Dartmouth: BABS housekeeping runs on the system that hosts the RIA stores,
  while compute-intensive jobs run on another system that does not host them.
- UPenn: BABS housekeeping and compute-intensive jobs run on one HCP, while the
  RIA stores are hosted on another HCP.

**Store reuse.** `input_ria_path`/`input_ria_url` and
`output_ria_path`/`output_ria_url` may identify the same underlying store.
Where safe, BABS should detect this and avoid duplicate actions such as creating
the same store twice. However, two separately configured remotes pointing to
the same location may be intentional, so matching URLs or paths must not by
itself make the remotes interchangeable.

[#357](https://github.com/PennLINC/babs/issues/357), *RIAs should be
optional*, is an orthogonal requirement. RIAs remain useful for workflows such
as compute environments without a shared filesystem, but BABS should not
require them when ordinary Git/git-annex remotes or a shared filesystem are
sufficient.

Currently, BABS creates both the RIA store `input_ria`, which backs the
`analysis` sibling `input`, and the RIA store `output_ria`, which backs the
`analysis` siblings `output` and `output-storage`, for every project.

Input and output RIA use must be configurable independently, as explicitly
requested in the discussion on #357, allowing:

- input RIA only
- output RIA only
- both input and output RIAs
- neither

"Neither" means that RIA is optional, not that result storage is optional. A
non-RIA result destination must still provide both Git history and durable
git-annex content storage.

### Current data flow and coupling

Currently, BABS creates two local RIA stores and treats their on-disk layout as
part of its API:

```text
analysis dataset (`analysis`)
  ├── DataLad sibling `input` → its repository lives in RIA store `input_ria`
  │     → a job runs `datalad clone "${dssource}"`; `dssource` identifies it
  └── DataLad sibling `output` → its repository and storage live in `output_ria`
        ├── Git repository sibling (`output`)  ← `outputstore` pushes `BRANCH`
        └── ORA storage sibling (`output-storage`) ← annexed result content

`output_ria_source` (the `output` sibling) → `merge_ds_path` (`merge_ds`)
→ merge `list_branches_jobs` → push the `output` default branch
```

### Current names and roles

| Purpose | Current Python attribute or generated-script variable | Current DataLad/Git name |
| --- | --- | --- |
| Local analysis dataset | `analysis_path` | `analysis` |
| Job clone source | `input_ria_path`, `input_ria_url`, then `dssource` | sibling `input`, backed by RIA store `input_ria` |
| Result Git receiver | `output_ria_path`, `output_ria_url`, `output_ria_data_dir`, then `pushgitremote` | sibling `output`, backed by RIA store `output_ria`; job-local remote `outputstore` |
| Result annex receiver | no separate Python attribute; hard-coded in the job script | `output-storage` ORA special remote |
| Result branch | `BRANCH` | a `job-*` branch |
| Publish lock | `DSLOCKFILE` | `analysis/.SLURM_datalad_lock` |
| Temporary merge dataset | `merge_ds_path` | `merge_ds` |
| RIA dataset identifier | `analysis_dataset_id` | RIA dataset directory and `#<dataset-id>` clone fragment |

### Current `babs merge` flow

1. BABS builds `output_ria_source` from `output_ria_url` and
   `analysis_dataset_id`, then clones it into the temporary `merge_ds_path`
   dataset rather than merging directly in `analysis`.
2. It reads the completed jobs' `job-*` branches into `list_branches_jobs`,
   then merges the valid branches into `merge_ds`'s `default_branch_name`
   (`main` or `master`).
3. It pushes the merged default branch back to the output RIA, verifies that
   the corresponding annexed content is available from `output-storage`, and
   then deletes the merged job branches.

Consequently, after `babs merge`, the output RIA holds the advanced default
branch before the local `analysis` checkout does. The current
`babs update-input-data` path later updates `analysis` from its `output`
sibling. This is one reason the proposed design instead makes canonical
`analysis` history explicit during merge.

### RIA-specific implementation dependencies

The following code paths currently depend on local RIA paths, fixed sibling
names, or both:

- [`babs/base.py`](../babs/base.py) resolves `input_ria_path` and
  `output_ria_path` (the `input_ria` and `output_ria` project directories)
  below the project root, constructs `input_ria_url` and `output_ria_url`, and
  uses `wtf_key_info()` to parse the `output` sibling into
  `output_ria_data_dir`. `_get_results_branches()` then runs Git in that local
  directory.
- [`babs/bootstrap.py`](../babs/bootstrap.py) always creates RIA-backed
  `analysis` siblings with `create_sibling_ria()`: `input`, backed by
  `input_ria`, and `output` plus `output-storage`, backed by `output_ria`. It
  writes `input_ria_path` and `output_ria_path` to `.gitignore`, creates the
  local `output_ria/alias/data` symlink, and assumes it can clean or inspect
  the stores as local paths.
- [`babs/templates/participant_job.sh.jinja2`](../babs/templates/participant_job.sh.jinja2)
  calls `datalad clone "${dssource}"`, adds `pushgitremote` as the job-local
  Git remote `outputstore`, copies content to the hard-coded `output-storage`
  annex remote, and locks only `git push outputstore "${BRANCH}"`.
- [`babs/merge.py`](../babs/merge.py) clones a constructed output-RIA URL for
  the `output` sibling backed by `output_ria` into `merge_ds_path`, checks
  `output-storage`, and deletes branches by operating directly in
  `output_ria_data_dir`.
- [`babs/check_setup.py`](../babs/check_setup.py) validates RIA aliases and
  local `input_ria_path`/`output_ria_path` layout paths, including
  `actual_input_ria_data_dir` and `actual_output_ria_data_dir`.
  [`babs/update.py`](../babs/update.py) always calls `push(to='input')` and
  `push(to='output')`.

### Job result publication: `outputstore` versus `output-storage`

These similarly named values are different kinds of remote in a job clone:

- `outputstore` is a job-local **Git remote**. The job creates it with
  `git remote add outputstore "${pushgitremote}"` and pushes the result
  `job-*` branch with `git push outputstore "${BRANCH}"`. Its URL points to
  the Git repository backing the `output` sibling.
- `output-storage` is the configured **git-annex ORA special remote**. The job
  transfers actual annexed result-file content with
  `datalad push --to output-storage`. It stores those objects in the output
  RIA's annex storage.

In short, `outputstore` receives Git history and result refs, whereas
`output-storage` receives annexed file content. They are paired by the output
RIA setup, but `outputstore` exists only as a name added in each job clone;
`output-storage` is the persistent git-annex remote configuration.

There is already a partial move toward endpoint-based branch lookup:
`get_results_branches_from_ria()` uses `git ls-remote`. It currently converts a
remote-access error into an empty list, which is unsafe for status reporting.
The refactor should retain the endpoint-based approach but surface such errors.

### Constraints for the refactor

1. **Results require two channels.** In the current job template, `dssource`
   identifies the `input` sibling backed by `input_ria`. The Git receiver is
   the `pushgitremote` argument, registered as Git remote `outputstore`, which
   targets the `output` sibling backed by `output_ria`. The annex receiver is
   the `output-storage` special remote. A Git receiver can hold result branches
   and the `git-annex` branch, but it does not by itself guarantee that annexed
   result objects are available. The output contract must name both the Git
   receiver and the git-annex storage remote.

2. **Annex metadata is part of publication.** A result publish is not merely
   “copy data, then push `${BRANCH}`”, where `BRANCH` is currently a `job-*`
   branch. It must transfer content to `output-storage`, update and publish
   `git-annex` location metadata, and publish the result ref to `outputstore`.
   The paired RIA siblings currently supply this behavior implicitly.

3. **Concurrency must be explicit and capability-based.** `DSLOCKFILE` is
   generated from `babs.analysis_path + '/.SLURM_datalad_lock'`, but it covers
   only `flock "${DSLOCKFILE}" git push outputstore "${BRANCH}"`. A safe generic
   protocol must coordinate updates to shared Git and git-annex metadata, merge,
   and branch deletion. It should not serialize large annex-object transfers
   when the provider has demonstrated that concurrent transfers are safe. A
   `flock` file works only if every publisher and merger sees the same
   filesystem; an SSH URL alone does not provide a distributed lock.

4. **Remote RIA is not automatically a no-shared-filesystem or
   multi-controller solution.**
   Current jobs still use `analysis_path` for the submit script,
   `SUBJECT_CSV`/`job_submit_path_abs`, logs, `CONTAINER_SHARED` images, and
   the current lock. The first release therefore requires a single logical
   analysis control plane: controller commands and scheduler submission share
   one canonical `analysis` checkout, compute nodes can read the required
   analysis assets, and every publisher and merger can reach the configured
   coordinator. A deployment that runs submission and housekeeping against
   independent analysis checkouts requires state synchronization, artifact
   staging, and a distributed coordinator and is not delivered merely by
   accepting `ria+ssh` URLs.

5. **External endpoints must be adopted safely.** BABS may configure a
   sibling in its own clone and perform explicitly authorized, namespaced Git
   and annex publication. It must not initialize or reconfigure server-side
   storage, force-push shared history, delete outside its namespace, or clean an
   externally owned remote. It must reject an endpoint whose dataset identity,
   canonical history, or annex binding is incompatible.

6. **Store-root, dataset-target, and remote-role identities differ.** The current
   `input_ria_path`/`input_ria_url` and `output_ria_path`/`output_ria_url`
   specifications may resolve to one RIA root and one RIA dataset target. Store
   creation can be coalesced by confirmed store-root identity; dataset creation
   and initial publication can be coalesced only by confirmed dataset-target
   identity. BABS must nevertheless retain separate logical clone, result-Git,
   and result-annex roles when their names, permissions, or publication settings
   differ. Fetch and push URLs may differ, so raw URL equality is never enough
   evidence that two roles are interchangeable.

7. **Result refs need namespacing and immutability.** Branch deletion must never
   remove another user's `job-*` branch. `BRANCH` currently generates that
   prefix, and `_get_results_branches()` selects it. New configurations should
   use a stable project-scoped namespace and a new ref for every attempt. A
   published result ref is immutable; a retry publishes a new attempt ref. The
   scratch-directory name must be separate from the slash-containing Git ref.
   Legacy projects can recognize existing branch names only under stricter
   ownership and deletion rules.

8. **Transport values need safe argument and credential handling.** The submit
   path currently builds `cmd_template`, derives `cmd`, and invokes
   `cmd.split()`. New URLs and paths must be represented as structured argv
   values rather than relying on whitespace splitting. Credentials must not be
   embedded in URLs or stored in tracked YAML, generated scripts, scheduler
   command lines, or `set -x` output. SSH agents, Git credential helpers,
   environment-specific credential providers, or non-secret credential-profile
   names supply authentication.

9. **Jobs need a pinned canonical revision.** A queued job must not silently
   switch to newer code or inputs because the clone source advanced before the
   job started. Submission records an exact canonical commit, publishes that
   commit and required git-annex configuration to the clone source, and makes
   the job verify and check out that commit. The result record includes the base
   commit; merge must not infer result validity merely by comparing a job ref to
   the current default branch.

10. **Publication and merge must be recoverable.** Updating local canonical
    history, one or more remote default branches, the `git-annex` branch, and
    result refs is not a single cross-endpoint transaction. Operations must use
    exact expected OIDs, persist enough state to resume after failure, and keep
    result refs until every required canonical publication has succeeded.

## Proposed architecture

### Principles

- `analysis` is the canonical BABS dataset and durable control plane. Remote
  stores distribute a known analysis revision and collect results; they are not
  the sole authority for merged history.
- Storage and execution locations are independent. A controller may run BABS
  housekeeping close to the RIA store while jobs run on another HCP, or both
  controller and jobs may run on one HCP while the RIA is hosted on another.
  Each location needs only the endpoint access and credentials appropriate to
  its work. The supported topology must still satisfy the first-release control
  plane and coordinator contract above. No BABS command may infer an on-disk
  repository path and operate inside a RIA layout.
- RIA is a provider type, not a special execution path. A managed RIA creates
  a repository sibling and an ORA storage sibling. An existing provider
  validates and configures BABS-local sibling state and permits only the
  explicitly authorized publication operations.
- A result topology must be annex-capable. Its Git and annex roles may map to
  the same regular git-annex sibling or to separate Git and special remotes. A
  code-only Git repository is not a valid result destination.
- A plain Git endpoint can be a clone source only when it contains a viable
  DataLad dataset history, including the refs and subdataset information needed
  by a fresh job clone.
- Configuration resolution is pure. Network access, sibling creation,
  materialized endpoint discovery, and capability checks occur only in
  explicit provisioning or validation operations.
- Provider-neutral control-plane code consumes provisioned bindings and
  capabilities. It does not branch on RIA layout details.

### Supported host topology

Before provisioning, BABS records and validates where each actor runs:

| Actor or operation | Required access |
| --- | --- |
| `babs init`, `sync-code`, `update-input-data`, and `merge` | canonical `analysis`, provider control endpoints, and publication coordinator |
| `babs submit` and scheduler integration | canonical project configuration, inclusion/submission state, scripts, and log destination |
| compute job | pinned clone source, result Git and annex receivers, coordinator, subject CSV, and container images |
| status/reporting | scheduler state plus result-Git ref enumeration |

The initial implementation supports one logical analysis control plane even if
the RIA store is remote. The Dartmouth-style split is supported in this stage
only when submission and housekeeping share that control plane and coordinator.
Independent controller checkouts and staging of scripts, logs, CSV files, or
containers are a later project and must not be implied by `ria+ssh` support.

### Runtime roles

- **Job clone source** — Current names: `dssource`, `input_ria_url`, and the
  `input` sibling backed by `input_ria`. It supplies each job's fresh analysis
  clone and requires read/clone access.

- **Result Git receiver** — Current names: `pushgitremote`, the job-local
  `outputstore` remote, and the `output` sibling backed by `output_ria`. It
  receives result-branch and annex-metadata refs, and requires read, push, and
  ref-enumeration access.

- **Result annex receiver** — Current name: `output-storage`, backed by
  `output_ria`. It stores annexed result objects, has a stable annex UUID, and
  must be enableable and usable in a fresh job clone. It may be the same named
  regular Git sibling as the result Git receiver or a distinct special remote.

- **Publication coordinator** — Current name: `DSLOCKFILE`. It serializes
  operations that cannot run concurrently and requires a lock protocol that
  every publisher and merger can reach.

- **Canonical publisher** — Replaces fixed `push(to='input')` and
  `push(to='output')` calls. It publishes a specific canonical commit and
  required git-annex metadata to every unique target that must serve that
  revision.

Each role has independent fetch and push endpoints where needed. When input
transport is omitted, the clone source falls back to the local shared
`analysis` dataset. When output transport is omitted, the result receiver does
the same. This fallback still creates or configures an annex-capable receiver
in the job clone; it is not a code-only shortcut.

### Configuration specifications and provisioned bindings

The internal API separates declarative configuration from operational values:

- `TransportSpec` is the versioned, non-secret user configuration. Parsing and
  resolving it performs no network access.
- `TransportBinding` is produced by provisioning or loading validated local
  sibling state. It contains actor-specific dataset clone and result Git
  endpoints, annex remote name and UUID, enable procedures, coordinator
  binding, provider capabilities, and canonical publication targets.

This separation matters for managed RIA. Actor access profiles identify a RIA
store through the URLs that the controller and jobs can actually use. A clone
URL additionally selects the dataset with `#<dataset-id>` or `#~alias`, while
ordinary Git operations such as `git ls-remote` and `git push` require a
provisioned Git sibling endpoint. Provider setup uses controller access to
provision the store, materializes separate controller and job bindings, and
does not assume its own local sibling URL is usable by a job. Generic
control-plane code does not construct RIA layout paths.

An existing result provider must describe both sides of the topology:

- the Git sibling's fetch URL, push URL, name, and expected dataset identity;
- the annex binding's name, expected UUID, kind, and fresh-clone enable method;
  and
- a non-secret credential-profile name when environment-specific setup is
  required.

Some special remotes need parameters on every `git annex enableremote` call.
Those parameters must come from non-secret configuration plus an external
credential provider. A remote name by itself is not a sufficient binding.

### Store roots, dataset targets, and logical roles

Provisioning tracks three distinct identities:

- A **logical remote role** describes how BABS uses an endpoint: clone source,
  result Git receiver, or result annex receiver. Roles retain their own
  sibling names, publication dependencies, and permissions.
- A **store-root identity** is used only to coalesce creation or validation of a
  managed RIA root.
- A **dataset-target identity** combines the confirmed store and dataset
  identity and is used to coalesce dataset creation and initial canonical
  publication.

For example, input and output may be separately configured siblings that
target one RIA root and dataset. BABS creates the RIA root once and the dataset
target once, configures all requested logical siblings, and publishes the
initial canonical state once per unique dataset target. Provider planning must
create the annex-capable result bundle before a clone-only sibling when that
order is required. This optimization must not erase a deliberately distinct
storage sibling or make the roles aliases for each other.

Coalescing requires an explicit declaration such as `reuse: clone_source` plus
provider validation. Equivalent-looking URLs are not proof of identity. If
identity is uncertain, BABS performs distinct safe operations or rejects an
ambiguous managed configuration.

### Configuration model

Persist a versioned, non-secret `transport` section in the authoritative BABS
project configuration. The exact CLI spelling remains a design decision, but
users must be able to provide it at `babs init` time without placing secrets in
YAML. A managed-RIA example is:

```yaml
transport:
  version: 1
  project_id: 8eadaf62-3bad-4c2a-aad7-b77799f01234
  managed_stores:
    project-store:
      controller:
        read_url: ria+file:///srv/babs-ria
        write_url: ria+file:///srv/babs-ria
      job:
        read_url: ria+ssh://job-reader@ria.example.org/srv/babs-ria
        write_url: ria+ssh://job-writer@ria.example.org/srv/babs-ria
  clone_source:
    kind: managed-ria
    store: project-store
    sibling_name: babs-input
  results:
    kind: managed-ria
    store: project-store
    reuse_dataset_target: clone_source
    repository_sibling_name: babs-results
    storage_sibling_name: babs-results-storage
  coordination:
    kind: shared-flock
    lock_path: /shared/project/analysis/.babs-publish.lock
```

The named store avoids duplicating physical-store configuration while logical
roles remain independent. Jobs read from the clone source and read/write the
result topology during annex metadata reconciliation; the controller must
read/write both targets for validation and canonical publication. Unneeded
actor operations may be omitted only when the capability matrix proves that no
workflow uses them. Every configured actor access context must be tested.

An existing Git-plus-annex result topology uses a discriminated shape instead:

```yaml
transport:
  version: 1
  project_id: 8eadaf62-3bad-4c2a-aad7-b77799f01234
  clone_source:
    kind: analysis
  results:
    kind: existing
    git:
      sibling_name: babs-results
      expected_dataset_id: 238da2f2-2fc4-4b88-a2c5-aa6e754b5d0b
      controller:
        fetch_url: file:///srv/babs-results.git
        push_url: file:///srv/babs-results.git
      job:
        fetch_url: ssh://job-reader@results.example.org/srv/babs-results.git
        push_url: ssh://job-writer@results.example.org/srv/babs-results.git
    annex:
      kind: existing-remote       # or: git-sibling
      remote_name: babs-results-storage
      expected_uuid: 7f4a56a1-7e80-4a91-8239-95a39e3f3792
      enable: auto                # or a supported named enable strategy
      credential_profiles:
        controller: babs-results-controller
        job: babs-results-jobs
  coordination:
    kind: shared-flock
    lock_path: /shared/project/analysis/.babs-publish.lock
```

`managed-ria` accepts DataLad-supported RIA store read and write URLs,
including `ria+file` and `ria+ssh`. `existing` declares an already provisioned
topology; BABS validates it from a fresh clone and performs only authorized
publication. `analysis` is the explicit shared-filesystem fallback. A result
configuration may explicitly reuse the clone source, but that declaration
permits management coalescing only after identity validation and does not erase
the logical roles. `reuse_dataset_target` is an explicit assertion to validate,
not permission to infer identity from equivalent-looking URLs.

Only coordinator kinds with a demonstrated acquisition, exclusion, stale-lock
recovery, and release protocol belong in version 1. `shared-flock` is valid only
for a verified shared filesystem. A server-side SSH lock or a lease-controlled
remote Git ref is a candidate for split-host use, not a promised provider until
the integration probes prove it.

The authoritative operational configuration is the tracked, non-secret project
configuration in `analysis/code/babs_proj_config.yaml`; the root `.babs`
configuration is a bootstrap/locator snapshot. Materialized bindings and local
credential-provider state are untracked, permission-restricted, and
regenerable. Migration updates the authoritative configuration and regenerates
derived participant and scheduler templates atomically.

The binding exposed to runtime code contains actor- and role-oriented values
such as `job_clone_dataset_url`, `job_result_git_fetch_url`,
`job_result_git_push_url`, `controller_result_git_fetch_url`,
`controller_result_git_push_url`, `result_annex_name`, `result_annex_uuid`,
`canonical_publish_targets`, and `publication_coordinator`. It must not expose
or depend on `output_ria_data_dir`.

### Project namespace

Every new project has a stable random `project_id`. Result and probe refs use
separate namespaces, for example:

```text
refs/heads/babs/<project-id>/jobs/<scheduler-job-id>/<task-id>/<attempt-id>
refs/heads/babs/<project-id>/probes/<probe-id>
```

The participant job uses a separate filesystem-safe scratch name. It publishes
an immutable result ref with an explicit refspec such as
`HEAD:<fully-qualified-result-ref>`; retries use a new `attempt-id`. Status
parsing consumes the namespace and result metadata rather than relying solely
on subject strings embedded in a branch name.

Legacy projects continue to enumerate `job-*` only through the legacy binding.
Deletion is limited to exact OIDs and branches attributable to the project's
job ledger on its configured dedicated endpoint. A legacy project must migrate
before sharing a generic result receiver where ownership cannot be proven.

### Canonical revision publication

Bootstrap, `sync-code`, `update-input-data`, job submission, and merge all use
one `publish_canonical(commit_oid)` operation. For each unique required target,
it publishes the specified canonical Git commit and the git-annex metadata a
fresh clone needs. It uses an explicit refspec and expected remote OID rather
than argument-less `push()` behavior. Failure reports which targets succeeded
and which remain pending; it never rewrites an incompatible remote branch.

Submission records the canonical commit OID only after the clone source is
confirmed to contain it. The job clones the configured source, fetches that OID
if necessary, verifies the canonical dataset ID, and checks out the pinned
revision before creating its result branch.

### Job publication protocol

The generated participant job receives resolved role endpoints. This replaces
the current `dssource`, `pushgitremote`, hard-coded `output-storage`, and
`DSLOCKFILE` inputs with a pinned revision and a validated
`TransportBinding`. Publication is a prepare/commit protocol:

1. Clone and check out the pinned canonical revision; configure and verify the
   result Git sibling and annex binding, including the expected annex UUID.
2. Create a filesystem-safe work directory and a project-scoped, attempt-scoped
   local result branch.
3. Run the workload, save its provenance and outputs, and create result metadata
   containing the base OID, scheduler identifiers, and attempt ID. The result
   ref itself supplies the result commit OID. Do not publish a completion ref if
   no valid result commit exists.
4. In the prepare phase, transfer annex objects outside the coordinator only if
   the provider contract proves concurrent object transfers safe. Record the
   resulting location metadata locally. Providers without that capability
   perform this step under the coordinator.
5. In the commit phase, acquire the coordinator, fetch and reconcile the latest
   remote `git-annex` metadata, publish the updated metadata with conflict
   detection/retry, and verify the result content is reported at the configured
   annex receiver.
6. Push the immutable result ref last, using an explicit create-only lease or
   equivalent expected-absence check, then release the coordinator.

Pushing the result ref last makes it the completion marker. A failure before
that point may leave harmless unreferenced content but must not make an
incomplete result visible to status or merge. The Stage 0 reference protocol
must also demonstrate that a DataLad publication dependency cannot implicitly
publish the result ref before the commit phase.

### Merge transaction

`babs merge` treats `analysis` as canonical and never operates inside a RIA
layout. Its journal lives in permission-restricted, untracked project state and
is written with atomic replacement before each irreversible transition:

1. Fail if canonical analysis has uncommitted tracked changes. Acquire the
   local BABS control-plane lock used by `sync-code` and `update-input-data`,
   then resume any recoverable unfinished journal before starting a new merge.
   If automatic recovery is unsafe, stop with a precise recovery command. Only
   after recovery record the canonical branch and base OID for a new merge.
2. Enumerate only
   `refs/heads/babs/<project-id>/jobs/*` with `git ls-remote --heads`, recording
   each exact ref/OID pair. An access or authentication error is fatal and is
   never reported as "no results".
3. Create a uniquely named temporary clone or worktree from the recorded
   canonical base, configure the result annex binding, and fetch every recorded
   result OID into a private temporary ref. Validate result metadata and merge
   the fetched commits. Expensive merge work need not hold the distributed
   publication coordinator because result refs are immutable.
4. Verify that every annex key introduced by the merge is available from the
   configured result annex receiver. Do not advance canonical history on
   failure.
5. Persist a merge journal containing the canonical base, result ref/OID
   snapshot, merge OID, annex verification outcome, and per-target publication
   and per-ref pruning state. Import the merge commit into canonical analysis
   and compare-and-swap fast-forward the canonical ref only if it still equals
   the recorded base; update the canonical worktree consistently.
6. Acquire the publication coordinator, reconcile and publish required
   git-annex metadata, and run `publish_canonical(merge_oid)` for every unique
   clone/result target with explicit expected OIDs. A partial failure leaves the
   journal and all result refs intact for idempotent retry.
7. After every canonical publication succeeds, delete each exact result ref
   using a lease that requires the remote ref still to equal its recorded
   result OID. Never use a wildcard deletion or an implicit tracking ref as the
   lease. Record each successful deletion so recovery does not repeat completed
   work.
8. After all deletions succeed, release the coordinator, remove the merge
   journal, and clean the temporary clone. A cleanup failure is reported
   separately and does not roll back a completed merge.

This transaction prevents the result receiver from becoming the default-branch
authority, avoids deleting a replaced result ref, and makes interruption after
local or partial remote publication recoverable.

## Staged refactoring plan

### 0. Freeze the support contract with integration probes

Before changing behavior, probe the exact DataLad/git-annex versions supported
by BABS, including its declared minimum DataLad version and a declared minimum
git-annex version. If the protocol requires newer behavior, raise the minimum or
provide a tested compatibility path. For each candidate topology, use a fresh
job-style clone to transfer a small annexed file, publish metadata and a result
ref in the required order, retrieve the file in an independent merge clone,
exercise concurrent publishers, and simulate failure between each protocol
step.

Required probes:

- current managed local RIA workflow;
- managed `ria+ssh` with separate read/push URLs where supported;
- controller and job access through distinct hosts or credential contexts;
- an externally managed Git-plus-annex sibling pair;
- analysis as clone source and/or result receiver;
- one explicitly shared endpoint;
- input and output roles that share one managed RIA store, plus intentionally
  distinct roles that happen to use equivalent-looking URLs;
- safe and unsafe concurrent annex-object transfer;
- coordinator exclusion, release, failure, and stale-owner recovery;
- exact-OID canonical publication and lease-safe deletion;
- rejection of a code-only result endpoint; and
- authentication and inaccessible-endpoint errors that remain distinct from an
  empty result namespace.

The deliverable is a capability matrix and executable reference algorithm for
each supported provider, not merely pass/fail notes. Do not promise the
split-controller Dartmouth topology or arbitrary git-annex special remotes
until their coordinator, initialization, fresh-clone enablement, credential,
and publication behavior have been demonstrated.

### 1. Add the specification, binding, namespace, and compatibility layer

Create typed `TransportSpec`, `TransportBinding`, capability, identity, and
coordinator interfaces. Add schema validation, the stable project namespace,
an explicit init-time configuration interface, and a transport-configuration
version. The model must represent clone and result providers independently and
support all four combinations explicitly required by issue #357.

For projects without the new section, synthesize the current two local managed
RIAs without rewriting the project. Provide an explicit migration command or a
documented migration path for projects that want the new representation. The
legacy adapter retains legacy sibling and ref names while enforcing exact-OID
deletion and dedicated-endpoint ownership rules.

Split the current `wtf_key_info()` responsibilities: obtain
`analysis_dataset_id` as the canonical dataset identity, provision managed RIA
URLs through provider operations, obtain materialized Git and annex bindings
from sibling state, and inspect remote refs through the result Git endpoint.
The constructor and pure resolver perform no network access.

Replace submit command strings with structured argv templates end to end; do
not use `cmd.split()` or shell re-parsing. Reject credential-bearing URLs,
redact endpoints in errors, and prevent participant `set -x` output from
printing sensitive environment-derived values.

### 2. Implement the canonical transaction on the current local-RIA topology

Before adding new providers, implement pinned revision publication, the
prepare/commit job protocol, project-scoped refs for new projects, exact result
ref enumeration, the merge journal, CAS canonical updates, canonical
publication, and lease-safe pruning against the existing managed local-RIA
workflow. Preserve legacy project behavior through the adapter.

This vertical slice must cover `submit`, `status`, `merge`, `sync-code`,
`update-input-data`, and `check-setup`; do not release an intermediate state in
which only bootstrap or participant jobs understand the new transport model.

### 3. Add provider-aware bootstrap, analysis fallbacks, and cleanup

Replace unconditional `create_sibling_ria()` calls with provider operations:

- create managed RIA siblings only when requested;
- configure and verify BABS-local siblings for an existing endpoint;
- configure the analysis fallback without creating a remote store.

Make `.gitignore`, alias, safe-directory, permission, and cleanup behavior
provider-conditional. New configurations stop relying on `output_ria/alias`,
but legacy aliases are preserved. Local managed stores and shared-group
analysis or input repositories retain the safe-directory handling they need.

Use confirmed store-root and dataset-target identities to plan provisioning.
Create each store root and dataset target only once while retaining every
logical sibling, then publish once per unique dataset target. Record a
provisioning ledger before each mutation. Cleanup never deletes a shared store
root; it may remove only an exact resource created by the current operation
with strong ownership proof. Externally owned resources are never cleanup
targets.

Complete the clone/result matrix for `analysis` fallbacks and managed local RIA:
input RIA only, output RIA only, both, and neither.

### 4. Add managed remote RIA and the proven coordinator

Implement managed `ria+ssh` using DataLad store read/write URLs and materialized
Git/annex bindings. Test controller-read/job-write and job-read/controller-write
access separately. Add only the coordinator kind selected and proven in Stage
0. If no distributed coordinator is accepted, document the shared-control-plane
restriction and do not claim the independent split-controller deployment.

Extend `babs check-setup --job-test` with a real compute-node transport smoke
test. It must verify the credentials and endpoint access that a future job
will use, not merely the Python/container environment. It also performs a
cross-process coordinator exclusion test. Probe refs use the project probe
namespace and are deleted only with exact leases. A tiny annex canary may be
retained intentionally; content cleanup is not attempted unless the provider
can prove exclusive ownership and safe deletion.

### 5. Add supported existing Git-plus-annex providers

Implement existing clone sources and result Git/annex bindings one demonstrated
capability class at a time. Validate dataset identity, canonical ancestry,
annex UUID, fresh-clone enablement, read/write/list/delete permissions, and
coordinator reachability. A write-capability probe requires explicit user
authorization, uses only the project probe namespace, and does not reinitialize
or destructively clean the endpoint.

Do not advertise arbitrary special remotes. Document precisely which regular
git-annex and special-remote bindings are supported and which enable strategies
and credential providers they require.

### 6. Regression coverage, documentation, and release migration

Preserve the existing local-RIA workflow as an end-to-end regression. Add
coverage for all input/output optional combinations, externally managed
annex-capable output, explicitly shared endpoints, a real SSH fixture, failed
authentication, controller/job access from distinct hosts or credentials,
same-store creation coalescing, intentionally separate remotes with
equivalent-looking URLs, branch-deletion races, fresh-clone annex
configuration, pinned jobs across canonical updates, partial publication and
merge recovery, dirty canonical worktrees, stale journals, coordinator failure,
safe-directory/shared-group projects, paths containing spaces, secret
redaction, and the legacy configuration path.

Run topology tests as vertical end-to-end workflows, not only provider unit
tests. A release is gated on all control-plane commands consuming the same
binding and transaction model and on compatibility tests at the declared
minimum dependency versions.

Document:

- RIA as the default managed provider;
- the distinction between remote stores, the controller location, and the
  compute-visible analysis control plane required by the first-stage design;
- credential requirements on controller and compute nodes;
- supported external remote capabilities and unsupported code-only output;
- coordinator scope, failure, and recovery requirements;
- project ref namespaces and legacy ownership limitations;
- configuration authority, credential providers, and secret-handling rules;
- canonical publication and merge-journal recovery; and
- migration and rollback guidance.

## Scope boundary

This work addresses remote and optional analysis transport. It should not
silently expand into a rewrite of output zipping, raw-derivative merging, or
general ephemeral worktree behavior. Packaging the submit script, logs, input
CSV, lock, and containers for a compute environment that cannot access
`analysis_path`, synchronizing multiple canonical controller checkouts, or
remotely controlling a scheduler is valuable, but is a subsequent architectural
project. Until then, remote RIA support requires the single logical analysis
control plane described above.
