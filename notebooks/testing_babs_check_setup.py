from babs.cli import babs_check_setup_main
from babs.utils import read_yaml, write_yaml
import os.path as op
import pprint   # no need to install, provided by python

babs_check_setup_main()

# # Below is to test out `read_yaml` and `write_yaml`:
# folder = "/Users/chenyzh/Desktop/Research/Satterthwaite_Lab/datalad_wrapper/data/test_babs_multi-ses_toybidsapp/analysis/code"
# fn = op.join(folder, "babs_proj_config.yaml")
# config = read_yaml(fn, if_filelock=True)

# pprint.pprint(config, sort_dicts=False)

# fn_new = op.join(folder, "test.yaml")
# write_yaml(config, fn_new, if_filelock=True)
