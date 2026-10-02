"""BABS analysis-dataset setup, as a datalad ``cfg_babs`` procedure.

Run by ``datalad create -c babs`` (i.e. ``dlapi.create(cfg_proc='babs')``) so a
BABS project owns its scaffold outright instead of taking datalad's ``yoda``
default and editing its ``.gitattributes``. It writes:

* a BIDS-friendly root ``.gitattributes`` (small text, incl. BIDS metadata
  sidecars, stays in git; binary or >1MiB files go to the annex);
* a ``code/`` directory whose contents always stay in git (BABS writes its
  scripts there and they must be directly readable, never annexed symlinks);
* minimal ``README.md`` / ``CHANGELOG.md`` so the result reads as a normal
  dataset.

The module is self-contained (standard library + datalad only) so it runs in
datalad's procedure interpreter without importing ``babs``; ``babs`` and the
test suite import the constants below from :mod:`babs.procedures`.
"""

import sys

# Annex a file if it is non-empty and binary (`mimeencoding=binary`, which needs
# git-annex's MagicMime build flag) or larger than 1MiB, so BIDS metadata (JSON,
# TSV, README) stays in git. Empty files read as binary to libmagic, so the size
# guard (`largerthan=0`) keeps them in git.
BIDS_GITATTRIBUTES = """\
* annex.backend=MD5E
* annex.largefiles=(((mimeencoding=binary)and(largerthan=0))or(largerthan=1MiB))
**/.git* annex.largefiles=nothing
"""

# `code/` is forced into git wholesale so scripts are always directly readable.
CODE_GITATTRIBUTES = '* annex.largefiles=nothing\n'

README = """\
# BABS project

This dataset was created by [BABS](https://github.com/PennLINC/babs).
All custom code lives in `code/`.
"""


def main(dataset_path):
    """Install the BABS scaffold into the freshly created dataset."""
    from datalad.distribution.dataset import require_dataset

    ds = require_dataset(dataset_path, check_installed=True, purpose='BABS dataset setup')
    root = ds.pathobj

    # Overwrite datalad's create-time `.gitattributes` before any content is
    # saved, so the annex policy applies to every file BABS adds afterward:
    (root / '.gitattributes').write_text(BIDS_GITATTRIBUTES)

    # `code/` must exist (BABS writes scripts into it during bootstrap) and stay
    # wholly in git, regardless of the size/binary rule above:
    code_dir = root / 'code'
    code_dir.mkdir(exist_ok=True)
    (code_dir / '.gitattributes').write_text(CODE_GITATTRIBUTES)

    (root / 'README.md').write_text(README)
    (root / 'CHANGELOG.md').write_text('')

    ds.save(
        path=[
            root / '.gitattributes',
            code_dir,
            root / 'README.md',
            root / 'CHANGELOG.md',
        ],
        message='Apply BABS dataset setup',
        result_renderer='disabled',
    )


if __name__ == '__main__':
    main(sys.argv[1])
