# Issue to Patch Agent

A Python decision loop reproduces authored Java semantic defects, makes bounded
edits, and returns a diff with independently checked domain state. The original
contribution is a compact Java benchmark with plausible false fixes that pass
public examples and fail protected checks. It uses Python 3.11 and JDK 17,
standard libraries only, with no package install, build tool or model server.

**Verified offline:** all 9 originals reproduce; all 9 references pass **210/210**
independent assertions; all 9 public-passing false fixes are rejected. Independent
M2 review confirmed the raw outcomes. These are authored candidate calibrations,
not a live agent solve rate. M3 passed independent final review on a fresh source
copy on Windows: eight commands and 182 additional checks passed. See
`EVIDENCE.md` for actual checks and unexecuted platform/model checks.

Run a successful repair and an independently rejected false fix from the
repository root in Windows PowerShell:

```powershell
py -3.11 -m issue_to_patch doctor
py -3.11 -m issue_to_patch demo --case V01 --scenario repair
py -3.11 -m issue_to_patch report --latest
py -3.11 -m issue_to_patch demo --case V01 --scenario false-fix
```

The repair exits **0 / ACCEPTED**, with 21/21 independent assertions. It observes
an actual failed public check after its first edit, then revises. The false fix
exits **2 / REJECTED**: public checks pass, but valid quantity 100 is rejected.
The command prints relative report/diff paths in `work/runs/<id>/`. Each run
retains candidate source, JSON/Markdown reports, source/oracle hashes, commands
and provider/tool trace. `report --latest` exits 0 regardless of the verdict.

```powershell
py -3.11 -m issue_to_patch demo --case V01 --scenario novel
```

This exits **3 / REVIEW_REQUIRED** and retains a diff with zero post-edit
processes. Only statically allowlisted authored source bytes may execute.
Execution permission does not certify correctness. A subprocess is not a
hostile-code sandbox.

The default provider decisions are authored conditional scripts. No script
is a recorded model run. Live model inference, costs and held-out solve rate
are unmeasured. The optional native Ollama adapter requires explicit opt-in,
model identity and a separately provisioned local-only server. Offline commands
never invoke a model or download one. Server/model compatibility remains
unverified; loopback addressing alone does not prove local inference.

## Dataset and evidence

| Family | Development task | Held-out tasks | Independent assertions per task |
| --- | --- | --- | --- |
| Validation | V01: quantity bounds | V02: blank customer; V03: bulk sum overflow | 21 |
| Pagination | P01: exact slices | P02: offset overflow; P03: stable ordering | 14 |
| Transaction | T01: failed multi-stock order | T02: duplicate-line totals; T03: audit failure | 35 |

The split is frozen at three development and six held-out tasks, with seven
independent scenarios per task. Held-out means excluded from acting scripts
and tool observations. Public readers can inspect the evaluator; tool authority
provides the boundary. This same-author public dataset cannot establish broad
coding performance or model generalization. P01/P02 reference bytes are shared
because their corrected slice API is the same.

M3 pairs a one-candidate baseline with the feedback loop on V01/P01/T01 only.
Both receive the same semantic context, budgets, first candidate and first six
tool actions; reports hash these inputs. Clock telemetry is explicitly excluded
from the common-context hash. A failed baseline stops honestly before a second
edit; host verification checks its frozen candidate after the actor closes.
Passing-before assertions that fail afterward count as regressions. Every task,
including infrastructure failures, stays in the denominator. These deliberately
scripted ablations do not compare inference quality.

Exactly three V01 repetitions report observed minimum/median/maximum runtime.
They measure this scripted workflow's timing, not stochastic model variance.
Calibration, development comparison, repeats and future live results retain
separate evidence labels. M3 scores no held-out proposals.

The Windows worker run accepted 2/3 one-candidate baselines and 3/3 feedback
loops. V01's deliberately authored first candidate produced 9 regressions among
19 originally passing assertions; revision reduced that to 0/19. P01/T01 were
already correct after their first candidate. All three V01 repeats passed 21/21
assertions with the same source bytes, in 6.609 / 6.625 / 6.641 seconds
(minimum / median / maximum). These observations demonstrate the scripted
feedback mechanism and local timing, not superior model reasoning.

## Verification commands

Check portable source and frozen inputs without compiling or connecting:

```powershell
py -3.11 scripts/release_check.py
py -3.11 scripts/freeze.py --verify
py -3.11 -m unittest discover -s tests/pure -v
```

Full local verification, including fictional loopback HTTP doubles and harmless
owned-process tests, then the complete outcome suite/comparison/three repeats:

```powershell
py -3.11 -m unittest discover -s tests/unit -v
py -3.11 scripts/acceptance.py --milestone all
```

`acceptance.py` treats expected negative outcomes as assertions and exits 0
only when they are verified. It retains detailed JSON under `work/`, including
`acceptance-m2.json`, `acceptance-m3.json`, `acceptance-all.json` and paired/repeat
reports in `work/development/<id>/`. Generated files are ignored. Worker checks
passed 34 full units, 68 isolated units, 114 M2 checks and 26 M3 checks; all
accepted fixture/runtime hashes remained unchanged. Hosted CI is unexecuted.

For only development comparison/repeats, use
`py -3.11 scripts/development.py --all`. Individual P01/T01 development journeys
use `py -3.11 -m issue_to_patch demo --case P01 --scenario repair` and the same
command with `--case T01`. These journeys are also included in full acceptance.

Linux/CI equivalents use `python` after selecting Python 3.11:

```bash
python -m issue_to_patch doctor
python scripts/release_check.py
python -m unittest discover -s tests/unit -v
python scripts/acceptance.py --milestone all
```

The workflow pins official checkout/setup-python/setup-java commits, selects
Python 3.11 and Microsoft JDK 17, and runs Ubuntu/Windows sequentially with a
15-minute timeout and read-only permissions. It has no secrets, caches, uploads
or live inference. Standard hosted runners are free for public repositories;
private allowances and larger runners differ. [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
Hosted execution is unexecuted; no repository has been published by this task.
Pins and official release URLs are in `docs/ci-actions.json`.

## Boundaries and limitations

This is a single-threaded in-memory Java library API, with no HTTP application,
database, arbitrary repositories, autonomous novel-code execution or production
claim. Typed tools enforce reproduction, edit/preimage integrity, current public
checks and closure before independent verification. Budgets cover decisions,
wall time, observed tokens, edits, changed lines, checks and output. Missing token
counts remain unknown. Owned children are killed and reaped; hostile descendants
and same-user processes are outside the containment claim.

See `ARCHITECTURE.md` for design/tradeoffs, `docs/PROVIDER_TESTS.md` for the local
provider behavior matrix, and `ATTRIBUTION.md` for licenses/prior art. Original
code, fixtures, data and documentation are fictional/authored and MIT licensed.
