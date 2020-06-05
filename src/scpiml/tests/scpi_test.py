from asyncio import start_server, sleep
from contextlib import contextmanager

from karabo.middlelayer import State, Double, AccessMode, getDevice, Device
from karabo.middlelayer_api.tests.eventloop import async_tst, DeviceTest
from scpiml import ScpiAutoDevice


class ManageDevice:
    def __init__(self, cls):
        self.device = cls({"url": "socket://localhost:35232", "_deviceId_": "scpi"})

    async def __aenter__(self):
        await self.device.startInstance()
        while not self.device.connected:
            await sleep(0.001)
        return self.device

    async def __aexit__(self, typ, value, tb):
        await self.device.slotKillDevice()

class Tests(DeviceTest):
    @classmethod
    @contextmanager
    def lifetimeManager(cls):
        client = Device({"_deviceId_": "client"})
        cls.server = cls.loop.run_until_complete(
            start_server(cls.connected_cb, "localhost", 35232))
        with cls.deviceManager(lead=client):
            yield

    @classmethod
    def connected_cb(cls, reader, writer):
        cls.reader = reader
        cls.writer = writer

    async def assertEnd(self, device):
        device.writer.write(b"THE END")
        sentinel = await self.reader.readexactly(7)
        self.assertEqual(sentinel, b"THE END")

    async def assertRead(self, data, until=b"\n"):
        read = await self.reader.readuntil(until)
        self.assertEqual(read, data)

    def tearDown(self):
        self.assertTrue(self.reader.at_eof())

    @async_tst
    async def test_simple(self):
        class Simple(ScpiAutoDevice):
            pass

        manager = ManageDevice(Simple)
        async with manager as device:
            self.assertTrue(device.connected)
            self.assertEqual(device.state, State.NORMAL)
            self.assertFalse(self.reader.at_eof())

    @async_tst
    async def test_simple_init(self):
        class Device(ScpiAutoDevice):
            initonly = Double(accessMode=AccessMode.INITONLY, alias="I", defaultValue=1)
            readonly = Double(accessMode=AccessMode.READONLY, alias="R")
            rw = Double(alias="RW")

        manager = ManageDevice(Device)
        async with manager as device:
            proxy = await getDevice("scpi")
            await self.assertRead(b"I 1.0\n")
            proxy.rw = 7
            self.writer.write(b"\n")
            await self.assertRead(b"RW 7.0\n")
