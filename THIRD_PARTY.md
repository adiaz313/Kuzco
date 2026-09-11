# Third-party components and redistribution review

Kuzco application source: GPL-3.0-only, Copyright 2026 Kuzco contributors. This
candidate license does not relicense dependencies, templates, models or LM Studio.
The full GPL text is in LICENSE. The repository is source-only; no installed
packages, compiled binaries, datasets or voice/LLM weights are bundled.

| Component | Role and terms |
|---|---|
| uv | MIT/Apache-2.0 environment manager, user-installed; version pinned |
| Piper 1.8.0 | GPL-3.0 local synthesis; upstream [Piper](https://github.com/OHF-Voice/piper1-gpl), including its packaged third-party notices |
| northern_english_male medium | Downloaded from rhasspy/piper-voices; model card records OpenSLR 83 dataset CC-BY-SA 4.0 and Lessac fine-tuning; preserved card in runtime/ |
| Sherpa-ONNX 1.13.7 | Apache-2.0 software; CPU keyword spotting |
| Sherpa 2025-12-20 bilingual 3M weights | Separate upstream download. Archive contains no model-specific license. Do not assume the software license licenses the weights |
| Whisper.cpp pinned commit | MIT software, source downloaded and built locally; retains upstream LICENSE |
| Whisper tiny.en | Public upstream model download; Whisper MIT terms and upstream provenance apply |
| Meta Llama 3.1/GGUF template | Llama 3.1 Community License, not Kuzco GPL; notice/license included for derived template. Weights installed separately via LM Studio |
| LM Studio and Apple runtime/voices | Separately installed proprietary applications/system components; not redistributed |
| DDGS / Trafilatura | MIT / Apache-2.0 retrieval/extraction libraries; content sources retain their own rights |
| Keyring / defusedxml | MIT / PSF-2.0 secure OS storage adapter and XML protection |
| NumPy, sounddevice, CMake | BSD-family/MIT licenses; numerical/audio/build dependencies |

The lockfile retains exact package artifacts and hashes; installed wheels carry
their license metadata and bundled notices. `evaluation/dependency-licenses.json`
records the actual runtime distributions examined. If distributing wheels or a
prebuilt app later, preserve all wheel/source notices and corresponding-source
obligations (including Piper/eSpeak); this source-only candidate does not provide
such a binary distribution.

**Unresolved before public model bundling:** Sherpa model-weight terms remain
unconfirmed. [Upstream issue 3802](https://github.com/k2-fsa/sherpa-onnx/issues/3802)
and [3852](https://github.com/k2-fsa/sherpa-onnx/issues/3852) do not supply a definitive
weight license in the inspected replies. Keep the existing Sherpa architecture;
do not mirror or bundle the weights. The explicit installer retrieves the public
upstream archive after the user reviews these terms. This does not establish a
right to redistribute the model. Resolve with upstream before any public model
bundling or commercial-use claim. Piper voice redistribution likewise needs the
model/dataset attribution and share-alike review; do not relicense weights as GPL.

No real credentials or personal recordings were used for this licensing review.
No model training, upstream issue posting or public release was performed.
