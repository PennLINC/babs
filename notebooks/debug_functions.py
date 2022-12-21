import sys
import os
import os.path as op
import pandas as pd

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
sys.path.append(op.dirname(__location__))   # print(sys.path)
from babs.utils import report_job_status, read_job_status_csv

analysis_path = "/cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis"
fn_csv = op.join(analysis_path, "code/job_status.csv")
df = read_job_status_csv(fn_csv)

report_job_status(df, analysis_path)
