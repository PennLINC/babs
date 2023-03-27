# This is a temporary file to test babs-init
# Note: first time running (with debugging mode) this in a vscode window
#   will have error:
#   e.g., $FREESURFER_HOME was not successfully exported
#   solution: stop the debugging; in `Python Debug Console`:
#   if on my local Mac:
#       $ source ~/.bashrc
#       $ conda activate mydatalad
#   if on cubic:
#       $ module unload freesurfer/5.3.0
#           # ^^ 5.3.0 is not folder and does not contain `license.txt`....
#       $ module load freesurfer/7.2.0
#       $ echo $FREESURFER_HOME
#   if on cubic but using vscode to debug:
#       $ export FREESURFER_HOME=/cbica/software/external/freesurfer/centos7/7.2.0
#   then start the debugging again

from babs.cli import babs_init_main
import sys
import os
import os.path as op
# import subprocess

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
sys.path.append(op.dirname(__location__))   # print(sys.path)
# from babs.cli import babs_init_main
# sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "babs"))

# ++++++++++++++++++++++++++++++++++++++++++++++++
flag_instance = "toybidsapp"
type_session = "multi-ses"
list_sub_file = None    # "file" or None (without quotes!)

flag_where = "cubic"   # "cubic" or "local"
# ++++++++++++++++++++++++++++++++++++++++++++++++

# where:
if flag_where == "cubic":
    where_project = "/cbica/projects/BABS/data"
elif flag_where == "local":
    where_project = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data"
else:
    raise Exception("not valid `flag_where`!")

# initial included sub list:
if list_sub_file == "file":
    list_sub_file = "notebooks/initial_sub_list_" + type_session + ".csv"

# bids-app specific:
if flag_instance == "toybidsapp":
    if type_session == "multi-ses":
        input_ds = op.join(where_project, "w2nu3")
    elif type_session == "single-ses":
        input_ds = op.join(where_project, "t8urc")

    input_cli = [["BIDS", input_ds]]
    project_name = "test_babs_" + type_session + "_" + flag_instance
    bidsapp = "toybidsapp"
    container_name = bidsapp + "-0-0-5"

elif flag_instance == "zipped_toybidsapp":
    project_name = "test_babs_" + type_session + "_" + flag_instance
    bidsapp = "toybidsapp"
    if type_session == "multi-ses":
        input_cli = [["fmriprep", op.join(where_project, "k9zw2")]]   # fmriprep done, multi-ses
    elif type_session == "single-ses":
        # fmriprep done, single-ses  # also allows 'osf://2jvub/'
        input_cli = [["fmriprep", op.join(where_project, "2jvub")]]
    container_name = bidsapp + "-0-0-5"

elif flag_instance == "fmriprep":
    if type_session == "multi-ses":
        input_ds = op.join(where_project, "w2nu3")
    elif type_session == "single-ses":
        input_ds = op.join(where_project, "t8urc")

    input_cli = [["BIDS", input_ds]]
    project_name = "test_babs_" + type_session + "_fmriprep"
    bidsapp = "fmriprep"
    container_name = bidsapp + "-0-0-0"  # TODO: to change

elif flag_instance == "qsiprep":
    project_name = "test_babs_" + type_session + "_qsiprep"
    bidsapp = "qsiprep"
    if type_session == "multi-ses":
        input_ds = op.join(where_project, "w2nu3")
    elif type_session == "single-ses":
        input_ds = op.join(where_project, "t8urc")
    input_cli = [["BIDS", input_ds]]
    container_name = bidsapp + "-0-0-0"  # TODO: to change

elif flag_instance == "xcpd":
    project_name = "test_babs_" + type_session + "_xcpd"
    bidsapp = "xcpd"
    if type_session == "multi-ses":
        input_cli = [["fmriprep", op.join(where_project, "k9zw2")]]   # fmriprep, multi-ses
    elif type_session == "single-ses":
        input_cli = [["fmriprep", "osf://2jvub/"]]   # fmriprep, single-ses

    container_name = bidsapp + "-0-0-0"  # TODO: to change

elif flag_instance == "fmriprep_ingressed_fs":
    project_name = "test_babs_" + type_session + "_fpfsin"
    bidsapp = "fmriprep"
    if type_session == "multi-ses":
        input_cli = [["BIDS", op.join(where_project, "w2nu3")],   # bids, multi-ses
                     ["freesurfer", op.join(where_project, "k9zw2")]]   # fmriprep done, multi-ses
    elif type_session == "single-ses":
        input_cli = [["BIDS", op.join(where_project, "t8urc")],   # bids, single-ses
                     ["freesurfer", "osf://2jvub/"]]   # fmriprep done, single-ses
    container_name = bidsapp + "-0-0-0"  # TODO: to change

elif flag_instance == "empty":
    project_name = "test_babs_emptyInputds"
    bidsapp = "fmriprep"
    input_cli = [["empty", op.join(where_project, "empty_dataset")]]

else:
    raise Exception("not valid `flag_instance`!")


# container_ds:
if flag_where == "cubic":
    container_ds = op.join(where_project, bidsapp + "-container")
elif flag_where == "local":
    container_ds = op.join(where_project, "toybidsapp-container-docker")

container_config_yaml_file = "notebooks/example_container_" + flag_instance + ".yaml"

if os.getenv("TEMPLATEFLOW_HOME") is None:
    os.environ['TEMPLATEFLOW_HOME'] = '/templateflow_home_test'

# babs_init(where_project, project_name,
#           input=input_cli,
#           list_sub_file=list_sub_file,
#           container_ds=container_ds,
#           container_name=container_name,
#           container_config_yaml_file=container_config_yaml_file,
#           type_session=type_session,
#           type_system="sge")
babs_init_main()

print("")
