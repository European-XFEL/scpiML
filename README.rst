***********************************
ScpiML Device (MiddleLayer)
***********************************

This device provides a base class for any device that uses SCPI-compliant protocol to communicate. 
Karabo devices that inherit from this base class can easily implement karabo properties and then use the property's alias to define the corresponding SCPI command. Methods in this base class can be redefined/overriden to make it work with various communication protocols that are SCPI-like but not strictly compliant.
It supports connections via ethernet, serial, or USB.


Testing
=======

Every Karabo device in Python is shipped as a regular python package.
In order to make the device visible to any device-server you have to install
the package to Karabo's own Python environment.

Simply type:

``pip install -e .``

in the directory of where the ``setup.py`` file is located, or use the ``karabo``
utility script:

``karabo develop scpiML``

Running
=======

If you want to manually start a server using this device, simply type:

``karabo-middlelayerserver serverId=middleLayerServer/1 deviceClasses=ScpiML``

Or just use (a properly configured):

``karabo-start``

Contact
========

For questions, please contact opensource@xfel.eu.


License and Contributing
=========================

This software is released by the European XFEL GmbH as is and without any
warranty under the GPLv3 license.
If you have questions on contributing to the project, please get in touch at
opensource@xfel.eu.

External contributors, i.e. anyone not contractually associated to
the European XFEL GmbH, are asked to sign a Contributor License
Agreement (CLA):

- people contributing as individuals should sign the Individual CLA
- people contributing on behalf of an organization should sign 
  the Entity CLA.

The CLAs can be found in the `contributor_license_agreement.md` and
`entity_contributor_license_agreement.md` documents located in
the root folder of this repository. 
Please send signed CLAs to opensource [at] xfel.eu. We'll get in
touch with you then. 
We ask for your understanding that we cannot accept external 
contributions without a CLA in place. Importantly, with signing the CLA
you acknowledge that

* European XFEL retains all copyrights of the Karabo Image Processor,
* European XFEL may relicense the Karabo Image Processor under other 
  appropriate open source licenses which the Free Software Foundation 
  classifies as Free Software licenses. 

However, you are welcome to already 
suggest modifications you'd like to contribute by opening a merge/pull 
request before you send the CLA.

You are free to use this software under the terms of the GPLv3 without signing a CLA.
