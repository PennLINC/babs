# This is a temporary file to test babs-init

import sys
import os
import os.path as op
sys.path.append( os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "babs"  ))

from babs.core_functions import *
from babs.cli import *

where_project = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data"
project_name = "test_babs"
input_ds = op.join(where_project, "zd9a6")
type_session = "multi-ses"
container_ds = op.join(where_project, "xxxx")

babs_init(where_project, project_name, 
            input = ["False", input_ds],
            container_ds = container_ds,
            type_session = type_session,
            system = "sge")

print("")


