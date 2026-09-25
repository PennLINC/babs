"""BABS-owned datalad procedures.

:func:`procedures_registered` temporarily points datalad at this directory
(``datalad.locations.extra-procedures``) so ``dlapi.create(cfg_proc='babs')``
finds :mod:`babs.procedures.cfg_babs`. The scaffold constants are re-exported
here so ``babs`` code and the tests share a single source of truth with the
procedure script.
"""

import os.path as op
from contextlib import contextmanager

from babs.procedures.cfg_babs import BIDS_GITATTRIBUTES, CODE_GITATTRIBUTES

PROCEDURES_DIR = op.dirname(__file__)

__all__ = [
    'BIDS_GITATTRIBUTES',
    'CODE_GITATTRIBUTES',
    'PROCEDURES_DIR',
    'procedures_registered',
]


@contextmanager
def procedures_registered():
    """Register BABS's procedures dir with datalad for the duration of the block.

    Lets ``dlapi.create(cfg_proc='babs')`` resolve ``cfg_babs`` without leaving a
    persistent ``datalad.locations.extra-procedures`` override on the global
    datalad config, which would otherwise shadow a user's own setting and leak
    into later datalad calls in the same process. The override is removed on the
    way out even if the wrapped call raises.
    """
    # Local import so that importing the constants above does not pull in datalad.
    from datalad import cfg as datalad_cfg

    key = 'datalad.locations.extra-procedures'
    datalad_cfg.set(key, PROCEDURES_DIR, scope='override', reload=True)
    try:
        yield
    finally:
        datalad_cfg.unset(key, scope='override', reload=True)
