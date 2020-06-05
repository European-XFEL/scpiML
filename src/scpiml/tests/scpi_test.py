from asyncio import StreamReader, StreamWriter, StreamReaderProtocol, WriteTransport, get_event_loop, sleep
from contextlib import contextmanager

from karabo.middlelayer import State, Double, AccessMode, getDevice, Device
from karabo.middlelayer_api.tests.eventloop import async_tst, DeviceTest
from scpiml import ScpiAutoDevice


class ManageDevice(WriteTransport):
    def __init__(self, cls):
        self.device = cls({"url": "test://example.com", "_deviceId_": "scpi"})
        self.device.reader = StreamReader()
        protocol = StreamReaderProtocol(self.device.reader)
        self.device.writer = StreamWriter(self, protocol, self.device.reader, get_event_loop())
        self.buf = []

    def write(self, data):
        self.buf.append(data)

    def close(self):
        pass

    def get_buffer(self):
        ret = b"".join(self.buf)
        self.buf = []
        return ret

    async def __aenter__(self):
        await self.device.startInstance()
        return self.device

    async def __aexit__(self, typ, value, tb):
        await self.device.slotKillDevice()

class Tests(DeviceTest):
    @classmethod
    @contextmanager
    def lifetimeManager(cls):
        client = Device({"_deviceId_": "client"})
        with cls.deviceManager(lead=client):
            yield

    @async_tst
    async def test_simple(self):
        class Simple(ScpiAutoDevice):
            pass

        manager = ManageDevice(Simple)
        async with manager as device:
            self.assertTrue(device.connected)
            self.assertEqual(device.state, State.NORMAL)
        self.assertEqual(manager.get_buffer(), b"")

    @async_tst
    async def test_simple_init(self):
        class Device(ScpiAutoDevice):
            initonly = Double(accessMode=AccessMode.INITONLY, alias="I", defaultValue=1)
            readonly = Double(accessMode=AccessMode.READONLY, alias="R")
            rw = Double(alias="RW")

        manager = ManageDevice(Device)
        async with manager as device:
            proxy = await getDevice("scpi")
            self.assertEqual(manager.get_buffer(), b"I 1.0\n")
            proxy.rw = 7
            device.reader.feed_data(b"\n\n\n     ")
            await sleep(0.1)
            self.assertEqual(manager.get_buffer(), b"RW 7.0\n")
