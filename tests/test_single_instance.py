"""Single-instance enforcement.

``QLocalServer`` is a named pipe on Windows -- local, deterministic, and available headless
-- so this is tested for real rather than mocked. No network is involved (D11).
"""

from __future__ import annotations

import uuid

import pytest
from pytestqt.qtbot import QtBot

from snipline.single_instance import CAPTURE_COMMAND, SingleInstance, run_or_signal_existing


@pytest.fixture
def server_name() -> str:
    # Unique per test: a leaked name from one test would make the next one look like a
    # second instance, and the failure would depend on test ordering.
    return f"snipline-test-{uuid.uuid4().hex}"


def test_the_first_instance_becomes_primary(server_name: str) -> None:
    instance = SingleInstance(server_name)
    try:
        assert instance.try_become_primary()
        assert instance.is_primary
    finally:
        instance.close()


def test_a_second_instance_is_refused_the_lock(server_name: str) -> None:
    first = SingleInstance(server_name)
    second = SingleInstance(server_name)
    try:
        assert first.try_become_primary()
        assert not second.try_become_primary()
        assert not second.is_primary
    finally:
        first.close()
        second.close()


def test_claiming_twice_is_idempotent(server_name: str) -> None:
    instance = SingleInstance(server_name)
    try:
        assert instance.try_become_primary()
        assert instance.try_become_primary()
    finally:
        instance.close()


def test_the_lock_is_reusable_after_a_clean_close(server_name: str) -> None:
    first = SingleInstance(server_name)
    first.try_become_primary()
    first.close()

    second = SingleInstance(server_name)
    try:
        assert second.try_become_primary()
    finally:
        second.close()


def test_a_stale_server_name_does_not_block_startup(server_name: str) -> None:
    # Simulates a killed process: the pipe name survives with nothing listening. Without
    # explicit recovery, one crash would block every future launch permanently.
    from PySide6.QtNetwork import QLocalServer

    abandoned = QLocalServer()
    assert abandoned.listen(server_name)
    abandoned.close()  # leaves the name behind without a listener on some platforms

    instance = SingleInstance(server_name)
    try:
        assert instance.try_become_primary()
    finally:
        instance.close()


def test_the_second_launch_delivers_a_command_to_the_primary(
    server_name: str, qtbot: QtBot
) -> None:
    primary = SingleInstance(server_name)
    primary.try_become_primary()
    received: list[bytes] = []
    primary.command_received.connect(received.append)

    secondary = SingleInstance(server_name)
    try:
        with qtbot.waitSignal(primary.command_received, timeout=2000):
            assert secondary.send_command()
    finally:
        primary.close()

    assert received == [CAPTURE_COMMAND]


def test_send_command_does_not_need_the_sender_to_outlive_the_call(
    server_name: str, qtbot: QtBot
) -> None:
    # run_or_signal_existing discards the sender and returns immediately, and the real
    # second launch then exits the process. If send_command returned before the bytes left
    # the socket, the command would be lost and the second launch would silently do
    # nothing -- which looks exactly like a broken hotkey.
    primary = SingleInstance(server_name)
    primary.try_become_primary()
    received: list[bytes] = []
    primary.command_received.connect(received.append)

    try:
        with qtbot.waitSignal(primary.command_received, timeout=2000):
            assert SingleInstance(server_name).send_command()
    finally:
        primary.close()

    assert received == [CAPTURE_COMMAND]


def test_sending_with_no_primary_running_reports_failure(server_name: str) -> None:
    assert not SingleInstance(server_name).send_command()


def test_run_or_signal_returns_an_instance_for_the_first_launch(server_name: str) -> None:
    instance = run_or_signal_existing(server_name, lambda _payload: None)
    try:
        assert instance is not None
        assert instance.is_primary
    finally:
        assert instance is not None
        instance.close()


def test_run_or_signal_returns_none_and_notifies_the_primary(
    server_name: str, qtbot: QtBot
) -> None:
    received: list[bytes] = []
    primary = run_or_signal_existing(server_name, received.append)
    assert primary is not None

    try:
        with qtbot.waitSignal(primary.command_received, timeout=2000):
            assert run_or_signal_existing(server_name, lambda _payload: None) is None
    finally:
        primary.close()

    assert received == [CAPTURE_COMMAND]


def test_a_refused_instance_does_not_unlink_the_holders_pipe(server_name: str) -> None:
    # A secondary removing the server name leaves the primary running but unreachable, so
    # the next launch starts a second tray icon whose hotkey registration cannot succeed.
    first = SingleInstance(server_name)
    second = SingleInstance(server_name)
    try:
        assert first.try_become_primary()
        assert not second.try_become_primary()

        second.close()

        assert first.is_primary
        assert not SingleInstance(server_name).try_become_primary()
    finally:
        first.close()
