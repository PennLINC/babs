# This is a temporary file to test out `babs-submit` and `babs-status`
import sys
import os
import os.path as op

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))   # noqa
sys.path.append(op.dirname(__location__))   # print(sys.path)   # noqa

from babs.cli import babs_submit_main, babs_status_main

# ++++++++++++++++++++++++++++++++++++++++++++++++
flag_instance = "toybidsapp"
type_session = "multi-ses"
count = 1

flag_where = "local"   # "cubic" or "local" or "msi"
# ++++++++++++++++++++++++++++++++++++++++++++++++

# where:
if flag_where == "cubic":
    where_project = "/cbica/projects/BABS/data"
elif flag_where == "local":
    where_project = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data"
elif flag_where == "msi":
    where_project = "/home/faird/zhaoc/data"
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

project_root = op.join(where_project, project_name)

print("--project-root:")
print(project_root)

babs_project = op.join(where_project, project_name)

# babs_submit_main()
babs_status_main()

print()
