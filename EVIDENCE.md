# Verification evidence

Worker verification log, 2026-10-08. Main independently accepted M1 and M2.
M3 passed independent final review on a fresh source copy; the final section
records the main reviewer's commands and raw outcome checks.
Decisions are authored scripts; HTTP provider tests
use a fictional loopback double. Live model inference and held-out solve rate
are unmeasured.

Environment: Python 3.11.9 selected with `py -3.11`; Microsoft OpenJDK/Javac
17.0.18, runtime build 17.0.18+8; Windows PowerShell. No dependencies, build
tools, model weights or runtimes were downloaded. Commands below run from the
repository root. Exact run reports and process argument arrays remain in the
ignored `work/` directory; shared prose uses no personal absolute paths.

## Authoring checks

- Static digest generation via `py -3.11 -` exited 0. Four authored candidate
  digests and six immutable fixture/probe/oracle digests were written; no build
  ran. Candidate membership authorizes execution and does not establish
  semantic correctness.

## Verification commands

- First `py -3.11 -m unittest discover -s tests/unit -v`: exit 0, 27 tests
  passed, 1.640 seconds reported by unittest. A timed-out HTTP double emitted a
  Windows ConnectionAbortedError during its expected disconnect cleanup. The
  double was corrected to catch that additional socket-close condition;
  assertions and provider behavior were unchanged. Clean reruns are recorded below.
- Clean unit rerun: `py -3.11 -m unittest discover -s tests/unit -v`, exit 0,
  27/27 tests passed in 1.238 seconds, with no server cleanup traceback.
- The first lease precheck exited 1: "Active M1 lease missing, expired or
  insufficient." Worker orchestration incorrectly launched the following
  integration command despite that failure. This is a worker execution-gate
  error, not a passing resource check. Further heavy work stopped immediately
  when the batch results were inspected; the grant state is being audited.
- That first `py -3.11 scripts/acceptance.py --milestone 1` exited 0: 13/13
  acceptance assertions, 18 sequential Java processes, 7.108 seconds summed
  process time, 7.782 seconds wrapper time. Its technical outcomes are real,
  but its failed precheck must remain visible. Properly gated reruns and CLI
  verification are recorded below.

## Audited grant and final checks

The grant audit found the named M1 lease active through 2026-10-08 10:04 UTC.
PowerShell had deserialized expires_at to DateTime; Parse on its localized
"08-10-2026" display interpreted 10 August. Direct DateTimeOffset casting
preserves 8 October. The false rejection and subsequent orchestration error
above remain in the log. Following runs checked the corrected gate and its
exit status before launching any Java command.

| Command/check | Actual result |
| --- | --- |
| Corrected resource precheck | Exit 0; active M1 grant, 900-second active limit, 768 MiB RAM, 100 MiB generated disk. |
| `py -3.11 scripts/acceptance.py --milestone 1` (gated rerun) | Exit 0; 13/13 assertions, 18 sequential Java processes, 7.361 process seconds / 8.062 wrapper seconds. |
| `py -3.11 -m issue_to_patch doctor` | Exit 0; Python 3.11.9, java/javac available, immutable digests valid, zero builds. |
| `py -3.11 -m issue_to_patch demo --case V01 --scenario repair` | Native and shell exit 0; ACCEPTED, independent 21/21. |
| `py -3.11 -m issue_to_patch demo --case V01 --scenario false-fix` | Report/native exit 2; REJECTED, public checks pass, independent 18/21. Tool's PowerShell wrapper initially surfaced exit 1. |
| `py -3.11 -m issue_to_patch demo --case V01 --scenario novel` | Report/native exit 3; REVIEW_REQUIRED, independent not_run, zero post-edit processes. Tool wrapper initially surfaced exit 1. |
| Native child CLI exit verification (`py -3.11 -` with selected-interpreter subprocesses) | Wrapper exit 0; confirmed actual child exits 2 and 3, recorded in work/cli-verification.json. |
| `py -3.11 -m issue_to_patch report --latest` (selected-interpreter child) | Native exit 0; valid JSON for REVIEW_REQUIRED with zero post-edit processes. |

