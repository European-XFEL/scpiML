"""A base class for SCPI-like devices

SCPI is a standard command set for programmable instruments. Many controllers
with a command port (be it serial, USB or Ethernet) claim to adhere to this
standard, while most actually do not.

This Karabo device is very flexible in that it can be modified to communicate
with many controllers, whether they claim to follow SCPI or not.
"""
from asyncio import (
    get_event_loop, Lock, open_connection, Protocol, shield, sleep,
    StreamReader, StreamReaderProtocol, StreamWriter, TimeoutError, wait_for)
from itertools import chain
import os
import termios
import urllib

from karabo import middlelayer
from karabo.middlelayer import (
    AccessMode, Assignment, background, Configurable,
    Device, Double, isSet, KaraboValue, Node, State, String,
    Unit)
try:
    # Karabo >= 2.11
    from karabo.middlelayer import string_from_hashtype
    use_descriptor = False
except ImportError:
    # Karabo <= 2.10
    use_descriptor = True

if not hasattr(Configurable, "get_root"):
    # Karabo < 2.13
    from karabo.native.schema.descriptors import get_instance_parent
    has_get_root = False
else:
    has_get_root = True


def decodeURL(url, handle):
    strings = dict(
        bits={"6": (termios.CS6, 2), "7": (termios.CS7, 2),
              "8": (termios.CS8, 2)},
        stopbits={"1": (0, 0), "2": (termios.CSTOPB, 2)},
        parity={"none": (0, 0), "odd": (termios.PARENB | termios.PARODD, 2),
                "even": (termios.PARENB, 2)},
        flow={"software": (termios.IXOFF, 0), "off": (0, 0)},
        onl={"nl": (0, 0), "crnl": (termios.ONLCR, 1)})
    mask = [0, 0, 0]
    for v in strings.values():
        for t, n in v.values():
            mask[n] |= t
    ios = termios.tcgetattr(handle)
    ios[4] = ios[5] = termios.B9600
    for i, n in enumerate(mask):
        ios[i] &= ~n
    d = dict(bits="8", stopbits="1", parity="none", flow="off")
    if url.query:
        d.update(s.split("=") for s in url.query.split("&"))
    for k, v in d.items():
        if k == "speed":
            ios[4] = ios[5] = getattr(termios, "B" + v)
        else:
            t, n = strings[k][v]
            ios[n] |= t
    termios.tcsetattr(handle, termios.TCSANOW, ios)


