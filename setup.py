#!/usr/bin/env python
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
from os.path import dirname, join, realpath

from setuptools import find_packages, setup

# local implementation of device_scm_version from karabo.packaging.versioning
ROOT_FOLDER = dirname(realpath(__file__))
scm_version = lambda: {
    'local_scheme': lambda v:
        f'{v.distance}-{v.node}-dirty' if v.dirty else f'{v.distance}-{v.node}',
    'version_scheme': lambda v:
        f'{v.tag}+' if '-' not in str(v.tag) else f'{v.tag}'.replace('-', '+', 1),
    'root': ROOT_FOLDER,
    'write_to': join(ROOT_FOLDER, 'src', 'scpiml', '_version.py'),
}

setup(name='scpiML',
      use_scm_version=scm_version,
      author='David Hickin',
      author_email='david.hickin@xfel.eu',
      description='',
      long_description='',
      url='',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      entry_points={},
      package_data={},
      requires=[],
      )
