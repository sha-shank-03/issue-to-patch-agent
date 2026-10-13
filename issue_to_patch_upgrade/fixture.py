"""Authored protocol fixture, not the downloaded Commons Lang task or live evidence."""
from .core import digest

SOURCE_PATH = "src/QuantityApi.java"
ORIGINAL = "quantity < 0 || quantity > 100"
INTERMEDIATE = "quantity < 1 || quantity > 1"
REPAIRED = "quantity <= 0 || quantity > 100"
FALSE_FIX = "quantity < 1 || quantity >= 100"
SOURCE = (
    "public final class QuantityApi {\n"
    "    public static boolean accepts(int quantity) {\n"
    "        if (quantity < 0 || quantity > 100) return false;\n"
    "        return true;\n"
    "    }\n"
    "}\n"
)
ISSUE = "The quantity API accepts a zero quantity. Inspect, reproduce and propose a bounded repair."
CONTRACT = "Accept quantities 1 through 100 inclusive; reject every other quantity."
VISIBLE = (SOURCE_PATH, "issue.md", "contract.md")
DATASET_HASH = digest({"source": SOURCE, "issue": ISSUE, "contract": CONTRACT,
                       "case": "D01-contract", "kind": "authored_protocol_fixture"})


def known_sources():
    return {digest(SOURCE.replace(ORIGINAL, pattern)): pattern
            for pattern in (ORIGINAL, INTERMEDIATE, REPAIRED, FALSE_FIX)}

