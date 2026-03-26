# SCPIML karabo Package

-  The scpiML package can be found [here](https://git.xfel.eu/karabodevices3/scpiml)
-  In order to make the device visible to any device-server, install the package to Karabo’s own Python environment.
-  After having installed and activated Karabo [see here](https://karabo.pages.xfel.eu/Framework/installation/binary.html), use the karabo utility script: *karabo develop scpiML*.


## Base Class Overview

1. ScpiConfigurable

-  It is the base class for SCPI-device nodes. It enables communication and control using SCPI commands.
-  This base class shall be extended to create device-specific implementations, handling setup, command execution and error management.

2. ScpiAutoDevice

-  It is the base class the final device should inherit, which manage the connection lifecycle automatically.
-  It automatically attempts to connect to the hardware device when it is run and ensures that connections are properly closed when the device is destroyed.

3. ScpiDevice

-  This class provides a structured way to initiate the SCPI connection asynchronously.


## Key Terminology

-  *descriptor*: It describes the karabo device parameter associated to a SCPI command or query to be sent to the device.
-  *node*: The descriptor of a node. A node encompasses multiple parameters, and is typically used to represent a channel for multi-channel devices such as e.g. a power supply.
-  *leaf*: The descriptor of the leaf inside the node, i.e. a parameter inside a node.
-  *value*: The karaboValue of the property leaf that will be applied or command to be set.
-  *result*: This parameter stores and processes the response returned by the SCPI device after a query.


## ScpiConfigurable Useful Methods

-  *sendCommand*: This method calls *createChildCommand* to create a command string, writes it to the device and reads back the result using *readCommandResult*. It may then immediately query the value if *commandReadBack* is set.
-  *sendQuery*: This method creates a query using *createChildQuery*, writes it to the device and reads its results using *readQueryresult*.
-  *createChildCommand*: This method returns the command string used to set the value for *descriptor* in child.
   -  If child is *None* or *self* it means that the query is for the device. 
-  *createCommand*: returns the formatted command string.
-  *createChildQuery*: This method returns the query used to query for *descriptor* in child.
-  *createNodeCommand*: This method returns a formatted command string for a node.
   -  Must be implemented in the derives class if nodes are needed.
-  *createNodeQuery*: This method returns a formatted query string for a node.
   -  Must be implemented in the derives class if nodes are needed.
-  *parseResult*: This method parse the data returned from a query.
   -  It can be overridden in the base class if the device use a non-standard format.
-  *scpi_data_encoder*: A device may require that SCPI commands or queries are encapsulated in a custom vendor-defined protocol. This method can be used to custom encode queries or commands, before they are sent to the device.
   -  It can be overridden in the derived class if the device uses vendor-specific protocol.
-  *scpi_data_decoder*: A device may respond to received commands or queries in an encoded response format. This method can be used to custom decode SCPI responses from the device.
   -  It can be overridden in the derived class if the device requires custom response decoding.
   
## BaseScpiDevice Useful Methods

-  *writeread*: This method sends a command to the instrument, then waits for and reads the response. The command is encoded in UTF-8 before being sent.
-  *data_arrived*: This method handles incoming data when the device is being read from a file rather a socket.
-  *open_connection*: This method opens a connection to the instrument based on the provided URL. 
-  *close_connection*: This methods closes the connection to the instrument, if one is open.
-  *connect*: This method attempts to establish a connection to the instrument.
   -  It calls *open_connection* and handles potential errors like "ConnectionRefusedError", "ValueError" etc.
-  *disconnect*: This method closes the connection to the instrument.
   -  It calls *close_connection*.
-  *readline*: This method reads one line of input from the device. it handles various line endings (carriage return, line feed, or both, or null byte) and returns the line as a byte string, excluding the line ending.
   -  It can be overridden if the device uses a different line-ending character.


## Workflow for a Command

1. The *sendCommand* method is invoked with the provided descriptor and value.
2. If the command is associated with a child node in the device, it will call *createChildCommand*.
3. *createChildCommand* method calls *createNodeCommand* with the child’s alias.
4. *createNodeCommand* returns the command string by combining node’s alias with the command specified by the descriptor.
5. The *sendCommand* sends the returned command string to the instrument.
6. After sending the command, the *sendCommand* method awaits a response by calling *readCommandResult*.
7. If *commandReadBack* is enabled, a query is sent to confirm the command was processed correctly.
8. After response, the corresponding attributes are updated accordingly.


## Workflow for a Query

1. The *sendQuery* method is invoked with the provided descriptor and optional child node.
2. If the query is associated with a child node in the device, it will call *createChildQuery*.
3. *createChildQuery* method calls *createNodeQuery* with the child’s alias.
4. *createNodeQuery* combines the node’s alias to produce the final query string.
5. The *sendQuery* method sends the returned query string to the instrument.
6. After sending the query, the *sendQuery* method awaits a response by calling *readQueryResult*.
7. The *readQueryResult* method reads the response from the instrument.
8. The *parseResult* method is called to extract the value corresponding to the descriptor.
