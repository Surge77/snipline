"""Single-instance enforcement over a local socket.

Two copies of a screenshot tool is never what anyone wants: both would fight over the same
hotkey, and the second registration would fail, leaving a running app whose hotkey silently
belongs to a different process.

So the first launch owns a named local server; later launches connect to it, send a command,
and exit. ``QLocalServer`` is a named pipe on Windows -- no ports, no network, nothing that
D11 would object to.

The stale-socket case is handled explicitly: if the previous process was killed rather than
closed, the server name stays claimed and every future launch would otherwise refuse to
start, which turns one crash into a permanently broken installation.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

__all__ = ["CAPTURE_COMMAND", "SingleInstance"]

CAPTURE_COMMAND = b"capture\n"

# Long enough to cross a loaded machine, short enough that a stale pipe does not make the
# app look hung on launch.
_CONNECT_TIMEOUT_MS = 500
_WRITE_TIMEOUT_MS = 1000
_POLL_INTERVAL_MS = 20


class SingleInstance(QObject):
    """Owns the instance lock, or talks to whoever does."""

    command_received = Signal(bytes)

    def __init__(self, server_name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server_name = server_name
        self._server: QLocalServer | None = None

    @property
    def is_primary(self) -> bool:
        return self._server is not None

    def try_become_primary(self) -> bool:
        """Claim the instance lock. False means another instance already holds it."""
        if self._server is not None:
            return True

        if self._ping_existing():
            return False

        server = QLocalServer(self)
        # Nothing answered the ping, so any surviving name belongs to a process that died
        # without cleaning up. Removing it is what stops one crash from permanently
        # blocking every future launch.
        QLocalServer.removeServer(self._server_name)

        if not server.listen(self._server_name):
            server.deleteLater()
            return False

        server.newConnection.connect(self._on_connection)
        self._server = server
        return True

    def _ping_existing(self) -> bool:
        """Is a live instance listening on this name?"""
        socket = QLocalSocket()
        socket.connectToServer(self._server_name)
        connected = socket.waitForConnected(_CONNECT_TIMEOUT_MS)
        socket.abort()
        return connected

    def send_command(self, command: bytes = CAPTURE_COMMAND) -> bool:
        """Hand a command to the running instance. False if nothing is listening."""
        socket = QLocalSocket(self)
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
            socket.deleteLater()
            return False

        socket.write(command)
        socket.flush()

        # Block until the bytes have actually left, because the caller is typically about
        # to exit the process and a still-buffered command would simply be lost.
        #
        # waitForBytesWritten alone is not enough. The primary drains the pipe only when
        # its own event loop runs, and when both instances share a thread -- as they do
        # under test -- that loop cannot run while this call blocks. Pumping events between
        # attempts lets a same-thread primary accept the connection, and costs nothing in
        # the normal two-process case where the first wait already succeeds.
        elapsed = QElapsedTimer()
        elapsed.start()
        while socket.bytesToWrite() > 0 and elapsed.elapsed() < _WRITE_TIMEOUT_MS:
            socket.waitForBytesWritten(_POLL_INTERVAL_MS)
            QCoreApplication.processEvents()

        pending = socket.bytesToWrite()
        socket.disconnectFromServer()
        socket.deleteLater()
        return pending == 0

    def _on_connection(self) -> None:
        if self._server is None:
            return
        connection = self._server.nextPendingConnection()

        # One-shot: deliver() can be reached both from readyRead and from the immediate
        # drain below, and letting it run twice would call deleteLater on an already
        # deleted connection, which aborts the process rather than raising.
        delivered = False

        def deliver() -> None:
            nonlocal delivered
            if delivered:
                return
            payload = bytes(connection.readAll().data())
            if not payload:
                return

            delivered = True
            connection.readyRead.disconnect(deliver)
            self.command_received.emit(payload)
            connection.disconnectFromServer()
            connection.deleteLater()

        connection.readyRead.connect(deliver)
        # The command can arrive before this handler is attached -- the sender writes
        # immediately after connecting -- in which case readyRead has already fired and
        # will not fire again. Draining what is buffered closes that race.
        if connection.bytesAvailable() > 0:
            deliver()

    def close(self) -> None:
        """Release the lock. Safe to call more than once."""
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None
        QLocalServer.removeServer(self._server_name)


def run_or_signal_existing(
    server_name: str, on_command: Callable[[bytes], None]
) -> SingleInstance | None:
    """Become the primary instance, or signal the existing one and return None."""
    instance = SingleInstance(server_name)
    if not instance.try_become_primary():
        instance.send_command()
        return None
    instance.command_received.connect(on_command)
    return instance