Final inspection found four Windows runtime .db cache files under a literal
%SystemDrive% directory created by the restricted environment of harmless
Python child tests. SystemDrive/ProgramData are now preserved. A Windows-only
regression check covers the missing variable. Recursive cleanup was rejected
by automatic approval review; a validated, reversible same-workspace move
relocated these generated files into ignored work/windows-runtime-cache.
No unrelated files or processes were modified.

- Final `py -3.11 -m unittest discover -s tests/unit -v`: exit 0, **28/28**
  tests passed in **1.485 seconds**; no cleanup traceback or skip on Windows.
- Final corrected resource check: exit 0. Java integration was repeated because
  the runner environment changed, not to broaden the assigned milestone.
- Final `py -3.11 scripts/acceptance.py --milestone 1`: exit 0, **13/13**
  assertions passed, **18** sequential Java processes, **6.938** summed process
  seconds / **7.546** wrapper seconds. work/acceptance-m1.json retains the
  latest detailed assertions and run paths.

## Final domain outcomes

- Original: 19/21 independent assertions; failures are zero-quantity acceptance
  and the incorrectly added order. This is the authored defect, not a harness
  or compiler failure.
- Repair: 21/21 independent assertions. The trace contains two real public
  semantic failures (original and intermediate edit), followed by revision and
  current public success. Two authored patch attempts.
- False fix: public success; 18/21 independent assertions. Quantity 100 fails
  acceptance, stock and order-count checks. Rejected as required.
- Novel: source diff retained; zero post-edit compiler/probe calls and private
  evaluation not_run. Missing-compiler case separately returns INFRA_ERROR/4.
- All three scenarios bind report/manifest/candidate/probe digests. Protected
  verifier names/labels are absent from agent traces. Zero real model requests,
  model downloads or external writes; live held-out solve rate remains null.

## Resource handoff

Across all recorded development/verification runs: 78 sequential Java process
launches, 30.751 summed Java process seconds; approximately 37.610 seconds of
heavy-command wall time. Heap caps are javac 256 MiB and probe 128 MiB. Peak
process RSS was not measured; no production memory-performance claim is made.
Generated disk remains far below the 100 MiB lease limit; final exact bytes are
in work/resource-accounting.json. No download bytes. Heavy work is finished and
the named lease is release-ready for main to release. Worker checks do not
establish main acceptance.

Final source scan (`py -3.11 -`): exit 0, 25 source/document files scanned,
zero personal absolute paths or trailing-whitespace findings; no unexpected
runtime cache at the source root. `git status --short` lists only the intended
M1 source/docs and initial .gitignore. Generated work stays ignored. Final
accounting observed 1,327,068 generated bytes (about 1.27 MiB), below 100 MiB.

## Unexecuted checks and limitations

- Independent M3/final review and hosted Linux/Windows CI.
- M3, baseline comparison and repeat
  measurements, final CI configuration and hosted Linux/Windows CI.
- Actual Ollama/server/model inference or compatibility, API credentials and
  any real model usage or cost measurement.
- Hostile-code isolation, concurrency/database/HTTP integration and production
  operation. Only trusted authored Java is executed; novel patches are
  proposal-only. General process-tree containment is not claimed.

## M2 source-only handoff, 2026-10-08

M1 was independently accepted before this assignment. Its lease was released.
M2 authoring and lightweight Python units were authorized; a new integration
lease is required for Java, full demos, real HTTP doubles and subprocess units.
No such M2 work has run. Source authoring has added eight cases, three-family
reports, development-only scripts and bounded failure checks. No dependency,
UI, M3 baseline, CI or live inference work was added.

Commands actually run from the repository root:

