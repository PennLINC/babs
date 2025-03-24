import os.path as op

import yaml

from babs.utils import validate_queue


class System:
    """This class is for cluster management system"""

    def __init__(self, system_type):
        """
        This is to initialize System class.

        Parameters
        ----------
        system_type: str
            Type of the cluster management system.
            Options are: "sge" and "slurm"

        Attributes
        ----------
        type: str
            Type of the cluster management system.
            Options are: "sge" and "slurm"
        dict: dict
            Guidance dict (loaded from `dict_cluster_systems.yaml`)
            for how to run this type of cluster.
        """
        # validate and assign to attribute `type`:
        self.type = validate_queue(system_type)

        # get attribute `dict` - the guidance dict for how to run this type of cluster:
        self.get_dict()

    def get_dict(self):
        # location of current python script:
        #   `op.abspath()` is to make sure always returns abs path, regardless of python version
        #   ref: https://note.nkmk.me/en/python-script-file-path/
        __location__ = op.realpath(op.dirname(op.abspath(__file__)))

        fn_dict_cluster_systems_yaml = op.join(__location__, 'dict_cluster_systems.yaml')
        with open(fn_dict_cluster_systems_yaml) as f:
            dict = yaml.safe_load(f)
            # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`

        # sanity check:
        if self.type not in dict:
            raise Exception(
                "There is no key called '"
                + self.type
                + "' in"
                + ' file `dict_cluster_systems.yaml`!'
            )

        self.dict = dict[self.type]
        f.close()
