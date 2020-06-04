from asyncio import (
    coroutine, get_event_loop, Lock, open_connection, Protocol, shield, sleep,
    StreamReader, StreamReaderProtocol, StreamWriter)
from itertools import chain
import os
import termios
import urllib

from karabo import middlelayer
from karabo.middlelayer import (
    AccessMode, Assignment, background, Configurable,
    Device, isSet, KaraboValue, Node, State, String)


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

    @classmethod
    def sender(cls, descr):
        async def sc(self, value=None):
            if self.parent is not None and self.parent.connected:
                return (await self.parent.sendCommand(descr, value, self))
        return sc

    async def connect(self, parent):
        self.parent = parent
        for k in self._scpiattrs:
            descriptor = getattr(self.__class__, k)
            if isinstance(descriptor, Node):
                value = getattr(self, k)
                value.alias = descriptor.alias
                await value.connect(parent)
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


class BaseScpiDevice(ScpiConfigurable, Device):
    url = String(
        displayedName="Instrument URL",
        description="""The URL of the instrument. Supported URL schemes are
            socket://hostname:port/ and file:///filename""",
        assignment=Assignment.MANDATORY,
        accessMode=AccessMode.INITONLY)

    def __init__(self, configuration):
        self.connected = False
        super().__init__(configuration)
        self.lock = Lock()
        self.allowLF = False

    @classmethod
    def sender(cls, descr):
        @coroutine
        def sc(self, value=None):
            if self.connected:
                return (yield from self.sendCommand(descr, value))
        return sc

    def writeread(self, write, read):
        write = write.encode('utf8')

        async def inner():
            async with self.lock:
               self.writer.write(write)
               return (await read)

        return shield(inner())

    async def sendCommand(self, descriptor, value=None, child=None):
        if not self.connected:
            return
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor
        cmd = self.createChildCommand(descriptor, value, child)
        newvalue = await self.writeread(
            cmd, self.readCommandResult(descriptor, value))
        if newvalue is not None:
            descriptor.__set__(self if child is None else child, newvalue)
        elif (getattr(descriptor, "commandReadBack", self.commandReadBack)
              and value is not None):
            await self.sendQuery(descriptor, child)

    async def sendQuery(self, descriptor, child=None):
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor
        q = self.createChildQuery(descriptor, child)
        value = await self.writeread(
            q, self.readQueryResult(descriptor))
        descriptor.__set__(self if child is None else child, value)

    command_format = "{alias} {value}\n"
    commandReadBack = False

    def createChildCommand(self, descriptor, value=None, child=None):
        assert child is None or child is self, "default implementation does not handle children"
        return self.createCommand(descriptor, value)

    def createCommand(self, descriptor, value=None):
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor
        return (getattr(descriptor, "commandFormat", self.command_format)
                .format(alias=descriptor.alias,
                        device=self,
                        value="" if value is None
                        else descriptor.toString(
                            descriptor.toKaraboValue(value).value)))

    @coroutine
    def readCommandResult(self, descriptor, value=None):
        yield from self.readline()
        return value

    query_format = "{alias}?\n"

    def createChildQuery(self, descriptor, child=None):
        assert child is None or child is self, "default implementation does not handle children"
        return self.createQuery(descriptor)

    def createQuery(self, descriptor):
        return (getattr(descriptor, "queryFormat", self.query_format)
                .format(alias=descriptor.alias, device=self))

    @coroutine
    def readQueryResult(self, descriptor):
        line = yield from self.readline()
        return self.parseResult(descriptor, line.decode("ascii"))

    def parseResult(self, descriptor, line):
        return descriptor.fromstring(line)

    def data_arrived(self):
        """input data from a file (i.e., not a socket)"""
        d = self.writer.read(1)
        if self.writer.closed:
            self.reader.feed_eof()
        else:
            self.reader.feed_data(d)

    async def connect(self):
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
        self.state = State.NORMAL
        self.connected = True
        await super().connect(self)

    @coroutine
    def pollOne(self, descriptor, child):
        while True:
            yield from self.sendQuery(descriptor, child)
            yield from sleep(descriptor.poll)

    @coroutine
    def readline(self):
        line = []

        while True:
            c = yield from self.readChar()
            if self.allowLF and c == b"\n":
                self.allowLF = False
            elif c in b"\n\r\0":
                if c == b"\r":
                    self.allowLF = True
                return b"".join(line)
            else:
                line.append(c)

    @coroutine
    def readChar(self):
        return (yield from self.reader.read(1))


class ScpiAutoDevice(BaseScpiDevice):
    @coroutine
    def _run(self, **kwargs):
        yield from super()._run(**kwargs)
        yield from self.connect()

    @coroutine
    def onDestruction(self):
        self.writer.close()


class ScpiDevice(BaseScpiDevice):
    @middlelayer.Slot()
    @coroutine
    def connect(self):
        yield from super().connect()
