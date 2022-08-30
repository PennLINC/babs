# This is a temporary file to test babs-init

import sys
import os
import os.path as op
sys.path.append( os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "babs"  ))

from babs.core_functions import *
from babs.cli import *

where_project = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data"
project_name = "test_babs"
input_ds = op.join(where_project, "j854e")
type_session = "multi-ses"
container_ds = op.join(where_project, "toybidsapp-container-docker")
container_name = "toybidsapp-0-0-3"
container_config_yaml_file = "../notebooks/example_container.yaml"


babs_init(where_project, project_name, 
            input = ["False", input_ds],
            container_ds = container_ds,
            container_name = container_name,
            container_config_yaml_file= container_config_yaml_file,
            type_session = type_session,
            system = "sge")

print("")