| Command | Actual outcome |
| --- | --- |
| `py -3.11 work/author_m2.py` | Exit 0; eight additional authored cases, zero Java compilations/evaluations. Ignored one-time authoring script. |
| `py -3.11 work/freeze_m2.py` | Exit 0; nine frozen cases, 114 immutable files, zero Java processes. Ignored one-time authoring script. |
| First two `py -3.11 scripts/freeze.py --verify` attempts | Exit 1: verifier expected `held_out` while manifests used `held-out`, then expected `id` while preserved V01 input schema used `quantity`. Corrected schema handling; domain expectations unchanged. |
| `py -3.11 scripts/freeze.py --verify` | Exit 0; three development and six held-out cases. Read-only verifier never regenerates a failed freeze. Final receipt: `work/m2-freeze-verification.json`. |
| Initial `py -3.11 -m unittest discover -s tests/pure -v` | Exit 0; 52/52 tests in 41.155 seconds. No child processes, Java or network. |
| Final `py -3.11 -m unittest discover -s tests/pure -v` | Exit 0; 57/57 tests in 42.705 seconds, after adding compile/launch integrity doubles and using frozen V01 oracles. Full output: `work/m2-pure-unit-log.txt`. |
| Python `compile(...)` over shipped `.py` sources | Exit 0; 22 Python source files parsed/compiled in memory without executing their application code. Zero Java/child processes. |
| `py -3.11 -m issue_to_patch doctor` | Exit 0; Python 3.11.9, Java/javac available, nine frozen cases, zero builds. |

Final freeze SHA-256:
`14e1c6d5f476550fa308e91433e24718e9e0a53801441dc25675cfb658eea34c`.
Final static trust SHA-256:
`70fed424125df3b9bb02b33ede90fadb056358d5d56949ebb1cac241807fc86e`.
Every per-file and candidate digest is in `evaluation/frozen.json` and
`evaluation/trusted.json`. Inputs are frozen before domain integration; they
have not been calibrated by executing the additional Java candidates.

Pure tests check protocol correction/termination, reproduction-before-edit,
stale/idempotent edits, budgets, explicit unknown usage, protected files,
atomic write failures, endpoint/redirect/malformed-response restrictions,
typed observations and candidate/probe changes around compile/launch.
Process timeout/output/cancellation and Windows reparse checks use doubles.
Fake loop reports say `scripted_protocol_double`, with zero process records;
passing these units does not establish Java domain outcomes.

Prepared lease-only commands, not executed in this source-only M2 assignment:

```powershell
py -3.11 -m unittest discover -s tests/unit -v
py -3.11 scripts/acceptance.py --milestone 2
```

The first includes the M1 loopback HTTP/harmless Python process tests plus a
new real owned-child cancellation test. The second runs all pure adversarial
groups, 27 original/reference/false-fix candidates against public and private
probes, M1 regression, and P01/T01 development loops. It must report original
reproduction/reference acceptance/false-fix rejection as 3/3 in each family,
with six held-out tasks separately identified. Expected independent reference
assertion denominators are validation 63, pagination 42 and transaction 105
(210 total). These are frozen input counts, not passing outcome claims.

M2 Java compilations, real process cancellation, new-case semantic assertions,
9/9 outcome calibration and main independent M2 acceptance remain unexecuted.
Actual Windows junction creation, hostile code containment, live model
performance, M3 baseline and hosted CI remain unexecuted. This handoff makes
no new Java or live-model acceptance claim. The leased verification below
supersedes the Java unexecuted status from this source-only handoff.

## M2 leased worker verification, 2026-10-08

Main explicitly granted `issue-to-patch-agent-m2-integration` for four prepared
commands, authored held-out candidate calibration, local HTTP doubles and
harmless owned-process units. Before each command, `work/check_m2_lease.py`
read raw JSON timestamps using `datetime.fromisoformat`, required a timezone,
verified grant <= current UTC < expiry, and checked both approved hashes.
Every gate exited 0. Gate receipts are in `work/m2-lease-checks.jsonl`.
No dependency, candidate, oracle, label, runtime source or frozen hash changed.
There were no failed integration receipts or corrective reruns.

