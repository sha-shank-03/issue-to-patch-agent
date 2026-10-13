# U2-A Sandbox source contract

This additive Python 3.11 standard-library adapter sends fixed Vercel Sandbox
REST operations through an owned trusted Python transport helper. It checks
controller-selected project/team, exact image digest, JDK17 commands, candidate
bytes and session identity. The only task layout in this slice is the authored
D01 `QuantityApi`/`ContractProbe` protocol fixture. Commons Lang source,
licensing/build packaging, fresh corpus and baseline remain later U2-B work.

The example configuration intentionally leaves real project/team/image,
image validation and Sandbox/compute authorization unset. Its synthetic
image is a protocol identity; it is not an available or verified JDK image.
The default Vercel image is not assumed to contain JDK17. Separate approved
Sandbox authentication/project access, image availability/digest/architecture,
binary paths, writable working directory, absence of embedded credentials and
bounded cloud charges must be established before any external request.
An AI Gateway key does not supply these approvals.

## Verified operations

The canonical REST documentation rendered successfully. Its typed schemas,
rather than generated examples that stringify booleans/numbers, define the
wire values. Official SDK source was inspected at commit
`31244aa3280dc3fdca0680933f85971570d73d2d`; it confirms gzip upload and log
record framing. That SDK revision uses v2/v3 creation and some retries; this
adapter independently uses the documented v4 named-creation REST operation
and performs no automatic mutation retries or SDK installation.

| Operation | Fixed REST shape | Primary source |
|---|---|---|
| Create | `POST /v4/sandboxes`, project/name/image/architecture/resource/timeout pins | [Named creation](https://vercel.com/docs/rest-api/sandboxes/create-a-named-sandbox-2) |
| Upload | `POST /v2/sandboxes/sessions/{id}/fs/write`, gzip, `x-cwd:/vercel/sandbox` | [Upload](https://vercel.com/docs/rest-api/sandboxes/write-files) |
| Execute | `POST .../{id}/cmd`, argv array, `wait:false`, bounded timeout | [Execute](https://vercel.com/docs/rest-api/sandboxes/execute-a-command) |
| Await | `GET .../{id}/cmd/{commandId}?wait=true`, correlated identity and integer exit | [Command status](https://vercel.com/docs/rest-api/sandboxes/get-a-command) |
| Logs | `GET .../{id}/cmd/{commandId}/logs`, bounded NDJSON `stream/data` | [Logs](https://vercel.com/docs/rest-api/sandboxes/stream-command-logs), [SDK validators](https://github.com/vercel/sandbox/blob/31244aa3280dc3fdca0680933f85971570d73d2d/packages/vercel-sandbox/src/api-client/validators.ts) |
| Read | `POST .../{id}/fs/read`, fixed source/probe path and working directory | [File read](https://vercel.com/docs/rest-api/sandboxes/read-a-file) |
| Stop/observe | `POST .../{id}/stop`, then `GET .../{id}` | [Stop](https://vercel.com/docs/rest-api/sandboxes/stop-a-session), [Session status](https://vercel.com/docs/rest-api/sandboxes/get-a-session) |
| Recover/delete | named `GET` with project/team and `resume:false`; scoped `DELETE` after observed stop | [Named lookup](https://vercel.com/docs/rest-api/sandboxes/get-a-named-sandbox), [Delete](https://vercel.com/docs/rest-api/sandboxes/delete-a-sandbox) |

Every guest uses `persistent:false`, `networkPolicy:{"mode":"deny-all"}`,
`ports:[]` and `env:{}`. Commands use empty env, no sudo/stdin/shell, fixed
`/usr/bin/java` and `/usr/bin/javac` argv. Service authentication stays in the
control-plane helper's stdin memory and Authorization header; it is never
uploaded or injected into the guest. The helper only addresses
`api.vercel.com` over HTTPS, or an explicit literal loopback port for tests.
No proxy discovery, redirects, external source URL, mounts, packages or
credential brokering are used. [Sandbox security model](https://vercel.com/docs/sandbox),
[network policy](https://vercel.com/docs/sandbox/concepts/firewall).

## Authority and recovery

`Proposal.from_actor` closes the existing actor and freezes candidate bytes,
source/original/public-record hashes. Trusted `CheckPlan` owns probe bytes,
preimage and expectations. Private verification requires the actor closed;
it uses a distinct guest after the public guest stops and is deleted. No
verifier observation is given to the actor. A nonblocking controller lock
prevents overlapping execution/recovery, and the lifecycle caps two serial
sessions. Source/probe upload preimages and source bytes after execution are
compared independently of an exit-zero or completion string.

The controller journals the stable guest name and create intent before sending
the create POST. A lost/ambiguous response never causes another provisioning
POST. Cleanup resolves that name with `resume:false`, verifies matching
metadata, stops the known session, observes a terminal state, deletes the
owned named record and confirms absence. An early lookup 404 after ambiguous
creation does not establish that provisioning was absent. Pending stop,
identity drift, uncertain deletion, expired time or failed helper cleanup
retains the record, blocks further execution and returns a typed handoff.

`for_cleanup` restores only cleanup from a trusted host-owned journal. It
retains run identity/request/session/output counters, charges downtime against
the original deadline and denies clock discontinuity. It cannot resume
execution or allocate a new guest. Cleanup receives the reserved window on
the same cumulative clock. No automatic renewal or counter reset exists.
If auth/time is exhausted, main must authorize any separate operator recovery.
Unknown cost/reservations remain held for main reconciliation after teardown.

Default/hard bounds are 120/180 total seconds, 20 seconds per helper request,
10 seconds reserved cleanup, 48 requests, two guests, 15 seconds per command,
32 KiB candidate, 16 KiB probe, 64 KiB gzip upload/body/log output and 128 KiB
encoded request. Archives contain only two regular fixed-path files; they are
never extracted on the host. Critical optional API metadata is required by
local policy; missing/changed image, architecture, timeout or deny-all echo
fails closed rather than implying verified isolation.

## Evidence and reviewer commands

On 11 October 2026, 21 initial pure tests passed; after recovery/window/serial
hardening, all 26 passed with native exit 0. Tests prohibit sockets and process
creation. The earlier passing receipt is retained. Synthetic responses exercise
false fixes, command/runtime/source/log failures, sealed tampering, lost-create
recovery/404 handoff, stop pending, cumulative clocks/counters and fixed wire
authority. No genuine Sandbox, image, auth, Java or model quality claim follows.
Finite probe equality does not prove arbitrary candidate code cannot forge
stdout or memorize checks; `domain_verified` and `external_isolation_verified`
remain false throughout U2-A.

Only the pure command has run in this slice:

```powershell
py -3.11 -m unittest discover -s tests/sandbox_pure -v
```

The following ordered batch is authored and awaits a named local contracts
lease. The acceptance script includes five socket/helper tests once and
24 synthetic journey assertions; no extra transport-suite run is needed.

```powershell
py -3.11 -m issue_to_patch_sandbox doctor
py -3.11 scripts/sandbox_contract_acceptance.py
py -3.11 -m issue_to_patch_sandbox contract-demo --scenario success
py -3.11 -m issue_to_patch_sandbox contract-demo --scenario lost-create
```

Expected native exits are `0,0,0,4`; success is `CONTRACT_COMPLETE`, and lost
create is `TRANSPORT_ERROR` with one provisioning attempt, observed cleanup
and retained blocking state. Saved ignored output is under
`work/sandbox-contract/`; proposal Java remains text on Windows. The new REST
helper's actual wire/deadline/cancel/cleanup behavior is unexecuted. U1's prior
accepted helper tests do not substitute for that new integration batch.
