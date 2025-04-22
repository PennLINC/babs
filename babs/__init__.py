"""Top-level package for BABS."""

try:
    from ._version import __version__
except ImportError:
    __version__ = '0+unknown'

from .bootstrap import BABSBootstrap
from .check_setup import BABSCheckSetup
from .interaction import BABSInteraction
from .merge import BABSMerge
from .update import BABSUpdate

__all__ = [
    'BABSBootstrap',
    'BABSCheckSetup',
    'BABSInteraction',
    'BABSMerge',
    'BABSUpdate',
]
