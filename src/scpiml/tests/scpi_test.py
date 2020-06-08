from asyncio import start_server, sleep, gather
from contextlib import contextmanager
from time import time

from karabo.middlelayer import State, Double, AccessMode, getDevice, Node, Device, Slot, waitUntilNew, background
from karabo.middlelayer_api.tests.eventloop import async_tst, DeviceTest
from scpiml import ScpiAutoDevice, ScpiConfigurable


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
            with proxy:
                proxy.rw = 7
                self.writer.write(b"\n")
                await self.assertRead(b"RW 7.0\n")
                self.writer.write(b"25\n\n")
                while proxy.rw != 7:
                    await sleep(0.001)

    @async_tst
    async def test_simple_woc(self):
        class Device(ScpiAutoDevice):
            initonly = Double(accessMode=AccessMode.INITONLY, alias="I", defaultValue=1)
            initonly.writeOnConnect = True
            readonly = Double(accessMode=AccessMode.READONLY, alias="R", defaultValue=2)
            readonly.writeOnConnect = True
            rw = Double(alias="RW", defaultValue=3)
            rw.writeOnConnect = True

        manager = ManageDevice(Device)
        async with manager as device:
            await self.assertRead(b"I 1.0\n")
            self.writer.write(b"5\n")
            await self.assertRead(b"R 2.0\n")
            self.writer.write(b"5\n")
            await self.assertRead(b"RW 3.0\n")
            self.writer.write(b"5\n")
            await sleep(0.02)

    @async_tst
    async def test_simple_roc(self):
        class Device(ScpiAutoDevice):
            readonly = Double(accessMode=AccessMode.READONLY, alias="R")
            readonly.readOnConnect = True
            rw = Double(alias="RW")
            rw.readOnConnect = True

        manager = ManageDevice(Device)
        async with manager as device:
            proxy = await getDevice("scpi")
            with proxy:
                await sleep(0.02)
                await self.assertRead(b"R?\n")
                self.writer.write(b"5\n")
                while proxy.readonly != 5:
                    await waitUntilNew(proxy.readonly)
                await self.assertRead(b"RW?\n")
                self.writer.write(b"7\n")
                while proxy.rw != 7:
                    await waitUntilNew(proxy.rw)

    @async_tst
    async def test_read_command(self):
        class Device(ScpiAutoDevice):
            initonly = Double(accessMode=AccessMode.INITONLY, alias="I", defaultValue=1)
            rw = Double(alias="RW")
            slot = Slot(alias="S")

            async def readCommandResult(self, descriptor, value):
                ret = await self.readline()
                if value is not None:
                    return float(ret)

        manager = ManageDevice(Device)
        async with manager as device:
            proxy = await getDevice("scpi")
            with proxy:
                await sleep(0.02)
                await self.assertRead(b"I 1.0\n")
                self.writer.write(b"5\n")
                while proxy.initonly != 5:
                    await waitUntilNew(proxy.initonly)
                proxy.rw = 6
                await self.assertRead(b"RW 6.0\n")
                self.writer.write(b"9\n")
                while proxy.rw != 9:
                    await waitUntilNew(proxy.rw)
                back = background(proxy.slot())
                await self.assertRead(b"S \n")
                await sleep(0.02)
                self.assertFalse(back.done(),
                                 "slot returned although we we sent nothing!")
                self.writer.write(b"this text should not matter\n")
                await back

    @async_tst
    async def test_readline(self):
        class Device(ScpiAutoDevice):
            rw = Double(alias="RW")
            rw.readOnConnect = True

            async def readline(self):
                ret = await self.reader.readuntil(b"E")
                return bytes(c for c in ret if c < ord("A"))
                

        manager = ManageDevice(Device)
        async with manager as device:
            proxy = await getDevice("scpi")
            with proxy:
                await sleep(0.02)
                await self.assertRead(b"RW?\n")
                self.writer.write(b"1letters2do3not4matterE")
                while proxy.rw != 1234:
                    await waitUntilNew(proxy.rw)

    @async_tst
    async def test_format(self):
        class Device(ScpiAutoDevice):
            rw = Double(alias="RW", defaultValue=1)
            rw.writeOnConnect = True
            rw_special = Double(alias="RWS", defaultValue=2)
            rw_special.commandFormat = "mayu {alias} {device.deviceId} {value}\n"
            rw_special.writeOnConnect = True
         
            readonly = Double(accessMode=AccessMode.READONLY, alias="R")
            readonly.readOnConnect = True
            readonly_special = Double(accessMode=AccessMode.READONLY, alias="RS")
            readonly_special.readOnConnect = True
            readonly_special.queryFormat = "rena {alias} {device.deviceId}\n"
            query_format = "yuki {alias} {device.deviceId}\n"
            command_format = "rino {alias} {device.deviceId} {value}\n"

        manager = ManageDevice(Device)
        async with manager as device:
            await self.assertRead(b"rino RW scpi 1.0\n")
            self.writer.write(b"7\n")
            await self.assertRead(b"mayu RWS scpi 2.0\n")
            self.writer.write(b"7\n")
            await self.assertRead(b"yuki R scpi\n")
            self.writer.write(b"7\n")
            await self.assertRead(b"rena RS scpi\n")
            self.writer.write(b"7\n")
            await sleep(0.01)

    @async_tst
    async def test_poll(self):
        class Device(ScpiAutoDevice):
            readonly = Double(accessMode=AccessMode.READONLY, alias="R")
            readonly.poll = 0.001

        manager = ManageDevice(Device)
        async with manager as device:
            proxy = await getDevice("scpi")
            with proxy:
                await sleep(0.02)
                t0 = time()
                for i in range(10):
                    await self.assertRead(b"R?\n")
                    self.writer.write(f"{i}\n".encode("ascii"))
                    while proxy.readonly != i:
                        await waitUntilNew(proxy.readonly)
                t1 = time()
            self.assertLess(t1 - t0, 0.05)
            self.assertGreater(t1 - t0, 0.01)

    @async_tst
    async def test_node(self):
        class Channel(ScpiConfigurable):
            initonly = Double(accessMode=AccessMode.INITONLY, alias="I", defaultValue=1)
            readonly = Double(accessMode=AccessMode.READONLY, alias="R")
            readonly.poll = 0.01
            rw = Double(alias="RW")
            rw.readOnConnect = True

        class Device(ScpiAutoDevice):
            node = Node(Channel, alias="yuko")

            def createChildQuery(self, descr, child):
                 return f"{child.alias}.{descr.alias}?\n"

            def createChildCommand(self, descr, value, child):
                 return f"{child.alias}.{descr.alias} {value.value}\n"

        manager = ManageDevice(Device)
        async with manager as device:
            proxy = await getDevice("scpi")
            with proxy:
                await sleep(0.02)
                await self.assertRead(b"yuko.I 1.0\n")
                self.writer.write(b"\n")
                await self.assertRead(b"yuko.RW?\n")
                self.writer.write(b"7\n")
                await self.assertRead(b"yuko.R?\n")
                self.writer.write(b"8\n")
                await self.assertRead(b"yuko.R?\n")

                self.assertEqual(proxy.node.rw, 7)
                self.assertEqual(proxy.node.readonly, 8)
