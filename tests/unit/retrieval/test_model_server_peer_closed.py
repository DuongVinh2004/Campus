"""The model server must not run inference for a client that already hung up (step 1.9)."""
import importlib.util
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("serve_rag_models", ROOT / "scripts/serve_rag_models.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def pair():
    left, right = socket.socketpair()
    return left, right


def test_open_silent_client_is_not_closed():
    server_side, client = pair()
    try:
        assert server.peer_closed(server_side) is False
    finally:
        server_side.close(); client.close()


def test_client_that_sent_data_and_waits_is_not_closed_and_data_is_not_consumed():
    server_side, client = pair()
    try:
        client.sendall(b"x")
        assert server.peer_closed(server_side) is False
        assert server_side.recv(1) == b"x"          # peek consumed nothing
    finally:
        server_side.close(); client.close()


def test_client_that_hung_up_is_detected():
    server_side, client = pair()
    client.close()
    try:
        assert server.peer_closed(server_side) is True
    finally:
        server_side.close()


def test_a_dead_socket_counts_as_closed_and_never_raises():
    server_side, client = pair()
    server_side.close()
    assert server.peer_closed(server_side) is True
    client.close()
