# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
from asyncio import sleep, start_server
from time import time

import pytest
import pytest_asyncio

from karabo.middlelayer import (
    AccessMode, Double, Node, Slot, State, background, connectDevice,
    waitUntil)
from karabo.middlelayer.testing import AsyncDeviceContext
from scpiml import ScpiAutoDevice, ScpiConfigurable


class DeviceServer:
    def __init__(self):
        self.server = None
        self.reader = None
        self.writer = None

    async def start(self):
        self.server = await start_server(
            self.connected_cb, "127.0.0.1", 35232)

    async def connected_cb(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def assertRead(self, data, until=b"\n"):
        read = await self.reader.readuntil(until)
        assert read == data

    async def stop(self):
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        self.server.close()
        await self.server.wait_closed()


@pytest_asyncio.fixture(loop_scope="module")
async def device_factory():
    DEVICE_CONFIG = {"url": "socket://127.0.0.1:35232", "deviceId": "scpi"}
    server = DeviceServer()
    await server.start()
    await sleep(0.1)

    def create_context(device_cls):
        device = device_cls(DEVICE_CONFIG)
        return AsyncDeviceContext(
            device=device
            )
    yield create_context, server

    await server.stop()


class Simple(ScpiAutoDevice):
    pass


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_simple(device_factory):
    create_ctx, _ = device_factory

    async with create_ctx(Simple) as ctx:
        device = ctx["device"]
        await connectDevice(device.deviceId)
        assert device.connected
        assert device.state == State.NORMAL
        assert not device.reader.at_eof()


class DeviceInit(ScpiAutoDevice):
    initonly = Double(
        accessMode=AccessMode.INITONLY,
        alias="I",
        defaultValue=1)
    readonly = Double(
        accessMode=AccessMode.READONLY,
        alias="R")
    rw = Double(alias="RW")


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_simple_init(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceInit) as ctx:
        device = ctx["device"]
        dev_proxy = await connectDevice(device.deviceId)

        await server.assertRead(b"I 1.0\n")

        dev_proxy.rw = 7
        server.writer.write(b"\n")
        await server.assertRead(b"RW 7.0\n")
        server.writer.write(b"25\n\n")
        await waitUntil(lambda: dev_proxy.rw == 7)


class DeviceWoC(ScpiAutoDevice):
    initonly = Double(
        accessMode=AccessMode.INITONLY,
        alias="I",
        defaultValue=1)
    initonly.writeOnConnect = True
    readonly = Double(
        accessMode=AccessMode.READONLY,
        alias="R",
        defaultValue=2)
    readonly.writeOnConnect = True
    rw = Double(alias="RW", defaultValue=3)
    rw.writeOnConnect = True


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_simple_woc(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceWoC) as ctx:
        device = ctx["device"]
        await connectDevice(device.deviceId)
        await server.assertRead(b"I 1.0\n")
        server.writer.write(b"5\n")
        await server.assertRead(b"R 2.0\n")
        server.writer.write(b"5\n")
        await server.assertRead(b"RW 3.0\n")
        server.writer.write(b"5\n")
        await sleep(0.02)


class DeviceRoC(ScpiAutoDevice):
    readonly = Double(accessMode=AccessMode.READONLY, alias="R")
    readonly.readOnConnect = True
    rw = Double(alias="RW")
    rw.readOnConnect = True


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_simple_roc(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceRoC) as ctx:
        device = ctx["device"]
        dev_proxy = await connectDevice(device.deviceId)
        await server.assertRead(b"R?\n")
        server.writer.write(b"5\n")
        await waitUntil(lambda: dev_proxy.readonly == 5)
        await server.assertRead(b"RW?\n")
        server.writer.write(b"7\n")
        await waitUntil(lambda: dev_proxy.rw == 7)


class DeviceReadCommand(ScpiAutoDevice):
    initonly = Double(
        accessMode=AccessMode.INITONLY,
        alias="I",
        defaultValue=1)
    rw = Double(alias="RW")
    slot = Slot(alias="S")

    async def readCommandResult(self, descriptor, value):
        ret = await self.readline()
        if value is not None:
            return float(ret)


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_read_command(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceReadCommand) as ctx:
        device = ctx["device"]
        dev_proxy = await connectDevice(device.deviceId)
        await server.assertRead(b"I 1.0\n")
        server.writer.write(b"5\n")
        await waitUntil(lambda: dev_proxy.initonly == 5)
        dev_proxy.rw = 6
        await server.assertRead(b"RW 6.0\n")
        server.writer.write(b"9\n")
        await waitUntil(lambda: dev_proxy.rw == 9)
        back = background(dev_proxy.slot())
        await server.assertRead(b"S \n")
        await sleep(0.02)
        assert not back.done(), \
            "slot returned although we sent nothing!"
        server.writer.write(b"this text should not matter\n")
        await back


class DeviceReadLine(ScpiAutoDevice):
    rw = Double(alias="RW")
    rw.readOnConnect = True

    async def readline(self):
        ret = await self.reader.readuntil(b"E")
        return bytes(c for c in ret if c < ord("A"))


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_readline(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceReadLine) as ctx:
        device = ctx["device"]
        dev_proxy = await connectDevice(device.deviceId)
        await server.assertRead(b"RW?\n")
        server.writer.write(b"1letters2do3not4matterE")
        await waitUntil(lambda: dev_proxy.rw == 1234)


class DeviceFormat(ScpiAutoDevice):
    rw = Double(alias="RW", defaultValue=1)
    rw.writeOnConnect = True
    rw_special = Double(alias="RWS", defaultValue=2)
    rw_special.commandFormat = (
        "mayu {alias} {device.deviceId} {value}\n")
    rw_special.writeOnConnect = True

    readonly = Double(
        accessMode=AccessMode.READONLY,
        alias="R")
    readonly.readOnConnect = True
    readonly_special = Double(
        accessMode=AccessMode.READONLY,
        alias="RS")
    readonly_special.readOnConnect = True
    readonly_special.queryFormat = "rena {alias} {device.deviceId}\n"
    query_format = "yuki {alias} {device.deviceId}\n"
    command_format = "rino {alias} {device.deviceId} {value}\n"


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_format(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceFormat) as ctx:
        device = ctx["device"]

        await connectDevice(device.deviceId)
        await server.assertRead(b"rino RW scpi 1.0\n")
        server.writer.write(b"7\n")
        await server.assertRead(b"mayu RWS scpi 2.0\n")
        server.writer.write(b"7\n")
        await server.assertRead(b"yuki R scpi\n")
        server.writer.write(b"7\n")
        await server.assertRead(b"rena RS scpi\n")
        server.writer.write(b"7\n")
        await sleep(0.01)


class DevicePoll(ScpiAutoDevice):
    readonly = Double(accessMode=AccessMode.READONLY, alias="R")
    readonly.poll = 0.001


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_poll(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DevicePoll) as ctx:
        device = ctx["device"]
        dev_proxy = await connectDevice(device.deviceId)
        t0 = time()
        for i in range(10):
            await server.assertRead(b"R?\n")
            server.writer.write(f"{i}\n".encode("ascii"))
            await waitUntil(lambda: dev_proxy.readonly == i)
        t1 = time()
        await server.assertRead(b"R?\n")
        assert (t1 - t0) < 0.05
        assert (t1 - t0) > 0.01


class ChannelNode(ScpiConfigurable):
    initonly = Double(
        accessMode=AccessMode.INITONLY,
        alias="I",
        defaultValue=1)
    readonly = Double(
        accessMode=AccessMode.READONLY,
        alias="R")
    readonly.poll = 0.01
    rw = Double(alias="RW")
    rw.readOnConnect = True


class DeviceNode(ScpiAutoDevice):
    node = Node(ChannelNode, alias="yuko")

    parentProp = Double(alias="PARENT_RW")
    parentProp.readOnConnect = True

    def createNodeQuery(self, leaf, node):
        return f"{node.alias}.{leaf.alias}?\n"

    def createNodeCommand(self, leaf, value, node):
        return f"{node.alias}.{leaf.alias} {value.value}\n"


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_node(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceNode) as ctx:
        device = ctx["device"]
        dev_proxy = await connectDevice(device.deviceId)
        await server.assertRead(b"yuko.I 1.0\n")
        server.writer.write(b"\n")
        await server.assertRead(b"yuko.RW?\n")
        server.writer.write(b"7\n")
        await server.assertRead(b"yuko.R?\n")
        server.writer.write(b"8\n")
        await server.assertRead(b"PARENT_RW?\n")
        server.writer.write(b"-1\n")
        await waitUntil(lambda: dev_proxy.parentProp == -1)
        assert dev_proxy.parentProp == -1
        assert dev_proxy.node.initonly == 1
        assert dev_proxy.node.rw == 7
        assert dev_proxy.node.readonly == 8


class FormatNode(ScpiConfigurable):
    def get_prefix(self):
        if self == self.parent:
            return ""
        return f"{self.alias}."

    def createNodeQuery(self, leaf, node):
        return f"{self.get_prefix()}{node.alias}.{leaf.alias}?\n"

    def createNodeCommand(self, leaf, value, node):
        return (
            f"{self.get_prefix()}{node.alias}.{leaf.alias} "
            f"{value.value}\n")


class SubChannelNestedNode(FormatNode):
    initonly = Double(
        accessMode=AccessMode.INITONLY,
        alias="I",
        defaultValue=1)
    readonly = Double(
        accessMode=AccessMode.READONLY,
        alias="R")
    readonly.poll = 0.01
    rw = Double(alias="RW")
    rw.readOnConnect = True


class ChannelNestedNode(FormatNode):
    subnode = Node(SubChannelNestedNode, alias="souschef")
    initonly = Double(
        accessMode=AccessMode.INITONLY,
        alias="I",
        defaultValue=2)
    readonly = Double(accessMode=AccessMode.READONLY, alias="R")
    readonly.poll = 0.01
    rw = Double(alias="RW")
    rw.readOnConnect = True


class DeviceNestedNode(FormatNode, ScpiAutoDevice):
    node = Node(ChannelNestedNode, alias="chef")

    parentProp = Double(alias="PARENT_RW")
    parentProp.readOnConnect = True


@pytest.mark.timeout(30)
@pytest.mark.asyncio(loop_scope="module")
async def test_nested_node(device_factory):
    create_ctx, server = device_factory

    async with create_ctx(DeviceNestedNode) as ctx:
        device = ctx["device"]
        dev_proxy = await connectDevice(device.deviceId)
        await server.assertRead(b"chef.souschef.I 1.0\n")
        server.writer.write(b"\n")
        await server.assertRead(b"chef.souschef.RW?\n")
        server.writer.write(b"7\n")
        await server.assertRead(b"chef.souschef.R?\n")
        server.writer.write(b"8\n")
        await server.assertRead(b"chef.I 2.0\n")
        server.writer.write(b"\n")
        await server.assertRead(b"chef.RW?\n")
        server.writer.write(b"9\n")
        await server.assertRead(b"chef.R?\n")
        server.writer.write(b"10\n")
        await server.assertRead(b"PARENT_RW?\n")
        server.writer.write(b"-1\n")
        await waitUntil(lambda: dev_proxy.parentProp == -1)
        assert dev_proxy.parentProp == -1
        assert dev_proxy.node.subnode.initonly == 1
        assert dev_proxy.node.subnode.rw == 7
        assert dev_proxy.node.subnode.readonly == 8
        assert dev_proxy.node.initonly == 2
        assert dev_proxy.node.rw == 9
        assert dev_proxy.node.readonly == 10
