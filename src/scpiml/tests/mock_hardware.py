# Provides a mock server that can be used for testing scpiml devices
# To use it import the mock_server
# from scpiml.tests.mock_hardware import mock_server
# and fill a dictionary with the specific
# query/response pairs for the device under test, e.g.:
# RESPONSES = {
#     '*IDN?': "SRS,DG645",
#     '*ESR?': 2,
# }
# The first entry should match what your device sends, the second what you
# want the server to answer.
# You also need define the separator used by the DUT, e.g.:
# SEPARATOR = b"\n"
#
# To use it your tests it could look like this:

# @pytest_asyncio.fixture()
# async def interface():
#     async with mock_server(Keithley2470, RESPONSES, SEPARATOR) as hw_device:
#         hw_server, ctx = hw_device
#         device = ctx["device"]
#         proxy = await connectDevice(device.deviceId)
#         yield proxy, device, hw_server
#
# @pytest.mark.timeout(30)
# @pytest.mark.asyncio
# async def test_init(interface: interface):
#     proxy, _, server = interface
#     assert server.is_connected.is_set()
#
# For examples refer to the keithleyMultimeters package.

from asyncio import (
    Event, IncompleteReadError, Queue, create_task, start_server)
from contextlib import asynccontextmanager
from socket import AddressFamily

from karabo.middlelayer.testing import AsyncDeviceContext


class MockHardware:

    def __init__(self, responses, separator):
        self.reader = None
        self.writer = None
        self.consume_task = None
        self.port = None
        self.responses = responses
        self.separator = separator
        self.side_effects = dict()
        self.queue = Queue()
        self.is_connected = Event()
        self.running = Event()

    async def serve(self):
        server = await start_server(
            self.connectionHandler, port=0)
        ports = [
            sock.getsockname()[1]
            for sock in server.sockets
            if sock.family == AddressFamily.AF_INET
        ]
        assert len(ports) == 1
        self.port = ports[0]
        async with server:
            self.running.set()
            await server.serve_forever()
        self.running.clear()
        self.is_connected.clear()
        self.port = None

    def connectionHandler(self, reader, writer):
        if self.is_connected.is_set():
            raise RuntimeError("Already connected!")
        self.reader = reader
        self.writer = writer
        self.is_connected.set()
        self.consume_task = create_task(self.listen())

    def on_input(self, pattern, side_effect):
        # side effect should be an async definition
        self.side_effects[pattern] = side_effect

    async def write(self, data):
        data = f"{data}".encode("ascii") + self.separator
        self.writer.write(data)
        await self.writer.drain()

    async def listen(self):
        try:
            while True:
                next_item = await self.reader.readuntil(self.separator)
                result = next_item[:(-1 * len(self.separator))]
                result = result.decode()
                if (response := self.responses.get(result)) is not None:
                    await self.write(str(response))
                elif (side_effect := self.side_effects.pop(result, None)) is \
                        not None:
                    await side_effect
                else:
                    await self.queue.put(result)
        except (ConnectionResetError, IncompleteReadError):
            pass
        except Exception as e:
            print(e)
            raise e
        finally:
            self.is_connected.clear()


@asynccontextmanager
async def mock_server(cls, responses, separator, config=None):
    server = MockHardware(responses, separator)
    server_task = create_task(server.serve())
    await server.running.wait()
    port = server.port
    conf = {
        "deviceId": f"MOCKSPIML_{cls.__name__}",
        "measurementPollInterval": 2,
        "pollingInterval": 5,
        "url": f"socket://127.0.0.1:{port}",
    }
    if config is not None:
        conf.update(**config)
    device = cls(conf)
    async with AsyncDeviceContext(device=device) as ctx:
        yield server, ctx
    server_task.cancel()
