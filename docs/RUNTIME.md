# LM Studio and the recovered template

## Explicit setup requirement

Install LM Studio yourself. Download
`lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF`, file
`Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` (4,920,739,168 bytes in the validated setup).
Verified upstream revision: `8601e6db71269a2b12255ebdf09ab75becf22cc8`.
Verified GGUF SHA-256: `f2be3e1a239c12c9f3f01a962b11fb2807f8032fdb63b0a5502ea42ddef55e44`.
The installed file exactly matches the upstream LFS artifact. If downloading
outside LM Studio, select that repository revision and import the file into LM Studio.
Accept the upstream Llama terms. Use instance identifier
`meta-llama-3.1-8b-instruct`; keep other language models unloaded.

In this model's LM Studio prompt-template settings, select Jinja and paste the
complete contents of `runtime/llama31.jinja`. Save it **for this model**, then
reload the model. Do not modify weights or global instructions. Export/copy the
active template to a local `.jinja` file and pass it to `doctor.py --template-config`.
The doctor also accepts the saved per-model JSON containing `llm.load.promptTemplate`.
Do not mistake checking the repository template itself for checking active settings.

Enable the local OpenAI-compatible server on `localhost:1234`; do not expose it
to the LAN. Authentication is not configured in this candidate. The application
uses direct loopback HTTP, ignores HTTP proxy settings, and does not follow
redirects. Port is configurable; cloud inference hosts are deliberately unsupported.

The validated development runtime reports context length **51,200**, parallel
slots **4**, evaluation batch **2,048**, physical batch **512**, flash attention
and KV offload enabled. These allocations carry substantial memory/swap cost.
For strict baseline comparison use those values. The existing auto-loader requests
16,384 tokens and one slot, but saved LM Studio settings can take precedence.
Inspect actual loaded settings using `/api/v1/models`; do not assume CLI requests
overrode saved configuration. This discrepancy is explicit and deferred to Phase
13 measurement rather than quietly changing the memory/performance baseline.

## Exact historical modification

Recovered from the installed GGUF's `tokenizer.chat_template`, compared byte for
byte against the saved per-model override. The only change adds these lines
immediately after the `custom_tools` assignment block:

```jinja
{#- Empty or missing tools must not activate function-call instructions. #}
{%- if tools is not defined or not tools %}
    {%- set tools = none %}
{%- endif %}
```

The stock template tests `tools is not none`; an empty list is not `none`. It can
therefore inject native function-call instructions and consume the first user
message even when no functions are supplied. The correction normalizes missing
and empty lists. Explicit nonempty tools still render normally. No fine-tuning,
LoRA, model training or weight changes occurred.

Kuzco uses its own bounded JSON decision protocol and deterministic Python tool
authorization. Its schemas live in the request/system context; it does not ask
LM Studio to execute native tools. The release requests explicitly set
`tool_choice: "none"`; this documents that distinction, but is **not claimed as
a proven replacement for the template correction**.

## Why the explicit template remains

The REST chat API works on the current runtime. Official Python SDK 1.5.0 source
exposes per-prediction `promptTemplate`, but the bounded local probe could not
open its `ws://localhost:1234/llm` connection: the server returned HTTP 200 rather
than a WebSocket upgrade. No saved setting was reset, and no transport was
replaced to force this experiment. The SDK is not a candidate dependency.

The accepted fallback is therefore an **explicit, versioned template requirement**,
with an exact comparison check and local no-tools/structured-output probes.
The development override remains identical to this file. This resolves the hidden
dependency by making it part of installation; it does not claim stock-template
independence. Normal runtime/model weights remain unmodified. Revisit removing
the override only after a supported replacement is demonstrated.

Corrected-template SHA-256:
`99ad124d24124d52abe41296654fa0275e7ba840bf7272189a14135f019b37a9`.

Sources: [LM Studio template settings](https://lmstudio.ai/docs/app/advanced/prompt-template),
[REST load configuration](https://lmstudio.ai/docs/developer/rest/load),
[official SDK mapping](https://github.com/lmstudio-ai/lmstudio-python/blob/main/src/lmstudio/_kv_config.py).
Template provenance: Meta Llama 3.1 tokenizer template in the named GGUF; correction
by Kuzco development. See `runtime/LLAMA_LICENSE` and `runtime/NOTICE`.


## Fresh-install validation settings

The promotion validation used the installed runtime reporting Bionic 1.1.1 (build 5), with its LM Studio-compatible API. For this exact baseline, disable automatic hardware optimization in the model load settings and explicitly set context length to 51,200; verify the actual loaded values listed above. In Local Model API settings keep verbose request logging off, content redaction on, and CORS off. Bind only to loopback. These settings were applied explicitly during the fresh installation; they must not depend on inherited development configuration.
