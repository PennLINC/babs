import os
import os.path as op
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "babs"))
sys.path.append("..")
from babs.cli import babs_merge_main   # noqa

babs_merge_main()
