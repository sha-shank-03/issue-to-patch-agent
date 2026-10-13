"""Controller-owned pins, fixed commands and immutable actor-closed proposals."""
from dataclasses import asdict, dataclass
import hashlib
import io
import re
import tarfile
import gzip

from issue_to_patch_upgrade.core import Failure, digest
from issue_to_patch_upgrade.fixture import SOURCE

ROOT = "/vercel/sandbox"
SOURCE_PATH = "src/QuantityApi.java"
PROBE_PATH = "ContractProbe.java"


@dataclass(frozen=True)
class SandboxLimits:
    wall_seconds: float = 120
    request_seconds: float = 20
    cleanup_seconds: float = 10
    requests: int = 48
    sessions: int = 2
    request_bytes: int = 131072
    response_bytes: int = 65536
    source_bytes: int = 32768
    upload_bytes: int = 65536
    command_ms: int = 15000

    def __post_init__(self):
        import math
        maxima = {"requests":48,"sessions":2,"request_bytes":131072,"response_bytes":65536,
                  "source_bytes":32768,"upload_bytes":65536,"command_ms":15000}
        for key, maximum in maxima.items():
            if type(getattr(self,key)) is not int or not 1 <= getattr(self,key) <= maximum:
                raise Failure("CONFIG_ERROR","sandbox_invalid_limit")
        for key, maximum in (("wall_seconds",180),("request_seconds",20),("cleanup_seconds",20)):
            value = getattr(self,key)
            if type(value) not in (int,float) or not math.isfinite(value) or not 0 < value <= maximum:
                raise Failure("CONFIG_ERROR","sandbox_invalid_deadline")
        if self.wall_seconds <= self.cleanup_seconds or self.command_ms < 100:
            raise Failure("CONFIG_ERROR","sandbox_cleanup_reserve_required")


