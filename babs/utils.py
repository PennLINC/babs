""" Utils and helper functions """

import pkg_resources

def get_datalad_version():
    return pkg_resources.get_distribution('datalad').version