| Authorized command | Actual outcome |
| --- | --- |
| `py -3.11 -m issue_to_patch doctor` | Exit 0; Python 3.11.9, Java/javac available, nine frozen cases; zero builds. Log: `work/m2-integration-01-doctor.log`. |
| `py -3.11 scripts/freeze.py --verify` | Exit 0; 9 cases, 114 immutable files, exact approved freeze/trust digests. Log: `work/m2-integration-02-freeze.log`. |
| `py -3.11 -m unittest discover -s tests/unit -v` | Exit 0; **29/29** in **7.546 seconds**, no skips. Real loopback HTTP doubles and four harmless owned Python children, including timeout, capped output, Windows environment and keyboard cancellation. Log: `work/m2-integration-03-units.log`. |
| `py -3.11 scripts/acceptance.py --milestone 2` | Exit 0; **114/114** acceptance checks; embedded **57/57** pure units in **43.677 seconds**; M1 regression **13/13**. **138** sequential Java process records, **59.016** cumulative process seconds, **148.125** acceptance wall seconds. Log: `work/m2-integration-04-acceptance.log`; detail: `work/acceptance-m2.json`. |

| Family | Original defects reproduced | References accepted | Public-passing false fixes rejected | Independent reference assertions | Held-out cases |
| --- | --- | --- | --- | --- | --- |
| Validation | 3/3 | 3/3 | 3/3 | 63/63 | V02, V03 (2) |
| Pagination | 3/3 | 3/3 | 3/3 | 42/42 | P02, P03 (2) |
| Transaction | 3/3 | 3/3 | 3/3 | 105/105 | T02, T03 (2) |
| Total | **9/9** | **9/9** | **9/9** | **210/210** | **6** |

All 27 frozen authored candidates were actually compiled and observed through
separate public/private builds. A candidate was accepted only from final
domain state. The reference calibration passed every frozen assertion;
every false fix passed public checks but failed independent verification.
Each calibration's commands, source digest, public/private observations and
verdict are retained in its `work/runs/<id>/calibration.json`.

Development-script journeys also passed independently: V01 21/21 (including
actual failed feedback before revision), P01 14/14, T01 35/35. Novel V01 code
remained proposal-only with zero post-edit processes. Missing javac remained
an infrastructure failure. Independent oracle paths/labels were absent from
the acting traces. Unit-double reports retain their double labels.

The cancellation test started a real owned Python child, injected keyboard
cancellation at the runner boundary, and asserted that the child exited and
both pipes closed. Timeout/output tests returned reaped child exit codes.
Every Java process record returned completed/exit 0; execution is sequential.
A post-run Windows process inventory found no Java/javac process whose command
line referenced this repository. No unrelated process was stopped.

Resource use stayed below the 15 active-minute lease ceiling: approximately
156.31 seconds for the full units plus acceptance, one Java child at a time,
compiler heap cap 256 MiB and probe heap cap 128 MiB. Peak RSS was not measured;
the 768 MiB allocation is a requested estimate, not an observed memory result.
Generated disk accounting and final receipt hashes are in this worker's
coordination verification record. Downloads and real model calls were zero.

This is authored candidate calibration and scripted workflow verification,
not model solve-rate measurement. Live held-out solve rate remains null and
live tasks attempted remains zero. Main independent M2 acceptance, M3 baseline
and CI, actual Windows junction creation and hostile-code containment remain
unexecuted. The worker stops at M2 review readiness.

## M2 independent acceptance and M3 source-only preparation

Main independently accepted M2 on 2026-10-08 after rerunning all four commands,
reparsing 630 raw probe values across 27 candidates, checking 114 immutable
hashes and independently recomputing P02/T03 contract outcomes. Reference
assertions were 210/210; all nine originals reproduced and all nine false fixes
were rejected. M2 remains candidate calibration rather than live solve rate.

M2's heavy lease was released. The next assignment authorizes M3 source and
lightweight isolated Python only. No M3 Java execution, complete HTTP/process
unit suite, comparison/repeat scoring or CI-equivalent acceptance has run.
Source now includes a development-only paired ablation, exactly three V01
repetitions, release checks, expanded provider tests, architecture/tradeoffs,
final quickstart and a pinned official CI workflow. No frozen fixture, label,
oracle, allowlist or accepted runtime source changed.

