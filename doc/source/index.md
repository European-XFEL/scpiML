# Introduction - SCPI

This overview provides a step-by-step guide to implement code for controlling a SCPI device. The guide covers the necessary concepts and provides detailed explanation of the relevant classes and functions, the device-specific implementation (specifically a high-voltage power supply).  


## SCPI (Standard Commands for Programmable Instruments)

-  SCPI or Standard Commands for Programmable Instruments, is a standardized language for controlling and programming instruments.
-  SCPI commands are ASCII textual strings, which are sent to the instrument over any physical layer such as USB, serial ports, Ethernet etc.
-  These commands are used to configure, control, and retrieve data from instruments such as power supplies, oscilloscopes, and signal generators.
-  For a general overview of SCPI protocol see the [Wikipedia](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) reference.

## Key Concepts

-  SCPI commands to an instrument may either perform a command (e.g. setting a value or switching a device on) or a query (e.g. reading a value or the status of a device).
-  A command is often composed of a command mnemonic followed by parameters.
-  Queries (or query commands) are used to request information from the device.
-  Queries are issued to an instrument by appending a question-mark to the end of a command.
-  While SCPI aims for standardization, many devices implement SCPI in slightly different ways, necessitating custom implementations for different devices.


## Chapter Overview

The following sections describe in detail, the concepts and implementation:

   - [scpiML Package Reference](https://git.xfel.eu/karabodevices3/scpiml/-/blob/add/doc/doc/source/scpi_ml_package.md) - Explains the usage of the scpiML package, detailing classes, methods and their roles in managing SCPI-devices
   - [How to Implement a SCPI Device](https://git.xfel.eu/karabodevices3/scpiml/-/blob/add/doc/doc/source/general_device_implementation.md) - Provides general steps to follow for the implementation of SCPI-device.
   - [An Example of Device-Specific Implementation](https://git.xfel.eu/karabodevices3/scpiml/-/blob/add/doc/doc/source/device_specific_implementation.md) - Provides SCPI implementation for High-Voltage device, including class structure, SCPI command formats, and customization of base methods.


