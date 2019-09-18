from asyncio import (
    coroutine, get_event_loop, Lock, open_connection, Protocol, shield, sleep,
    StreamReader, StreamReaderProtocol, StreamWriter, TimeoutError, wait_for)
from itertools import chain
import os
import termios
import urllib

from karabo import middlelayer
from karabo.middlelayer import (
    AccessMode, Assignment, background, Device, Double, isSet, KaraboValue,
    State, String, Unit)


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


class BaseScpiDevice(Device):
    """Base Device Class for SCPI interface """

    # some devices might not require a read after a command or a write
    # set this class attribute to False in this case.
    readOnCommand = True

    url = String(
        displayedName="Instrument URL",
        description="""The URL of the instrument. Supported URL schemes are
            socket://hostname:port/ and file:///filename""",
        assignment=Assignment.MANDATORY,
        accessMode=AccessMode.INITONLY)

    timeout = Double(
        displayedName="Timeout",
        description="""The timeout on polling. If negative, the response
            will be waited forever.""",
        defaultValue=-1.,
        unitSymbol=Unit.SECOND,
        accessMode=AccessMode.INITONLY)

    def __init__(self, configuration):
        self.connected = False
        super().__init__(configuration)
        self.lock = Lock()
        self.allowLF = False

    @classmethod
    def register(cls, name, dict):
        super().register(name, dict)
        attrs = chain.from_iterable(c._attrs for c in cls.__mro__
                                    if issubclass(c, BaseScpiDevice))
        cls._scpiattrs = [a for a in attrs
                          if getattr(cls, a).alias is not None]
        for attr in cls._scpiattrs:
            descr = getattr(cls, attr)
            if "method" in descr.__dict__ or "setter" in descr.__dict__:
                continue  # the user already decorated a function
            descr(cls.sender(descr))

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

    async def sendCommand(self, descriptor, value=None):
        if not self.connected:
            return
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor
        cmd = self.createCommand(descriptor, value)
        read = self.readCommandResult(descriptor, value)
        if not self.readOnCommand:
            read = self.setResultNoRead(descriptor, value)
        newvalue = await self.writeread(
            cmd, read)
        if newvalue is not None:
            descriptor.__set__(self, newvalue)

    async def sendQuery(self, descriptor):
        if isinstance(descriptor, KaraboValue):
            descriptor = descriptor.descriptor
        q = self.createQuery(descriptor)
        value = await self.writeread(
            q, self.readQueryResult(descriptor))
        descriptor.__set__(self, value)

    command_format = "{alias} {value}\n"

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
    def setResultNoRead(self, descriptor, value=None):
        return value

    @coroutine
    def readCommandResult(self, descriptor, value=None):
        try:
            yield from self.readline()
            return value
        except TimeoutError:
            msg = "Timeout while waiting for reply to {} {}".format(
                descriptor.key, descriptor.alias)
            self.status = msg
            self.state = State.ERROR
            raise TimeoutError(msg)

    query_format = "{alias}?\n"

    def createQuery(self, descriptor):
        return (getattr(descriptor, "queryFormat", self.query_format)
                .format(alias=descriptor.alias, device=self))

    @coroutine
    def readQueryResult(self, descriptor):
        try:
            line = yield from self.readline()
            reply = line.decode("ascii")
            if reply:
                return self.parseResult(descriptor, line.decode("ascii"))
            else:
                return None
        except TimeoutError:
            self.status = "Timeout while waiting for reply to {}".format(
                descriptor.key)
            self.state = State.ERROR
            raise TimeoutError

    def parseResult(self, descriptor, line):
        return descriptor.fromstring(line)

    def data_arrived(self):
        """input data from a file (i.e., not a socket)"""
        d = self.writer.read(1)
        if self.writer.closed:
            self.reader.feed_eof()
        else:
            self.reader.feed_data(d)

    @coroutine
    def open_connection(self):
        url = urllib.parse.urlsplit(self.url)
        if url.scheme == "file":
            socket = open(
                url.path, "r+b", buffering=0,
                opener=lambda path, flag: os.open(path, flag | os.O_NONBLOCK))
            decodeURL(url, socket)
            self.reader = StreamReader()
            loop = get_event_loop()
            yield from loop.connect_read_pipe(
                lambda: StreamReaderProtocol(self.reader), socket)
            trans, proto = yield from loop.connect_write_pipe(Protocol, socket)
            self.writer = StreamWriter(trans, proto, self.reader, loop)
        elif url.scheme == "socket":
            self.reader, self.writer = yield from open_connection(
                url.hostname, url.port)
        else:
            raise ValueError("Unknown url scheme {}".format(url.scheme))

    @coroutine
    def connect(self):
        """Connect to the instrument"""
        yield from self.open_connection()
        self.state = State.NORMAL
        self.connected = True

        for k in self._scpiattrs:
            descriptor = getattr(self.__class__, k)
            if getattr(descriptor, "writeOnConnect",
                       descriptor.accessMode is AccessMode.INITONLY):
                value = getattr(self, k)
                if isSet(value):
                    yield from self.sendCommand(descriptor, value)
                else:
                    yield from self.sendQuery(descriptor)
            if getattr(descriptor, "readOnConnect", False):
                yield from self.sendQuery(descriptor)
            if getattr(descriptor, "poll", False):
                background(self.pollOne(descriptor))

    @coroutine
    def pollOne(self, descriptor):
        while True:
            logged = False
            try:
                yield from self.sendQuery(descriptor)
                yield from sleep(descriptor.poll)
            except TimeoutError:
                if not logged:
                    # log only once on timeout
                    msg = "Timeout while polling {}".format(descriptor.key)
                    self.status = msg
                    self.logger.error(msg)
                    logged = True

    @coroutine
    def readline(self):
        # if self.timeout is negative, wait indefinitely.
        timeout = None if self.timeout.value < 0 else self.timeout.value
        line = yield from wait_for(self._readline(), timeout=timeout)
        return line

    @coroutine
    def _readline(self):
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
        try:
            self.writer.close()
        except AttributeError:
            pass


class ScpiDevice(BaseScpiDevice):
    @middlelayer.Slot()
    @coroutine
    def connect(self):
        yield from super().connect()