Actual source/lightweight checks:

| Command/check | Outcome |
| --- | --- |
| Read-only `py -3.11 scripts/freeze.py --verify` | Exit 0; nine cases/114 files; accepted freeze `14e1c6d5f476550fa308e91433e24718e9e0a53801441dc25675cfb658eea34c`, trust `70fed424125df3b9bb02b33ede90fadb056358d5d56949ebb1cac241807fc86e`. |
| Initial `py -3.11 scripts/release_check.py` | Exit 1; unfrozen `.gitignore` retained CRLF. Receipt `work/m3-release-initial-failure.json`. Normalized only that file to LF; frozen bytes unchanged. |
| Corrected `py -3.11 scripts/release_check.py` | Exit 0; source compiles in memory; expected MIT/docs/pins/CI policy and LF bytes checked. Zero builds, child processes or network. Receipt `work/m3-source-release-check.json`. |
| `py -3.11 -m unittest discover -s tests/pure -v` | Exit 0; **68/68** in **44.883 seconds**. Log `work/m3-pure-unit-log.txt`. No Java, actual child process, HTTP request or baseline/repeat scoring. |
| Official release pages and three `git ls-remote` checks | Fixed checkout v7.0.1, setup-python v7.0.0 and setup-java v6.0.1 tags resolved to full commits; each Git metadata query exited 0. No repository clone or action/runtime/model download/execution. |

The eleven new isolated units use fictional feedback and transport mocks. They
check shared-context/action-prefix integrity, the one-candidate stopping rule,
held-out exclusion, regression denominators, unknown infrastructure results,
provider envelope/usage/cleanup and CI pin/permission/platform restrictions.
They validate components and control flow, without measuring the new ablation.
The five additional actual loopback tests are source-authored and unexecuted.
`docs/PROVIDER_TESTS.md` lists the behavior coverage without inventing a code
coverage percentage or live model compatibility result.

The paired harness delegates to the accepted script for both modes. It hashes
the common semantic context, first candidate and first six tool actions. Clock
telemetry is the explicit exclusion; common host budget limits remain identical.
It independently checks the original development source for regression counts.
A failed one-candidate actor abstains honestly; separate host verification
evaluates its frozen candidate after channel closure. That host verification is
included in the mode's total latency, separately from actor latency. No held-out
proposal is scored or used to tune scripts.

Prepared lease-only commands:

```powershell
py -3.11 -m issue_to_patch doctor
py -3.11 scripts/release_check.py
py -3.11 -m unittest discover -s tests/unit -v
py -3.11 scripts/acceptance.py --milestone all
```

The full unit suite is expected to contain 34 tests, including five new real
loopback boundaries. Full acceptance combines the accepted M2 calibration with
three paired development tasks and three V01 repeats. Source-derived process
estimate: 138 M2 Java invocations plus 68 comparison/repeat invocations, all
sequential (206 total). These are prepared workload counts, not executed results.
New M3 comparison acceptance asserts pairing, one-candidate termination, actual
V01 failed feedback, zero loop regressions and three passing identical-candidate
repeats. Runtime range/median, acceptance and regression metrics remain unmeasured
until the integration lease.

The CI workflow pins `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`,
`actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97` and
`actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6`. Official release
URLs/versions are retained in `docs/ci-actions.json` and `ATTRIBUTION.md`.
It selects standard Ubuntu/Windows runners, max-parallel 1, 15-minute job limit,
read-only permissions, Python 3.11 and Microsoft Java 17. LF attributes protect
hash portability. Source checks do not establish hosted execution or Linux
compatibility; no push, publication, deployment or remote workflow was triggered.

M3 Java comparison/repeats, new real HTTP checks, full acceptance, main independent
M3 review, hosted CI, actual model/server inference and hostile-code containment
remain unexecuted. Live held-out solve rate stays null and model calls stay zero.
The source-only status is superseded by the leased verification below.

## M3 leased worker verification and review handoff

