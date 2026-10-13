"""U2-A Sandbox contracts; synthetic evidence does not establish external isolation."""
VERSION = "2.2-u2a"
SCHEMA_VERSION = "sandbox-rest-contract-1"


def source_version():
    import hashlib
    from pathlib import Path
    from issue_to_patch_upgrade.core import digest
    return digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(Path(__file__).parent.glob("*.py"))})
