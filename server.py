# https://gist.github.com/bsergean/bad452fa543ec7df6b7fd496696b2cd8
import asyncio
import logging.handlers
import os
from queue import SimpleQueue
from typing import Any

import coloredlogs
import websockets
from websockets import WebSocketServerProtocol

# Server settings
HOST = "0.0.0.0"
PORT = "8675"

# Client settings
REMOTE_URL = "wss://websocket-echo.com"


log = logging.getLogger("main")


async def proxy(local_ws: WebSocketServerProtocol, path: str) -> None:
    """Proxy a connection to a server.

    Sends a dummy message to fix libcurl.
    https://github.com/curl/curl/issues/11402
    """
    log.info(
        'New connection from %s:%s on path "%s"', *local_ws.remote_address[:2], path
    )

    # Send dummy message
    await local_ws.send("deadbeef")

    # Create proxy connection
    url = REMOTE_URL + path
    async with websockets.connect(url) as remote_ws:
        producer = asyncio.create_task(proxy_client_to_remote(local_ws, remote_ws))
        consumer = asyncio.create_task(proxy_remote_to_client(local_ws, remote_ws))

        done, pending = await asyncio.wait(
            [producer, consumer], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()

    # Connection closed
    log.info(
        "Connection from %s:%s closed with code %d (%s)",
        *local_ws.remote_address[:2],
        local_ws.close_code,
        local_ws.close_reason or "*No Reason Provided*",
    )


async def proxy_client_to_remote(
    local_ws: WebSocketServerProtocol, remote_ws: WebSocketServerProtocol
) -> None:
    """Proxy client messages to the remote."""
    async for message in local_ws:
        log.debug(
            'Message received from client %s:%s for remote: "%s"',
            *local_ws.remote_address[:2],
            message,
        )
        await remote_ws.send(message)


async def proxy_remote_to_client(
    local_ws: WebSocketServerProtocol, remote_ws: WebSocketServerProtocol
) -> None:
    """Proxy remote messages to the client."""
    async for message in remote_ws:
        log.debug(
            'Message received from remote for client %s:%s: "%s"',
            *local_ws.remote_address[:2],
            message,
        )
        await local_ws.send(message)


async def start_server() -> None:
    """Start server."""
    log.info("Starting server")
    async with websockets.serve(proxy, HOST, PORT):
        await asyncio.Future()  # run forever


###############################################################################


class LocalQueueHandler(logging.handlers.QueueHandler):
    def emit(self, record: logging.LogRecord) -> None:
        # Removed the call to self.prepare(), handle task cancellation
        try:
            self.enqueue(record)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.handleError(record)


def setup_logs() -> None:
    """Initialize loggers."""
    # Initialize logging
    coloredlogs.install(
        level=os.getenv("RACCOON_PROXY_LOG_LEVEL", "INFO"),
        fmt=(
            "%(asctime)s | %(name)-17s | %(levelname)-7s | %(message)s"
            "\t[%(funcName)s:%(lineno)d]"
        ),
    )

    # Set up queue logger
    # https://www.zopatista.com/python/2019/05/11/asyncio-logging/
    log_queue = SimpleQueue[Any]()
    root = logging.getLogger()

    # Add input handler
    handler = LocalQueueHandler(log_queue)
    root.addHandler(handler)

    # Save previous root handlers
    handlers: list[logging.Handler] = []

    for h in root.handlers[:]:
        if h is not handler:
            root.removeHandler(h)
            handlers.append(h)

    # Start queue listener
    listener = logging.handlers.QueueListener(
        log_queue, *handlers, respect_handler_level=True
    )
    listener.start()

    # Notify
    log.info("Logging initialized")


def main() -> None:
    setup_logs()

    # Start server
    try:
        # use uvloop
        import uvloop  # type: ignore

        loop_factory = uvloop.new_event_loop
        log.info("Using uvloop for a faster event loop")
    except ImportError:
        # no uvloop
        loop_factory = asyncio.new_event_loop
        log.warning("Using default event loop, install uvloop for better performance")

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        server_task = start_server()
        runner.run(server_task)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