Main accepted the exact M3 source snapshot before integration:
`73a1ca6302dcdf9573955a95d6fc243fa16bc603226d7753509994dd3dce6cb3`, 141 files.
Main then explicitly granted `issue-to-patch-agent-m3-integration` for the four
recorded commands. The raw JSON offset-aware gate checked owner, milestone,
active grant/expiry, resource limits, every reviewed source hash and accepted
freeze/trust before each dependent command. All four gates exited 0; receipts
are in `work/m3-lease-checks.jsonl`. No code, policy, label, candidate, oracle or
frozen-runtime correction was needed. There were no failed integration runs.

| Authorized command | Actual result |
| --- | --- |
| `py -3.11 -m issue_to_patch doctor` | Exit 0; Python 3.11.9, Java/javac available, nine frozen cases, zero builds. Log `work/m3-integration-01-doctor.log`. |
| `py -3.11 scripts/release_check.py` | Exit 0; all 141 reviewed source hashes, 114 accepted immutable hashes, LF/MIT/CI/pin checks. Log `work/m3-integration-02-release.log`. |
| `py -3.11 -m unittest discover -s tests/unit -v` | Exit 0; **34/34** tests in **7.592 seconds**, no skips. Real owned loopback doubles included all five new provider edge tests; four harmless Python process probes passed cleanup/timeout/output/environment checks. Log `work/m3-integration-03-units.log`. |
| `py -3.11 scripts/acceptance.py --milestone all` | Exit 0; **114/114 M2** and **26/26 M3** checks, embedded **68/68** pure units in **43.233 seconds**, M1 regression **13/13**. **206** sequential Java invocations, **85.433** cumulative process seconds, **206.766** full acceptance wall seconds. Log `work/m3-integration-04-acceptance.log`; JSON `work/acceptance-all.json`. |

M2 calibration again reproduced all nine originals, accepted all nine
references (210/210 assertions), and rejected all nine public-passing false
fixes. M3 scored only the three development pairs and exactly three V01 repeats.
The pair report is `work/development/4b2fb4a4e31f4e1eb7fc19b3fa260405/pairs.json`;
the repeat report is `repeats.json` in the same directory.

| Development task | One-candidate domain result | Feedback-loop domain result | Baseline regressions | Loop regressions | Patch attempts baseline/loop |
| --- | --- | --- | --- | --- | --- |
| V01 | Rejected; actor honestly ABSTAINED | Accepted, 21/21 | 9/19 | 0/19 | 1 / 2 |
| P01 | Accepted, 14/14 | Accepted, 14/14 | 0/11 | 0/11 | 1 / 1 |
| T01 | Accepted, 35/35 | Accepted, 35/35 | 0/33 | 0/33 | 1 / 1 |
| Accepted task count | **2/3** | **3/3** | | | |

Each pair matched initial semantic context, first candidate and six-action
prefix hashes. Both policies used identical host limits. Only measured remaining
wall-clock telemetry was excluded from the common-context hash. Regression
denominators are originally passing assertions, not all assertions. V01's
baseline failed its actual public check, then stopped before another edit.
Its separate host verification ran after actor closure and retained the original
ABSTAINED report. The loop consumed failed feedback and revised. The first
candidate/revision was deliberately authored, so the 2/3 versus 3/3 difference
does not establish superior model reasoning or held-out quality.

All three V01 repeats accepted the same final source SHA-256 and passed 21/21
independent assertions. Observed runtimes were **6.609, 6.625 and 6.641 seconds**
(minimum/median/maximum). These are timing observations for one deterministic
scripted workflow, not stochastic inference variance. Paired scoring used 44
Java invocations; repeats used 24. M3-only acceptance took 60.125 seconds and
27.643 cumulative Java process seconds; M2 regression supplied the other 138
Java invocations. Models/downloads were zero and live held-out solve rate is null.