@dataclass(frozen=True)
class SandboxConfig:
    project_id: str
    team_id: str
    image: str
    mode: str = "local-double"
    architecture: str = "amd64"
    java_major: int = 17
    limits: SandboxLimits = SandboxLimits()

    def __post_init__(self):
        for value, prefix in ((self.project_id,"prj_"),(self.team_id,"team_")):
            if not isinstance(value,str) or not re.fullmatch(prefix+r"[A-Za-z0-9_-]{1,100}",value):
                raise Failure("CONFIG_ERROR","sandbox_project_team_pins_required")
        if (not isinstance(self.image,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@sha256:[0-9a-f]{64}",self.image)
                or any(p in {".",".."} for p in self.image.split("@")[0].split("/"))):
            raise Failure("CONFIG_ERROR","sandbox_image_digest_required")
        if (self.mode not in {"local-double","live"} or self.architecture != "amd64"
                or type(self.java_major) is not int or self.java_major != 17 or not isinstance(self.limits,SandboxLimits)):
            raise Failure("CONFIG_ERROR","sandbox_runtime_contract_required")
        if self.mode == "local-double" and (self.project_id != "prj_synthetic" or self.team_id != "team_synthetic"
                or self.image != "synthetic/jdk17@sha256:" + "0"*64):
            raise Failure("CONFIG_ERROR","sandbox_double_identity_required")
        if self.mode == "live" and (self.project_id == "prj_synthetic" or self.team_id == "team_synthetic"
                or self.image.startswith("synthetic/") or self.image.endswith("0"*64)):
            raise Failure("CONFIG_ERROR","sandbox_real_pins_unverified")

    @property
    def fingerprint(self):
        return digest(asdict(self))


def synthetic_config(**kwargs):
    return SandboxConfig("prj_synthetic","team_synthetic","synthetic/jdk17@sha256:"+"0"*64,**kwargs)


@dataclass(frozen=True)
class SandboxAuthorization:
    """Trusted caller supplies independent auth/image/compute receipts, never model arguments."""
    project_id: str
    team_id: str
    image: str
    image_receipt_sha256: str
    compute_receipt_sha256: str
    allocation_inr: str
    worst_case_inr: str
    credential_free_image_attested: bool
    expires_at: str = ""

    def validate(self, config):
        from decimal import Decimal, InvalidOperation
        from datetime import datetime, timezone
        if ((self.project_id,self.team_id,self.image) != (config.project_id,config.team_id,config.image)
                or self.credential_free_image_attested is not True
                or any(not isinstance(v,str) or not re.fullmatch(r"[0-9a-f]{64}",v)
                       for v in (self.image_receipt_sha256,self.compute_receipt_sha256))):
            raise Failure("AUTHORIZATION_DENIED","sandbox_separate_authorization_required")
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            if expiry.tzinfo is None or datetime.now(timezone.utc) >= expiry:
                raise ValueError()
        except (ValueError,TypeError):
            raise Failure("AUTHORIZATION_DENIED","sandbox_dispatch_expired") from None
        if any(not isinstance(v,str) or len(v)>64 for v in (self.allocation_inr,self.worst_case_inr)):
            raise Failure("AUTHORIZATION_DENIED","sandbox_unknown_compute_quote")
        try:
            allocation, quote = Decimal(self.allocation_inr), Decimal(self.worst_case_inr)
        except (InvalidOperation, TypeError):
            raise Failure("AUTHORIZATION_DENIED","sandbox_unknown_compute_quote") from None
        if not allocation.is_finite() or not quote.is_finite() or not 0 < quote <= allocation:
            raise Failure("AUTHORIZATION_DENIED","sandbox_unknown_compute_quote")


@dataclass(frozen=True)
class Proposal:
    content: bytes
    source_sha256: str
    original_sha256: str
    actor_closed: bool
    public_record_sha256: str

    @classmethod
    def from_actor(cls, actor):
        sealed = actor.seal()  # This closes the U1 actor before any private session exists.
        if (actor.closed is not True or not sealed.public_result
                or sealed.public_result.get("status") != "passed"
                or sealed.public_result.get("source_sha256") != sealed.source_sha256
                or not 1 <= sealed.edits <= 3 or not 0 < sealed.changed_lines <= 200):
            raise Failure("POLICY_DENIED","sandbox_public_seal_required")
        return cls(sealed.source.encode("utf-8"),sealed.source_sha256,sealed.original_sha256,
                   actor.closed,digest(sealed.public_result))

    def validate(self, limits, role):
        if (not isinstance(self.content,bytes) or not 0 < len(self.content) <= limits.source_bytes
                or hashlib.sha256(self.content).hexdigest() != self.source_sha256
                or any(not isinstance(v,str) or not re.fullmatch(r"[0-9a-f]{64}",v)
                       for v in (self.original_sha256,self.public_record_sha256))):
            raise Failure("POLICY_DENIED","sandbox_sealed_source_invalid")
        if role == "verifier" and self.actor_closed is not True:
            raise Failure("POLICY_DENIED","sandbox_actor_must_be_closed")


@dataclass(frozen=True)
class CheckPlan:
    """Supplied by trusted controller/verifier; never accepted in model tool arguments."""
    role: str
    probe: bytes
    probe_sha256: str
    expected: tuple
    original_sha256: str = digest(SOURCE)

    def validate(self):
        if (self.role not in {"public","verifier"} or not isinstance(self.probe,bytes)
                or not 0 < len(self.probe) <= 16384 or hashlib.sha256(self.probe).hexdigest() != self.probe_sha256
                or not isinstance(self.expected,tuple) or not 1 <= len(self.expected) <= 64):
            raise Failure("CONFIG_ERROR","sandbox_trusted_probe_required")
        if not isinstance(self.original_sha256,str) or not re.fullmatch(r"[0-9a-f]{64}",self.original_sha256):
            raise Failure("CONFIG_ERROR","sandbox_original_preimage_required")
        quantities = []
        for record in self.expected:
            if (not isinstance(record,tuple) or len(record) != 2
                    or type(record[0]) is not int or type(record[1]) is not bool):
                raise Failure("CONFIG_ERROR","sandbox_probe_expectation_invalid")
            quantities.append(record[0])
        if len(set(quantities)) != len(quantities):
            raise Failure("CONFIG_ERROR","sandbox_probe_expectation_invalid")


def upload_archive(proposal, plan, limits):
    proposal.validate(limits,plan.role)
    plan.validate()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw,mode="w",format=tarfile.USTAR_FORMAT) as archive:
        for path, content in ((SOURCE_PATH,proposal.content),(PROBE_PATH,plan.probe)):
            item = tarfile.TarInfo(path)
            item.size,item.mode,item.mtime = len(content),0o644,0
            archive.addfile(item,io.BytesIO(content))
    packed = gzip.compress(raw.getvalue(),mtime=0)
    if len(packed) > limits.upload_bytes:
        raise Failure("BUDGET_EXHAUSTED","sandbox_upload_limit")
    return packed


def fixed_commands(config):
    """Only these controller-selected executables/argv are ever sent, with env={} and sudo=false."""
    return (
        ("java-version","/usr/bin/java",["-version"]),
        ("javac-version","/usr/bin/javac",["-version"]),
        ("compile","/usr/bin/javac",["-encoding","UTF-8","-d",ROOT,ROOT+"/"+SOURCE_PATH,ROOT+"/"+PROBE_PATH]),
        ("probe","/usr/bin/java",["-Xmx128m","-cp",ROOT,"ContractProbe"]),
    )
