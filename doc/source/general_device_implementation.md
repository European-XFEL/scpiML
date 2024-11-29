# GENERAL IMPLEMENTATION GUIDE


## Requirements

-  To successfully implement and integrate a high voltage device using the SCPI protocol, the following documentations and resources are required.

1. Device Manual
-  The device manual provides detailed information about the specific device.
-  It includes hardware specifications, operational modes, safety guidelines, and detailed instructions on how to interact with the device.

2. SCPI Programmers Guide
-  The SCPI Programmers Guide provides an understanding of the SCPI protocol, which is essential for programming and controlling the device.
-  It includes the syntax and structure of SCPI commands.
-  instructions on managing and responding to errors.

3. EIR Document
-  The EIR Document provides information about the requirements and functionalities to be implemented.


## General Implementation Steps

1. Gather Requirements and Documentation.
2. Set Up the Development Environment.
   -  Ensure that the required packages like *scpiml* are installed.
   -  Create a new middle-layer device for the implementation.
      -  *karabo* *new* <*newDevice*> *middlelayer*
3. Implement the code for the device.
   -  Define the class structure : *ScpiAutoDevice* and *ScpiConfigurable*.
   -  Define SCPI commands and Query Format by referring SCPI programmers Guide.
   -  Implement the requirements by referring EIR Documents.
   -  Develop a scene for the device.


## writeOnConnect versus readOnConnect

-  When setting up attributes that communicate with hardware devices using SCPI protocol, *writeOnConnect* and *readOnConnect* are parameters used to control how these attributes are initialized or synchronized when a connection to a device is established.

-  *writeOnConnect*
   -  Specifies that the attribute’s value should be sent (written) to the device immediately upon connection.
   -  This parameter is used when you want the device to start with a specific configuration as soon as it connects.
   -  For example, If the voltage on a power supply channel to be set to a predetermined value every time the device connects, set *writeOnConnect* for the voltage attribute.

-  *ReadOnConnect*
   -  Specifies that the attribute’s value should be read from the device immediately upon connection.
   -  It retrieves the current value from the device, useful for attributes that represent the device’s actual state.


## How to Poll

-  When setting up this parameter, it continuously check the status of a device such as voltage levels or error states at regular intervals.
-  For example, if the current parameter is to be polled, set *poll* for the current attribute.