All recorded Java commands completed with exit 0. Timeout, output and keyboard
cancellation probes killed/reaped their owned Python child and closed pipes.
Loopback doubles shut down, closed their servers and joined their threads; the
full unit command exited 0. Post-run Windows inventory found **zero** Java/javac
processes whose command line referenced this repository. No unrelated process
was stopped. Cleanup receipt: `work/m3-owned-process-check.json`.

The full units plus acceptance consumed approximately **214.94 heavy wall
seconds**, below the 15-active-minute cap. One Java child and at most one owned
loopback server ran at once; compiler/probe heap caps remained 256/128 MiB.
Peak RSS was not instrumented and is not claimed as measured. Final generated
disk bytes, command/receipt hashes and source snapshot are in the worker's
verification record. No dependency, runtime, action, model or repository was
downloaded under this lease.

Only README and this evidence log were updated after scoring to describe actual
results. The reviewed versions are retained in `work/m3-reviewed-README.md` and
`work/m3-reviewed-EVIDENCE.md`; the original reviewed source snapshot remains
intact. Executable source, policy, CI pins and all 114 accepted frozen hashes
are unchanged. Final source checking binds the updated documentation separately.

Hosted Ubuntu/Windows CI, actual Linux execution, live Ollama/server/model
inference, model/prompt digest capture, costs, actual Windows junction creation
and hostile-code/process-tree containment remain unexecuted. The free pinned
CI configuration, architecture/tradeoffs, MIT/license/data attribution and
Windows/Linux command shapes are present. No push, publication, deployment or
external account change was made. Worker verification is complete; main's
independent M3/final acceptance is recorded below.

## Independent final acceptance

On 2026-10-08 the main reviewer copied the 141 shipping source files into a
fresh directory, without Git metadata, generated runs, caches or build output.
Using Python 3.11.9 and Java 17 on this HP, all eight documented commands passed:
doctor, release check, the full unit suite, all-milestone acceptance, successful
V01 repair, latest report, false-fix rejection and novel-patch review. Their
native exits were 0, 0, 0, 0, 0, 0, 2 and 3 respectively; the last two are the
documented expected outcomes.

The full suite passed 34 units; all-milestone acceptance passed 68 pure units,
114 M2 checks and 26 M3 checks. Independent review added 182 conditions and
reparsed 833 raw probe values: 630 calibration values, 140 paired values and
63 repeat values. It recomputed reference outcomes, originally passing
regression denominators, identical action prefixes and final source digests.
The development baseline accepted 2/3 tasks and the feedback loop 3/3, with
the deliberately authored V01 failure retained. All three repeats passed 21/21;
main-run minimum/median/maximum were 7.500/7.625/7.656 seconds. These are local
scripted observations, without a live model performance claim.

All 141 source files and 114 protected files remained unchanged during the
run. Only README and this log were subsequently updated to record acceptance;
the release check was rerun. Official action tags independently resolved to
the three pinned commits above. Hosted CI, Linux execution, live inference,
actual junction creation and hostile-code/process-tree containment remain
unexecuted. The repository is accepted for this local, reproducible MVP scope.

## Public source release — 9 October 2026

All three local MVP milestones passed independent acceptance on 8 October 2026, including final documentation review. The review was executed separately from the implementation worker and included documented quickstarts, meaningful success/failure tests and direct domain-state checks. The results and limitations above remain unchanged.

This source release includes application code, authored fixtures, evaluator/tests, quickstart, architecture, license/attribution and the prepared CI workflow. Private orchestration records, machine-specific paths, runtime caches and generated local runs are excluded. Offline scripted/rule/replay outcomes and local provider doubles do not establish live model quality, employer adoption or production impact. Hosted CI results are available in this repository's Actions tab after publication; historical local reports retain their original execution dates.

## U1 source and pure contracts — 11 October 2026

The additive `issue_to_patch_upgrade` package implements native Gateway
function-call envelopes, finite read/search/edit/public-check tools, bounded
accounting/events, an owned transport helper and an independent verifier of
sealed proposals against authored simulated observations. The D01 contract
fixture is fictional; no Apache source was downloaded. The authored journey
consumes failed public feedback and revises, ending as `CONTRACT_COMPLETE`.
Its independent false-fix case ends as `CONTRACT_REJECTED`. Neither status
asserts that real Java executed or a real issue was repaired.

