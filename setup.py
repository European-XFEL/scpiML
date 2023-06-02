#!/usr/bin/env python
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
from os.path import dirname, join, realpath

from setuptools import find_packages, setup

# local implementation of device_scm_version from karabo.packaging.versioning
# looks like: git describe --tags --match "*.*.*" --dirty --always
ROOT_FOLDER = dirname(realpath(__file__))
scm_version = lambda: {
    'root': ROOT_FOLDER,
    'write_to': join(ROOT_FOLDER, 'src', 'scpiml', '_version.py'),
    'local_scheme': lambda v: '-dirty' if v.dirty else '',
    'version_scheme': lambda v:
        f'{v.tag}-{v.distance}-{v.node}'.replace('-', '+', 1) if v.distance \
        else f'{v.tag}'.replace('-', '+', 1),
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
