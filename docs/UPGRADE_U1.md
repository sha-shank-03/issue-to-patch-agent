# U1 native provider contracts

U1 adds a Python 3.11 standard-library function-call boundary, finite in-memory
read/search/edit/public-check tools, cumulative limits, redacted events and
independent sealed-proposal/simulated-state verification. The authored D01
protocol fixture is **not downloaded Commons Lang source**. Its sandbox double
maps a finite list of authored source digests to fictional observations and
never compiles, interprets or executes Java. No live model or real VM result is
implied by `CONTRACT_COMPLETE`.

Reviewer commands from the repository root (the bounded U1 batch passed on
11 October 2026; pure tests can run without a lease):

```powershell
py -3.11 -m unittest discover -s tests/upgrade_pure -v
py -3.11 -m issue_to_patch_upgrade doctor
py -3.11 scripts/upgrade_acceptance.py --milestone U1 --mode local-double
py -3.11 -m issue_to_patch_upgrade offline-demo --case D01 --scenario repair
py -3.11 -m issue_to_patch_upgrade report --run latest
py -3.11 -m issue_to_patch_upgrade offline-demo --case D01 --scenario false-fix
py -3.11 -m issue_to_patch_upgrade offline-demo --case D01 --scenario http-429
```

The acceptance command includes the seven socket/owned-process transport
tests. Run that bounded suite once; a separate transport-suite invocation is
needed only to investigate a failure. The executed worker batch was doctor,
acceptance, repair demo, latest report, false-fix demo and HTTP-429 demo.

On 11 October 2026, Python 3.11.9 passed all 36 lightweight pure U1 tests
(native exit 0). They prohibit sockets and subprocess creation and cover
native message correlation, cumulative budgets, feedback revision, independent
false-fix rejection, malformed/error responses, redaction and v1 freeze/trust
preservation. An earlier 32-test run also passed; four additional boundary
tests and source hardening preceded the final run. The later named U1 lease
passed all seven Windows transport tests and 59 authored journey assertions;
the six ordered commands returned expected exits 0,0,0,0,2,3. Main independently
accepted the bounded U1 CONTRACT milestone after 36 pure tests, seven transport
tests, 59 journey assertions, eight reviewer commands with exits
0,0,0,0,2,3,3,3, and 59 saved-artifact predicates plus four tamper controls.
This evidence does not establish real Gateway compatibility, real Java behavior
or live model quality.

Repair ends `0 / CONTRACT_COMPLETE` after the first edit fails a public check
and the next edit consumes that feedback. False fix ends `2 / CONTRACT_REJECTED`
after public success but failed independent **simulated** boundary observations.
HTTP 429 ends `3 / RATE_LIMITED`, with one attempt and no tool edits. `report`
exits 0 when reading a valid report, independently of its verdict.

Run output retains `report.json`, `events.jsonl`, `proposal.java` and
`proposal.diff` under ignored `work/upgrade/runs/<run-id>/`. Reports bind
code/prompt/config/dataset/source versions, budgets, native correlated tool
messages, unknown tokens/cost, error/approval/cancel/cleanup fields and the
proposal verifier. Source output is text for review; it is never executed.

The production transport points only at
`https://ai-gateway.vercel.sh/v1/chat/completions`; integration tests can inject
only a literal loopback port with synthetic data and no credential. It has
zero retries, no proxy discovery or redirect following, and an owned Python
helper with bounded pipes and time reserved for kill/reap/pipe cleanup. The
helper is trusted transport code, **not a Java sandbox**. On 11 October 2026,
the owned Windows suite passed stalled-DNS, trickle-body, cancellation, output
bound and ambiguous-loss checks. Both 2-second deadline tests passed the
3-second bound including helper teardown; cleanup checks passed. These local
results do not prove behavior of the external Gateway or real VM service.

Native function calling uses `tools`, `tool_calls`, `finish_reason:tool_calls`
and correlated `role:tool` messages. Exactly one call is validated locally;
malformed/unknown/refused/truncated output halts before tool dispatch, with no
content-action fallback or automatic schema-correction request. The API shape
comes from [official Gateway tool-calling documentation](https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions/tool-calling).

Real runtime model and serving provider must be explicitly configured and
verified against current catalog/endpoint metadata before later live use.
`test/synthetic-coder` is an authored protocol identity. The worker chat model
does not choose a runtime model. `run --provider gateway --model ...
--serving-provider ...` fails closed in U1, because genuine isolation and a
live assignment do not yet exist; it never switches to the offline double.

Counters and active elapsed time are retained on every terminal outcome.
U1 offers no execution resume: `resume --run <id>` returns `RESUME_DENIED`
and the saved counters, with no mutation or reset. A new run receives a new
identity and cannot borrow a prior allocation. The portable per-run cost gate
never manages main's aggregate ledger; unknown prices/dispatch, zero
allocation or ambiguous delivery retain/deny reservations. Actual cost is
null until independently reconciled, not zero inferred from missing usage.

Vercel Sandbox needs separate authentication, project access, image validation
and compute authorization. An AI Gateway key does not grant Sandbox access.
U2's remote contract must explicitly use `persistent:false` and deny-all
network policy with a Java17-capable image. U1 implements no remote VM/archive
adapter or downloads. V1's frozen host runner and authored digest guard remain
unchanged. Novel generated Java never runs on Windows. Finite simulated
checks establish protocol behavior, not isolation, model quality or a repair
of the real Apache issue. No U2/U3 live counts are allocations.

The additive [U2-A Sandbox contract](SANDBOX_U2A.md) is a separate source-only
slice. The retained U1 manifest records its original source-stage snapshot;
the U2-A manifest versions later modules and this dated documentation update.

