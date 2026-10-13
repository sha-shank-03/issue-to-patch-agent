"""LEASE REQUIRED: trusted REST helper/owned loopback doubles, never actual Sandbox."""
from contextlib import contextmanager
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import socket
import threading
import time
import unittest
from urllib.parse import urlsplit

from issue_to_patch_upgrade.core import Failure,encoded
from issue_to_patch_sandbox.client import SandboxClient,LifecycleBudget
from issue_to_patch_sandbox.contract import Proposal,SandboxLimits,synthetic_config
from issue_to_patch_sandbox.synthetic import SyntheticPlane,actor_candidate,probe_plan
from issue_to_patch_sandbox.transport import owned_transport


@contextmanager
def server(scenario="success",trickle=False):
    plane=SyntheticPlane(scenario);received=[];stop=threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def serve(self):
            payload=self.rfile.read(int(self.headers.get("Content-Length",0)))
            received.append({"method":self.command,"path":self.path,"authorization":self.headers.get("Authorization"),
                             "content_type":self.headers.get("Content-Type"),"cwd":self.headers.get("x-cwd")})
            try:
                response=plane.respond(self.command,urlsplit(self.path).path,payload)
            except Failure:
                self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
            self.send_response(response.status);self.end_headers()
            try:
                if trickle:
                    while not stop.wait(0.1): self.wfile.write(b"x");self.wfile.flush()
                else: self.wfile.write(response.body)
            except OSError: pass
        do_POST=do_GET=do_DELETE=serve
    http=ThreadingHTTPServer(("127.0.0.1",0),Handler);http.daemon_threads=False
    thread=threading.Thread(target=http.serve_forever,kwargs={"poll_interval":0.05});thread.start()
    try: yield http.server_port,plane,received
    finally:
        stop.set();http.shutdown();http.server_close();thread.join(timeout=1)
        if thread.is_alive(): raise AssertionError("owned Sandbox double server not joined")


def lookup_frame():
    return encoded({"method":"GET","path":"/v2/sandboxes/ipa-"+"a"*32+"-public-1?teamId=team_synthetic&projectId=prj_synthetic&resume=false",
                    "content_type":"application/json","cwd":None,"payload":""})


class SandboxTransportTests(unittest.TestCase):
    def test_two_serial_synthetic_sessions_and_fixed_helper_headers(self):
        config=synthetic_config();proposal=Proposal.from_actor(actor_candidate())
        with server() as (port,plane,received):
            transport=owned_transport(config,port=port);client=SandboxClient(config,transport)
            public=client.execute(proposal,probe_plan("public"));verifier=client.execute(proposal,probe_plan("verifier"))
            self.assertEqual(public["status"],"CONTRACT_COMPLETE");self.assertEqual(verifier["status"],"CONTRACT_COMPLETE")
            self.assertTrue(transport.cleanup_complete);self.assertEqual(plane.maximum_active,1)
            self.assertEqual(sum(r["path"].startswith("/v4/") for r in received),2)
            self.assertTrue(all(r["authorization"] is None for r in received))
            uploads=[r for r in received if "/fs/write" in r["path"]]
            self.assertEqual(len(uploads),2)
            self.assertTrue(all(r["content_type"]=="application/gzip" and r["cwd"]=="/vercel/sandbox" for r in uploads))
            self.assertFalse(plane.named)

    def test_lost_create_has_one_provision_attempt_and_recovers(self):
        config=synthetic_config();proposal=Proposal.from_actor(actor_candidate())
        with server("lost-create") as (port,plane,received):
            transport=owned_transport(config,port=port);client=SandboxClient(config,transport)
            result=client.execute(proposal,probe_plan("verifier"))
            self.assertEqual(result["status"],"TRANSPORT_ERROR");self.assertTrue(result["cleanup_complete"])
            self.assertTrue(client.blocked);self.assertTrue(transport.cleanup_complete)
            self.assertEqual(sum(r["path"].startswith("/v4/") for r in received),1)
            self.assertTrue(any("resume=false" in r["path"] for r in received));self.assertFalse(plane.named)

    def test_trickle_owned_deadline_returns_and_reaps(self):
        config=synthetic_config(limits=SandboxLimits(wall_seconds=2,request_seconds=2,cleanup_seconds=0.2))
        with server(trickle=True) as (port,_,received):
            transport=owned_transport(config,port=port);start=time.monotonic()
            with self.assertRaises(Failure) as error: transport.exchange(lookup_frame(),budget=LifecycleBudget(config.limits))
            self.assertEqual(error.exception.status,"TRANSPORT_TIMEOUT");self.assertTrue(transport.cleanup_complete)
            self.assertLessEqual(time.monotonic()-start,3);self.assertEqual(len(received),1)

    def test_cancellation_kills_trusted_helper(self):
        config=synthetic_config(limits=SandboxLimits(wall_seconds=2,request_seconds=2,cleanup_seconds=0.2))
        with server(trickle=True) as (port,_,received):
            transport=owned_transport(config,port=port);event=threading.Event();timer=threading.Timer(0.2,event.set)
            timer.start()
            try:
                with self.assertRaises(Failure) as error: transport.exchange(lookup_frame(),budget=LifecycleBudget(config.limits),cancel=event.is_set)
                self.assertEqual(error.exception.status,"CANCELLED");self.assertTrue(transport.cleanup_complete)
            finally: timer.cancel();timer.join(timeout=1)

    def test_worker_rejects_arbitrary_url_before_http(self):
        config=synthetic_config()
        with server() as (port,_,received):
            transport=owned_transport(config,port=port)
            frame=json.loads(lookup_frame());frame["path"]="https://evil.invalid/"
            with self.assertRaises(Failure): transport.exchange(encoded(frame),budget=LifecycleBudget(config.limits))
            self.assertTrue(transport.cleanup_complete);self.assertEqual(received,[])


if __name__=="__main__": unittest.main()