Python 3.11.9 passed `py -3.11 -m unittest discover -s tests/upgrade_pure -v`
with 32 tests and native exit 0 (1.953 unittest seconds). After four additional
boundary checks and source hardening, the final pure receipt wrapper passed
36 tests with no failures/errors, native exit 0 and 1.171 seconds elapsed.
Every pure test prohibits subprocess creation and sockets. Recorded in-memory
scenarios include repair, 401/402/429/503, malformed/unknown calls, premature
finish and ambiguous response loss; separate tests reject a public-passing
false fix and forged public records. Raw guarded events and source versions
are retained in the private worker receipt. These are authored protocol
observations on one fixture, with no live quality denominator.

The final pure tests verified the unchanged v1 freeze SHA-256
`14e1c6d5f476550fa308e91433e24718e9e0a53801441dc25675cfb658eea34c`
and trust SHA-256
`70fed424125df3b9bb02b33ede90fadb056358d5d56949ebb1cac241807fc86e`.
The original host digest guard remains intact; novel proposal Java is kept
as in-memory or saved review text and is never executed on Windows.

At the initial source-only handoff, socket/owned-child tests, stalled
DNS/trickle/cancel teardown, CLI end-to-end
demos, full suites, Java builds, real Gateway requests and external sandbox
integration were unexecuted. They required later named
leases/assignments as applicable. No transport cleanup or real isolation
claim is inferred from pure tests. No runtime key was read, no dependency or
archive was downloaded, and live/VM spend was zero. Runtime usage/cost fields
remain null where unobserved. The exact future commands and their expected
exits are described in [the U1 guide](docs/UPGRADE_U1.md).

## U1 contract acceptance — 11 October 2026

Under the named U1 lease, the worker ran its six ordered commands once with
native exits 0,0,0,0,2,3. Seven owned Windows transport tests and 59 authored
journey assertions passed; 40 checks against saved outputs also passed. The
stalled-DNS and trickle tests each passed the 3-second bound for a 2-second
budget including helper teardown. No owned descendants remained afterwards;
owned servers/pipes/threads completed their cleanup checks. Active command
time was 6.547 seconds. The worker sampled a 116.82 MiB peak for its owned
process tree, including the recorder; brief peaks may have been missed.

Main independently accepted the bounded U1 CONTRACT milestone after 36 pure
tests, seven transport tests, 59 journey assertions, eight reviewer commands
with native exits 0,0,0,0,2,3,3,3, and 59 independent artifact predicates plus
four tamper controls. Source remained unchanged throughout both batches.
Main did not independently measure peak process memory. These results remain
fictional protocol/sandbox observations: no Java, Commons Lang source, actual
model or external VM executed, and no real isolation or repair is claimed.
The original U1 source manifest and private raw receipts are retained.

## U2-A connector source — 11 October 2026

The additive Sandbox REST contract pins controller-selected project/team,
image digest and expected JDK17 commands. The example leaves real pins,
image validation and independent auth/compute authorization unset. It uses
nonpersistent guests, deny-all egress, no ports/guest credentials, sealed
candidate bytes, separate serial public/verifier sessions, fixed argv,
bounded tar uploads/logs/deadlines and cleanup-only recovery without duplicate
provisioning. V1 and U1 executable source remain unchanged.

Python 3.11.9 passed the first 21 pure tests, then all 26 after adding serial
access, cleanup-window and persisted-recovery counter/clock controls (native
exits 0 and 0; final wrapper elapsed 0.359 seconds). Every test prohibits sockets
and subprocess creation. Their source/response fixtures are authored; they do
not validate a real image, account, Java execution or external isolation.
The five new socket/helper tests and reviewer CLI batch are authored but
unexecuted pending a U2-A lease. No archive, dependency, key/presence check,
Java process, model call or VM/account call occurred in this slice. See
[the Sandbox contract guide](docs/SANDBOX_U2A.md) for exact bounds and gates.
