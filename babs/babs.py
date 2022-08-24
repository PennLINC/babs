# This is the main module.

import os
import os.path as op
import datalad.api as dlapi
import pandas as pd

class babs(object):
    """The babs class is for babs projects of BIDS Apps"""

    def __init__(self, project_root, type_session, system):
        '''
        Parameters
        ------------
        project_root: str
            absolute path to the root of this babs project
        type_session: str
            whether the input dataset is "multi-ses" or "single-ses"
        system: str
            the job scheduling system, "sge" or "slurm"
        '''

        self.project_root = project_root
        self.type_session = type_session
        self.system = system


    def babs_bootstrap(self, input_ds_pd, container_ds):
        """
        Bootstrap a babs project: initialize datalad-tracked RIAs, generate scripts to be used, etc
        """

        print("")

        # Initialize: TODO

        # Bootstrap scripts: TODO

        # Clean up: TODO
