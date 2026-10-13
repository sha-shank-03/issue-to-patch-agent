"""Reuse the accepted owned-process deadline boundary with a fixed Sandbox worker."""
from pathlib import Path
from issue_to_patch_upgrade.core import Failure
from issue_to_patch_upgrade.transport import OwnedTransport


class DispatchGuard:
    def __init__(self,authorization):
        self.authorization = authorization

    def reserve(self,config):
        # Main's quote covers the capped whole lifecycle. It remains held until main reconciliation.
        self.authorization.validate(config)


def owned_transport(config,*,port=None,credential=None,authorization=None):
    if config.mode == "live":
        if authorization is None:
            raise Failure("AUTHORIZATION_DENIED","sandbox_separate_authorization_required")
        authorization.validate(config)
        guard = DispatchGuard(authorization)
    else:
        if credential is not None or authorization is not None:
            raise Failure("CONFIG_ERROR","sandbox_double_must_be_credential_free")
        guard = None
    return OwnedTransport(config,port=port,credential=credential,gate=guard,
                          helper=Path(__file__).with_name("http_worker.py"))
