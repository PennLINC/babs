# This is a temporary file to test out `babs-submit` and `babs-status`

from babs.core_functions import babs_submit
import sys
import os
import os.path as op


# ++++++++++++++++++++++++++++++++++++++++++++++++
flag_instance = "fmriprep_ingressed_fs"
type_session = "multi-ses"
count = 1

flag_where = "local"   # "cubic" or "local"
# ++++++++++++++++++++++++++++++++++++++++++++++++

# where:
if flag_where == "cubic":
    where_project = "/cbica/projects/BABS/data"
elif flag_where == "local":
    where_project = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data"
else:
    raise Exception("not valid `flag_where`!")

if flag_instance == "toybidsapp":
    project_name = "test_babs_" + type_session + "_" + flag_instance
elif flag_instance == "fmriprep":
    project_name = "test_babs_" + type_session + "_" + flag_instance
elif flag_instance == "qsiprep":
    project_name = "test_babs_" + type_session + "_" + flag_instance
elif flag_instance == "fmriprep_ingressed_fs":
    project_name = "test_babs_" + type_session + "_fpfsin"
else:
    raise Exception("not valid `flag_instance`!")

babs_project = op.join(where_project, project_name)

babs_submit(babs_project, count)

print()
