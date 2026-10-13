"""LEASE REQUIRED: real owned loopback server/transport children; never an external API."""
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import threading
import time
import unittest

from issue_to_patch_upgrade.core import Budget, Config, Failure, Limits
from issue_to_patch_upgrade.doubles import completion
from issue_to_patch_upgrade.gateway import GatewayProvider
from issue_to_patch_upgrade.transport import OwnedTransport


@contextmanager
def server(mode="normal", status=200):
    stop = threading.Event()
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            received.append({"path": self.path, "authorization": self.headers.get("Authorization"),
                             "body": self.rfile.read(int(self.headers["Content-Length"]))})
            if mode == "loss":
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.send_response(status)
            if mode == "oversize":
                self.send_header("Content-Length", "131073")
            self.end_headers()
            try:
                if mode == "trickle":
                    while not stop.wait(0.1):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                else:
                    self.wfile.write(completion("test/synthetic-coder", "call-1", "list_files", {})
                                     if status == 200 else b"synthetic error body never logged")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    http.daemon_threads = False
    thread = threading.Thread(target=http.serve_forever, kwargs={"poll_interval":0.05})
    thread.start()
    try:
        yield http.server_port, received
    finally:
        stop.set()
        http.shutdown()
        http.server_close()
        thread.join(timeout=1)
        if thread.is_alive():
            raise AssertionError("owned HTTP server thread not joined")


class OwnedTransportTests(unittest.TestCase):
    def config(self, seconds=2):
        return Config("test/synthetic-coder", "test", limits=Limits(wall_seconds=seconds,request_seconds=seconds))

    def test_normal_native_call_and_no_auth(self):
        config = self.config()
        with server() as (port, received):
            transport = OwnedTransport(config,port=port)
            reply = GatewayProvider(config,transport).decide([],Budget(config.limits))
            self.assertEqual(reply.action.tool,"list_files")
            self.assertEqual(received[0]["path"],"/v1/chat/completions")
            self.assertIsNone(received[0]["authorization"])
            self.assertEqual(len(received),1)
            self.assertTrue(transport.cleanup_complete)
            self.assertEqual(transport.started,1)

    def test_http_errors_are_one_attempt_without_error_body(self):
        for status in (401,402,429,503):
            with self.subTest(status=status), server(status=status) as (port,received):
                config=self.config()
                transport=OwnedTransport(config,port=port)
                with self.assertRaises(Failure) as ctx:
                    GatewayProvider(config,transport).decide([],Budget(config.limits))
                self.assertNotIn("synthetic error",str(ctx.exception))
                self.assertEqual(len(received),1)
                self.assertTrue(transport.cleanup_complete)

    def test_windows_trickle_total_deadline_and_reap(self):
        config=self.config()
        with server("trickle") as (port,received):
            transport=OwnedTransport(config,port=port)
            start=time.monotonic()
            with self.assertRaises(Failure) as ctx:
                transport.exchange(b"{}",budget=Budget(config.limits))
            self.assertEqual(ctx.exception.status,"TRANSPORT_TIMEOUT")
            self.assertTrue(ctx.exception.ambiguous)
            self.assertLessEqual(time.monotonic()-start,3)
            self.assertTrue(transport.cleanup_complete)
            self.assertEqual(len(received),1)

    def test_cancel_interrupts_transport_and_reaps(self):
        config=self.config()
        cancelled=threading.Event()
        timer=threading.Timer(0.2,cancelled.set)
        with server("trickle") as (port,received):
            transport=OwnedTransport(config,port=port)
            timer.start()
            try:
                with self.assertRaises(Failure) as ctx:
                    transport.exchange(b"{}",budget=Budget(config.limits),cancel=cancelled.is_set)
                self.assertEqual(ctx.exception.status,"CANCELLED")
                self.assertTrue(transport.cleanup_complete)
            finally:
                timer.cancel()
                timer.join(timeout=1)

    def test_oversize_header_stops_bounded_reader(self):
        config=self.config()
        with server("oversize") as (port,received):
            transport=OwnedTransport(config,port=port)
            with self.assertRaises(Failure) as ctx:
                transport.exchange(b"{}",budget=Budget(config.limits))
            self.assertEqual(ctx.exception.code,"response_limit")
            self.assertTrue(transport.cleanup_complete)
            self.assertEqual(len(received),1)

    def test_ambiguous_response_loss_not_replayed(self):
        config=self.config()
        with server("loss") as (port,received):
            transport=OwnedTransport(config,port=port)
            with self.assertRaises(Failure) as ctx:
                transport.exchange(b"{}",budget=Budget(config.limits))
            self.assertTrue(ctx.exception.ambiguous)
            self.assertEqual(transport.started,1)
            self.assertEqual(len(received),1)
            self.assertTrue(transport.cleanup_complete)

    def test_blocked_dns_phase_helper_is_killed(self):
        config=self.config()
        helper=Path(__file__).with_name("blocked_dns_helper.py")
        transport=OwnedTransport(config,port=1,helper=helper)
        start=time.monotonic()
        with self.assertRaises(Failure) as ctx:
            transport.exchange(b"{}",budget=Budget(config.limits))
        self.assertEqual(ctx.exception.status,"TRANSPORT_TIMEOUT")
        self.assertLessEqual(time.monotonic()-start,3)
        self.assertTrue(transport.cleanup_complete)


if __name__ == "__main__":
    unittest.main()

