# Provider boundary checks

These tests use authored responses and no model inference. `tests/pure/`
replaces the transport with Python mocks and launches no child process or
network request. `tests/unit/` starts an owned loopback HTTP double plus
harmless Python process probes. Full transport tests require the integration
run; source preparation is not a passing transport result.

| Boundary | Local double or isolated unit |
| --- | --- |
| Explicit opt-in, model identity and literal loopback origin | `test_opt_in_and_remote_endpoints_denied_without_requests`, `test_endpoint_and_opt_in_restrictions_before_transport` |
| Native `/api/chat`, schema, nonstreaming body, history, fixed options and returned usage | `test_actual_http_contract_schema_history_and_usage`, `test_missing_usage_stays_null_and_request_is_native_structured_nonstreaming` |
| Null usage remains unknown | `test_missing_usage_round_trips_as_unknown` |
| 302, 429, 503; no retry or fallback | `test_http_failures_and_redirect_have_no_retry_or_fallback` |
| Wrong model/done/role/content/tool calls and invalid usage types | `test_wrong_native_metadata_and_usage_denied`, `test_native_tool_calls_wrong_roles_and_content_types_are_rejected`, isolated float-usage test |
| Invalid UTF-8, non-object JSON, duplicate keys and non-finite values | `test_invalid_utf8_and_non_object_json_are_rejected`, existing malformed-response test and isolated envelope tests |
| 65,536-byte response accepted; 65,537 rejected | `test_exact_byte_limit_accepted_and_one_byte_over_rejected` |
| Oversized context blocked before transport | `test_context_cap_blocks_transport_before_any_server_request` |
| Read timeout bounded and request failure closes connection | `test_read_timeout_is_bounded`, `test_request_exception_closes_connection_without_retry` |
| Unknown shell/tool, malformed action and finite correction budget | Existing protocol/dispatch units and `test_second_protocol_error_terminates_without_tool_execution` |

This is a behavior matrix, not a claimed percentage from a coverage tool.
It validates a real HTTP protocol boundary with fictional data. Real Ollama
server/model versions, prompt/model digest capture, live quality and costs are
unmeasured. The adapter uses no API key and the offline commands never opt in
to it. Server/model provisioning and live evaluation are outside this release.

All source/probe authority, state-transition and budget enforcement sits in
host code rather than provider instructions. See `ARCHITECTURE.md` for the
execution and trust boundary, and `EVIDENCE.md` for checks actually run.
