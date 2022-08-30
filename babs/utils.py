""" Utils and helper functions """

import os
import os.path as op
import pkg_resources

def get_datalad_version():
    return pkg_resources.get_distribution('datalad').version

def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]

def check_validity_input_dataset(input_ds_path, type_session = "single-ses"):
    """
    Check if the input dataset is valid. 
    * if it's multi-ses: subject + session should both appear
    * if it's single-ses: there should be sub folder, but no ses folder

    Parameters:
    ------------------
    input_ds_path: str
        path to the input dataset. It should be the one after it's cloned to `analysis` folder
    type_session: str
        multi-ses or single-ses

    Notes:
    -----------
    Tested with multi-ses and single-ses data; made sure that only single-ses data + type_session = "multi-ses" raise error.
    TODO: add above tests to pytests
    """

    if type_session not in ["multi-ses", "single-ses"]:
        raise Exception("invalid `type_session`!")

    is_valid_sublevel = False

    list_subs = get_immediate_subdirectories(input_ds_path)
    for sub_temp in list_subs:   # if one of the folder starts with "sub-", then it's fine
        if sub_temp[0:4] == "sub-":
            is_valid_sublevel = True
            break
    if not is_valid_sublevel:
        raise Exception("There is no `sub-*` folder in this input dataset: " + input_ds_path)

    if type_session == "multi-ses":
        for sub_temp in list_subs:   # every sub- folder should contain a session folder
            if sub_temp[0] == ".":   # hidden folder
                continue    # skip it
            is_valid_seslevel = False
            list_sess = get_immediate_subdirectories(op.join(input_ds_path, sub_temp))
            for ses_temp in list_sess:
                if ses_temp[0:4] == "ses-":   # if one of the folder starts with "ses-", then it's fine
                    is_valid_seslevel = True
                    break
                
            if not is_valid_seslevel:
                raise Exception("There is no `ses-*` folder in subject folder " + sub_temp)

def validate_type_session(type_session):

    if type_session in ['single-ses', 'single_ses', 'single-session', 'single_session']:
        type_session = "single-ses"
    elif type_session in ['multi-ses', 'multi_ses', 'multiple-ses', 'multiple_ses', 
                'multi-session', 'multi_session','multiple-session', 'multiple_session']:
        type_session = "multi-ses"
    else:
        print('`type_session = ' + type_session + '` is not allowed!')

    return type_session