class ScpiConfigurable(Configurable):
    parent = None
    connected = None

    @classmethod
    def register(cls, name, dict):
        super().register(name, dict)
        attrs = chain.from_iterable(c._attrs for c in cls.__mro__
                                    if issubclass(c, ScpiConfigurable))
        cls._scpiattrs = [a for a in attrs
                          if getattr(cls, a).alias is not None]
        for attr in cls._scpiattrs:
            descr = getattr(cls, attr)
            if ("method" in descr.__dict__ or "setter" in descr.__dict__
                    or isinstance(descr, Node)):
                continue  # the user already decorated a function
            setattr(cls, attr, descr(cls.sender(descr)))

    def get_root(self):
        if has_get_root:
            return super().get_root()
        else:
            return get_instance_parent(self)

    @classmethod
    def sender(cls, descr):
        async def sc(self, value=None):
            root = self.get_root()
            if root.connected:
                return (await root.sendCommand(descr, value, self))
            else:
                setattr(self, descr.key, value)
        return sc

    async def connect(self, parent):
        self.parent = parent
        self.connected = parent.connected
        await self.onConnect()
        for k in self._scpiattrs:
            descriptor = getattr(self.__class__, k)
            if isinstance(descriptor, Node):
                value = getattr(self, k)
                value.alias = descriptor.alias
                await value.connect(self)
                continue

            if getattr(descriptor, "writeOnConnect",
                       descriptor.accessMode is AccessMode.INITONLY):
                value = getattr(self, k)
                if isSet(value):
                    await self.parent.sendCommand(descriptor, value, self)
                else:
                    await self.parent.sendQuery(descriptor, self)
            if getattr(descriptor, "readOnConnect", False):
                await self.parent.sendQuery(descriptor, self)
            if getattr(descriptor, "poll", False):
                background(self.parent.pollOne(descriptor, self))

    async def onConnect(self):
        """ can be implemented in the derived class """

    async def sendCommand(self, descriptor, value=None, child=None):
        """send a command out

        This method creates a command using `createChildCommand` and reads back
        its result using `readCommandResult`, and may then immediately query
        the value if `commandReadBack` is set.

        This is the method where locking takes place, which may become
        complicated. You should reimplement this method only if you really
        know what you are doing, otherwise better reimplement the methods
        mentioned above.

        You may, however, call this method to your likings. But be aware not to
        do this from within the methods just mentioned, as this would destroy
        the locking mechanism.
        """
        if not self.connected:
            return
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor
        cmd = self.createChildCommand(descriptor, value, child)
        newvalue = await self.get_root().writeread(
            cmd, self.readCommandResult(descriptor, value))
        if newvalue is not None:
            child = self if child is None else child
            descriptor.__set__(child, newvalue)
        elif (getattr(descriptor, "commandReadBack", self.commandReadBack)
              and value is not None):
            await self.sendQuery(descriptor, child)

    async def sendQuery(self, descriptor, child=None):
        """send a query out

        This method creates a query using `createChildQuery` and read its
        results using `readQueryResult`.

        The same caveats for usage and reimplementation apply as for
        `sendCommand`.
        """
        if not self.connected:
            return
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor
        q = self.createChildQuery(descriptor, child)
        value = await self.get_root().writeread(
            q, self.readQueryResult(descriptor))
        child = self if child is None else child
        descriptor.__set__(child, value)

    command_format = "{alias} {value}\n"
    commandReadBack = False

    # do not use the following line, it is legacy.
    readOnCommand = True

    def createChildCommand(self, descriptor, value=None, child=None):
        """create a command

        return the command string used to set the value for `descriptor`
        in `child`.  child is `None` or `self` if we are querying for the
        device. `value` is `None` for Slots, and contains the value to be
        set for all other parameters.

        Often all you need to do is to set the class variable `command_format`,
        which uses the Python format method to format the string, to define
        how a query is build. You may even define query formats on a
        per-descriptor basis, as in::

            specialInput = Double()
            specialInput.commandFormat = "SET super special {alias}!\n"

        In the query formats, *alias* represents the descriptor's alias,
        while *device* refers to the device this method is called for,
        and {value} is the value to be set. Note that {value} is set to
        be the empty string for Slots, which is what is needed in most
        cases.
        """
        if child is None or child is self:
            return self.createCommand(descriptor, value)
        return self.createNodeCommand(descriptor, value, child)

    def createNodeCommand(self, leaf, value, node):
        """Implement this in the derived class if nodes are needed

        Parameters:
            leaf: the descriptor of the leaf inside the node
            value: the KaraboValue of the property leaf that will be applied
                   or command to be set
            node: the descriptor of the node

        One can implement this interface as such::

            class SourceChannel(ScpiConfigurable):
                offset = Double(
                    displayedName='Voltage Offset',
                    alias="VOLT:OFFS",
                    unitSymbol=Unit.VOLT
                )

            class NodedDevice(ScpiAutoDevice):
                source1 = Node(SourceChannel, alias="SOURce1")

                def createNodeQuery(self, leaf, node):
                    return f"{node.alias}:{leaf.alias}?\n"

                def createNodeCommand(self, leaf, value, node):
                    return f"{node.alias}:{leaf.alias} {value.value}\n"

        The query and command for the property `source1.offset` will be::

            "SOURce1:VOLT:OFFS?\n"
            "SOURce1:VOLT:OFFS VALUE\n"

        for nested nodes, the `createNodeQuery` and `createNodeCommand` need
        to be implemented in the nodes as well. Depending on the syntax needed
        by the hardware, one can generalize by subclassing `ScpiConfigurable`
        as in::

            class FormatNode(ScpiConfigurable):
                def get_prefix(self):
                    if self == self.parent:
                        return ""
                    return f"{self.alias}."

                def createNodeQuery(self, leaf, node):
                    return f"{self.get_prefix()}{node.alias}:{leaf.alias}?\n"

                def createNodeCommand(self, leaf, value, node):
                    prefix = self.get_prefix()
                    return f"{prefix}{node.alias}:{leaf.alias} {value.value}\n"


            class VoltChannel(FormatNode):
                offset = Double(
                    displayedName='Voltage Offset',
                    alias="OFFS",
                    unitSymbol=Unit.VOLT
                )


            class SourceChannel(FormatNode):
                volt = Node(SourceChannel, alias="VOLT")


            class NodedDevice(FormatNode, ScpiAutoDevice):
                source1 = Node(SourceChannel, alias="SOURce1")

        The query and command for the property `source1.volt.offset` will be::

            "SOURce1:VOLT:OFFS?\n"
            "SOURce1:VOLT:OFFS VALUE\n"

        """
        raise NotImplementedError(
            "default implementation does not handle children"
        )

    def createCommand(self, descriptor, value=None):
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor

        if value is None:
            string_var = ""
        else:
            if use_descriptor:
                string_var = descriptor.toString(
                    descriptor.toKaraboValue(value).value)
            else:
                string_var = string_from_hashtype(
                    descriptor.toKaraboValue(value).value)
        return (getattr(descriptor, "commandFormat", self.command_format)
                .format(alias=descriptor.alias,
                        device=self,
                        value=string_var))

    async def readCommandResult(self, descriptor, value=None):
        """read the result of a command and return it

        Unfortunately, there is no generally accepted way on what to retur
        for a command. The default implementation reads one line, ignores it
        and returns the *value*.

        A command may be the setting of a value to *value*, or it may be
        the calling of a slot, in which case *value* is *None*.

        Some devices do not return anything at all, in which case you may
        find it best to write::

            async def readCommandResult(self, descriptor, value):
                return value

        Others return the same way as they return for queries::

            async def readCommandResult(self, descriptor, value):
                if value is not None:
                    return (await self.readQueryResult(descriptor))

        Often devices do not return anything useful, instead one wishes to
        read back the parameter with a query after each setting. This
        can be achieved by setting the `commandReadBack` attribute either
        globally or per descriptor.
        """
        if not self.readOnCommand:
            return value
        try:
            await self.get_root().readline()
            return value
        except TimeoutError:
            msg = "Timeout while waiting for reply to {} {}".format(
                descriptor.key, descriptor.alias)
            self.status = msg
            self.state = State.ERROR
            raise TimeoutError(msg)

    query_format = "{alias}?\n"

    def createChildQuery(self, descriptor, child=None):
        """creates a query

        return the query used to query for `descriptor` in `child`.
        child is `None` or `self` if we are querying for the device.

        Often all you need to do is to set the class variable `query_format`,
        which uses the Python format method to format the string, to define
        how a query is build. You may even define query formats on a
        per-descriptor basis, as in::

            specialInput = Double()
            specialInput.queryFormat = "GET super special {alias}!\n"

        In the query formats, *alias* represents the descriptor's alias,
        while *device* refers to the device this method is called for.
        """
        if child is None or child is self:
            return self.createQuery(descriptor)
        return self.createNodeQuery(descriptor, child)

    def createNodeQuery(self, leaf, node):
        """Implement this in the derived class if nodes are needed

        Parameters:
            leaf: the descriptor of the leaf inside the node
            node: the descriptor of the node

        see: inline documentation for `createNodeCommand`
        """
        raise NotImplementedError(
            "default implementation does not handle children"
        )

    def createQuery(self, descriptor):
        return (getattr(descriptor, "queryFormat", self.query_format)
                .format(alias=descriptor.alias, device=self))

    async def readQueryResult(self, descriptor):
        """Read the result from a query

        The default implementation reads one line, parses it and returns the
        result. Unless you need to do some complicated handshaking, you
        should rather reimplement `parseResult` if all you need is to have
        some advanced parsing of the returned string.
        """
        try:
            line = await self.get_root().readline()
            reply = line.decode("ascii", errors='ignore')
            if reply:
                return self.parseResult(descriptor, line.decode("ascii", errors='ignore'))
            else:
                return None
        except TimeoutError:
            self.status = "Timeout while waiting for reply to {}".format(
                descriptor.key)
            self.state = State.ERROR
            raise TimeoutError

    async def pollOne(self, descriptor, child):
        communication_timeout = False
        while True:
            try:
                await self.sendQuery(descriptor, child)
                if descriptor.poll is True:
                    sleep_time = self.pollingInterval.value
                else:
                    assert descriptor.poll > 0, \
                        "polling interval must be positive"
                    sleep_time = descriptor.poll
                await sleep(sleep_time)
                if communication_timeout:  # readout recovered
                    self.status = ""
                    communication_timeout = False
            except TimeoutError:
                if not communication_timeout:
                    # log only once on timeout
                    msg = "Timeout while polling {}".format(descriptor.key)
                    self.status = msg
                    self.logger.error(msg)
                    communication_timeout = True

    def parseResult(self, descriptor, line):
        """Parse the data returned from a query

        given the string in line and a descriptor, return the value this
        should correspond to. The default implementation is good a parsing
        the standard data types, but if the device encodes data weirdly,
        you may want to reimplement this method.

        As an example, if the device returned integers encoded in hex,
        you may write::

            def parseResult(self, descriptor, line):
                return int(line, base=16)
        """
        return descriptor.fromstring(line)


