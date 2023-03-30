import os
import os.path as op
import sys
import pprint   # no need to install, provided by python

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "babs"))
from babs.cli import babs_check_setup_main   # noqa
from babs.utils import read_yaml, write_yaml   # noqa
from babs.cli import babs_init_main  # noqa
from babs.babs import BABS, Input_ds   # noqa

# babs_init_main()
babs_check_setup_main()


# Below is to test out `clean_up()`: --------------------
# project_root = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data/test_babs_multi-ses_toybidsapp"
# type_session = "multi-ses"
# type_system = "sge"
# input_cli = [["BIDS", "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data/w2nu3"]]

# babs_proj = BABS(project_root, type_session, type_system)
# input_ds = Input_ds(input_cli)

# babs_proj.clean_up(input_ds)


# # Below is to test out `read_yaml` and `write_yaml`:  --------
# folder = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data/test_babs_multi-ses_toybidsapp/analysis/code"
# fn = op.join(folder, "babs_proj_config.yaml")
# config = read_yaml(fn, if_filelock=True)

# pprint.pprint(config, sort_dicts=False)

# fn_new = op.join(folder, "test.yaml")
# write_yaml(config, fn_new, if_filelock=True)
