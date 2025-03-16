#!/usr/bin/env python3
"""Script to download test datasets for BABS testing"""

import os
import os.path as op

import datalad.api as dlapi
import yaml


def download_datasets():
    """Download all test datasets specified in origin_input_dataset.yaml"""
    # Read the yaml file
    yaml_path = op.join(op.dirname(op.abspath(__file__)), 'origin_input_dataset.yaml')
    with open(yaml_path) as f:
        datasets = yaml.safe_load(f)

    base_dir = '/home/circleci/test_data'
    os.makedirs(base_dir, exist_ok=True)

    # Download each dataset
    for dataset_type, sessions in datasets.items():
        for session_type, url in sessions.items():
            target_dir = op.join(base_dir, f'{dataset_type}_{session_type}')
            print(f'Downloading {dataset_type} {session_type} from {url} to {target_dir}')
            dlapi.clone(source=url, path=target_dir)


if __name__ == '__main__':
    download_datasets()
