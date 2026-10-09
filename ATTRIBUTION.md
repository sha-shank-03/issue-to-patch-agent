# Attribution and technical choices

Original Python code, Java fixtures/probes, task text and documentation are
authored for this repository and licensed under MIT. No external code, defect
dataset or model weights are copied or redistributed.

Python 3.11 standard-library modules provide execution, HTTP, JSON, CLI and
tests. Python uses the [PSF license](https://docs.python.org/3.11/license.html).
The separately installed Microsoft JDK 17 uses
[GPLv2 with Classpath Exception](https://learn.microsoft.com/en-us/java/openjdk/faq).
Neither runtime is bundled. The Java runner uses the documented
[javac](https://docs.oracle.com/en/java/javase/17/docs/specs/man/javac.html) and
[java](https://docs.oracle.com/en/java/javase/17/docs/specs/man/java.html) options.

The optional adapter follows Ollama's official
[chat protocol](https://docs.ollama.com/api/chat) and
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
Ollama server source is [MIT licensed](https://github.com/ollama/ollama/blob/main/LICENSE);
weights have separate licenses and none are included. Actual server/model
versions remain untested. Local-only prerequisites are documented in the
[Ollama FAQ](https://docs.ollama.com/faq).

[SWE-agent](https://github.com/SWE-agent/SWE-agent),
[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) and
[OpenHands](https://github.com/OpenHands/OpenHands) are prior art for development
agents. Our contribution is Java semantic outcomes and independently rejected
false fixes, rather than a general agent framework. The
[Codex Core Agent role](https://openai.com/careers/applied-ai-engineer-codex-core-agent-san-francisco/)
illustrates demand for coding-task and regression evaluation; no employer
endorsement is implied. Primary references were reviewed on 2026-10-08.

CI uses these official MIT-licensed actions, resolved on 2026-10-08 to full
commit SHAs via their fixed release tags:

| Action | Release | Pinned commit |
| --- | --- | --- |
| [checkout](https://github.com/actions/checkout/releases/tag/v7.0.1) | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| [setup-python](https://github.com/actions/setup-python/releases/tag/v7.0.0) | v7.0.0 | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| [setup-java](https://github.com/actions/setup-java/releases/tag/v6.0.1) | v6.0.1 | `de7274f081f381c8f8158605e0321c36c376e2e6` |

Actions are referenced by configuration rather than vendored into application
source. No action, Python runtime or JDK was downloaded/executed while preparing
M3 source. Hosted CI would provision those runtimes on its runners after an
authorized publication. Standard runners are free for public repositories;
larger runners/private repository usage have different billing. [Official billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

The baseline and repeat harness is original code. Its candidate/context pairing
is an authored control-flow ablation; no external benchmark, model transcript,
salary claim, employer endorsement or trained-model performance is attributed
to these results. GitHub workflow execution and live model evaluation remain
unexecuted. `docs/ci-actions.json` retains the source/version receipt.
