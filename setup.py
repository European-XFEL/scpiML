#!/usr/bin/env python
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
from os.path import dirname, join, realpath

from setuptools import find_packages, setup

from karabo.packaging.versioning import device_scm_version

ROOT_FOLDER = dirname(realpath(__file__))
scm_version = device_scm_version(
    ROOT_FOLDER,
    join(ROOT_FOLDER, 'src', 'scpiml', '_version.py')
)

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
