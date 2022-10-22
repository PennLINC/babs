# This is a temporary file to test babs-init


from babs.core_functions import babs_init
import sys
import os
import os.path as op

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "babs"))

# ++++++++++++++++++++++++++++++++++++++++++++++++
flag_instance = "fmriprep_ingressed_fs"
type_session = "multi-ses"


flag_where = "local"   # "cubic" or "local"
# ++++++++++++++++++++++++++++++++++++++++++++++++

# if else:
if flag_where == "cubic":
    where_project = "/cbica/projects/BABS/data"
elif flag_where == "local":
    where_project = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data"
else:
    raise Exception("not valid `flag_where`!")

if flag_instance == "fmriprep":
    input_ds_name = "fmriprep"
    if type_session == "multi-ses":
        input_ds = op.join(where_project, "j854e")
    elif type_session == "single-ses":
        input_ds = op.join(where_project, "zd9a6")

    input_cli = [["BIDS", input_ds]]

    print("NOT FINISHED YET....")


elif flag_instance == "qsiprep":
    print("")
elif flag_instance == "xcpd":
    print("")
elif flag_instance == "fmriprep_ingressed_fs":
    assert type_session == "multi-ses"
    project_name = "test_babs_" + type_session + "_fpfsin"
    bidsapp = "fmriprep"
    input_cli = [["BIDS", op.join(where_project, "j854e")],
                 ["freesurfer", op.join(where_project, "fmriprep_multises_outputs")]]


else:
    raise Exception("not valid `flag_instance`!")


# container_ds:
if flag_where == "cubic":
    container_ds = op.join(where_project, "toybidsapp-container")
elif flag_where == "local":
    container_ds = op.join(where_project, "toybidsapp-container-docker")
container_name = bidsapp + "-0-0-0"  # "toybidsapp-0-0-3"
container_config_yaml_file = "notebooks/example_container_" + flag_instance + ".yaml"

if os.getenv("TEMPLATEFLOW_HOME") is None:
    os.environ['TEMPLATEFLOW_HOME'] = '/templateflow_home_test'

babs_init(where_project, project_name,
          input=input_cli,
          container_ds=container_ds,
          container_name=container_name,
          container_config_yaml_file=container_config_yaml_file,
          type_session=type_session,
          system="sge")

print("")