class BaseScpiDevice(ScpiConfigurable, Device):
    """Base Device Class for SCPI interface """

    url = String(
        displayedName="Instrument URL",
        description="""The URL of the instrument. Supported URL schemes are
            socket://hostname:port/ and file:///filename""",
        assignment=Assignment.MANDATORY,
        accessMode=AccessMode.INITONLY)

    timeout = Double(
        displayedName="Timeout",
        description="""Max time to wait for an answer to a command/query.
            If negative, the response will be waited for forever. Devices
            whose protocol foresee commands w/o answer will not work with
            negative timeouts! """,
        defaultValue=1.,
        unitSymbol=Unit.SECOND,
        accessMode=AccessMode.INITONLY)

    pollingInterval = Double(
        displayedName="Polling Interval",
        description="The minimum polling interval to be used for parameters "
                    "that do not have an hard-coded one.",
        defaultValue=1.,
        unitSymbol=Unit.SECOND,
        minInc=0.05,
        maxInc=30.)

    def __init__(self, configuration):
        self.connected = False
        super().__init__(configuration)
        self.lock = Lock()
        self.allowLF = False

    def writeread(self, write, read):
        write = write.encode('utf8')

        async def inner():
            async with self.lock:
                self.writer.write(write)
                return (await read)

        return shield(inner())

    def data_arrived(self):
        """input data from a file (i.e., not a socket)"""
        d = self.writer.read(1)
        if self.writer.closed:
            self.reader.feed_eof()
        else:
            self.reader.feed_data(d)

    async def open_connection(self):
        """Connect to the instrument"""
        url = urllib.parse.urlsplit(self.url)
        if url.scheme == "file":
            socket = open(
                url.path, "r+b", buffering=0,
                opener=lambda path, flag: os.open(path, flag | os.O_NONBLOCK))
            decodeURL(url, socket)
            self.reader = StreamReader()
            loop = get_event_loop()
            await loop.connect_read_pipe(
                lambda: StreamReaderProtocol(self.reader), socket)
            trans, proto = await loop.connect_write_pipe(Protocol, socket)
            self.writer = StreamWriter(trans, proto, self.reader, loop)
        elif url.scheme == "socket":
            self.reader, self.writer = await open_connection(
                url.hostname, url.port)
        else:
            raise ValueError("Unknown url scheme {}".format(url.scheme))

    async def close_connection(self):
        self.writer.close()
        await self.writer.wait_closed()
        self.connected = False

    async def connect(self):
        """Connect to the instrument"""
        await self.open_connection()
        self.state = State.NORMAL
        self.connected = True
        await super().connect(self)

    async def readline(self):
        """Read one input line

        This reads one line from the input. A pretty flexible definition of a
        line is used, it may end in a carriage return, a line feed, or both,
        or in a byte 0. This method returns a bytes string excluding the
        end-of-line character found.

        If your device has an incompatible line ending definition, reimplement
        this method. As an example, if your device sends ETX as a line ending,
        you may write::

            async def readline(self):
                ret = await self.reader.readuntil(b"\3")  # this is ETX
                return ret[:-1]

        Any kind of filtering also may be done here, as an example on could
        filter out all special characters::

            async def readline(self):
                ret = await self.reader.readuntil(b"\n")
                return bytes(ch for ch in ret if ch >= ord(" "))
        """
        # if self.timeout is negative, wait indefinitely.
        timeout = None if self.timeout.value < 0 else self.timeout.value
        line = await wait_for(self._readline(), timeout=timeout)

        return line

    async def _readline(self):
        line = []

        while True:
            c = await self.readChar()
            if self.allowLF and c == b"\n":
                self.allowLF = False
            elif c in b"\n\r\0":
                if c == b"\r":
                    self.allowLF = True
                return b"".join(line)
            else:
                line.append(c)

    async def readChar(self):
        try:
            return (await self.reader.read(1))
        except ConnectionError:
            await self.close_connection()
            return


class ScpiAutoDevice(BaseScpiDevice):
    """A ScpiDevice that automatically connects"""
    async def _run(self, **kwargs):
        await super()._run(**kwargs)
        background(self.connect())

    async def onDestruction(self):
        try:
            self.writer.close()
        except AttributeError:
            pass


class ScpiDevice(BaseScpiDevice):
    @middlelayer.Slot()
    async def connect(self):
        await super().connect()
