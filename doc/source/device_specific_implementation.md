# AN EXAMPLE OF DEVICE SPECIFIC IMPLEMENTATION

-  The device package can be found [here](https://git.xfel.eu/karabodevices3/isegshrhvpowersupply)
-  This is a walk-through of the implementation of a high voltage power supply device using the SCPI protocol.


## Requirements

1. Device Manual
2. SCPI Programmers Guide for the device
3. EIR Document


## Imports

-  *scpiml* provides the classes *ScpiAutoDevice* and *ScpiConfigurable* for handling SCPI communication.
-  *karabo.middlelayer* is a part of Karabo framework which includes several utilities like data types, device states, nodes, slots etc.


## Class Structure and Inheritance

-  *IsegShrHvPowerSupply* Class
   -  Inherits from *ScpiAutoDevice*, which is a base class for devices that communicate using SCPI commands.
-  *HvChannel* Class
   -  Nested within *IsegShrHvPowerSupply*, this class represents individual channels of the power supply.
   -  It inherits from *ScpiConfigurable*, which allows each channel to be configured via SCPI commands.
-  *Node* Class
   -  A concept in Karabo framework used to represent and manage device channels as part of the *IsegShrHvPowerSupply* class.


## Initialization and Connection

-  The constructor of the parent class *ScpiAutoDevice* is called to initialize the device with provided configuration.
-  *onIntialization* method is executed when the device starts. This method can be used to define actions to be executed after instantiation.


## SCPI Command and Query Formats

-  *query_format* and *command_format*
   -  Define the standard format strings used for constructing SCPI queries and commands for the device.
   -  The command format can be found in the ‘SCPI Programmers Guide’.

-  *commandReadBack*
   -  This parameter indicates whether the command’s effect should be read back from the device to ensure it was executed correctly.
   -  *commandReadBack* = *True* sets the parameter.


## Channel Class

-  The class *HVChannel* class represents a single high-voltage channel.
-  Each instance of this class defines the attributes to control and monitor key parameters such as voltage, current etc.
-  The parameters to be implemented can be found in the ‘EIR’ document.
-  *Key Attributes in brief:*

   1. Target Voltage
   -  Represents the target voltage for the channel which is a *Double* value.
   -  *displayedName* parameter sets the name that is typically visualized in GUI.
   -  *description* helps the users understand that this parameter is used to set the desires voltage for the channel in volts.
   -  *alias* defines the SCPI command that corresponds to this attribute. The command for the attribute can be found in ‘SCPI Programmers Guide’.
   -  *unitSymbol* specifies the unit of measurement for this attribute.
   -  The attribute can be set to *writeOnConnect* or *readOnConnect* according to the requirement of the attribute.

   2. Actual Voltage
   -  Reads the actual voltage from the channel, using the *READ:VOLT*  SCPI command.
   -  Set to *READONLY* and marked for polling, meaning it will be regularly queried.

   3. Polarity
   -  Controls the output polarity of the channel via the *CONF:OUTPUT:POL* SCPI command.
   -  The *options* parameter is defined with two values ( n, p ) so that this attribute can be set to either *p* or *n*.


## Parsing Methods

-  The channel class includes several parsing methods to convert the responses from the device into standard data types.
-  The parse methods are re-implemented for each attribute so that it parses the specific data type of the attribute.
   -  Example: *parse_voltage*
         -  Takes a string argument containing the numeric voltage value followed by the character ‘V’.
         -  This string is typically the raw response from the high-voltage device when voltage value is queried using SCPI command.
         -  The method returns the floating-point representation of the voltage.
         -  Assigning *parse_voltage* to *actualVoltage.fromstring*, it is telling the *actualVoltage* attribute to use this parsing method whenever it needs interpret a string response from thendevice.


## Node Class

-  The *Node* class instance represent a channel of the high-voltage device.
-  For each channel of the power supply, an instance of *Node* is created, which contains channel instance.
-  Each *Node* encapsulates the channel class attributes to control and monitor each channel.


## Re-implementation of Methods

-  The base class has simple implementation that might not fit all device-specific requirements.
-  *createNodeQuery* and *createNodeCommand* are methods re-implemented from the base class.
-  They are re-implemented to accommodate the unique command or query syntax of the specific device.