# Research: extraction model — keep `alibayram/medgemma:27b` or move to Gemma 4?

*Researched 2026-07-08 against primary sources (Google/DeepMind release notes, HuggingFace model
cards, Ollama library pages). Context: structured JSON extraction from badly formatted German OCR
text (medical letters, lab reports), Ollama backend, 24 GB GPU (RTX 3090/4090 class).*

## 1. Does "Gemma 4" exist? Yes — and the user's sizes are correct

Gemma 4 shipped **March 31, 2026** (announced April 2) in sizes **E2B, E4B, 31B dense, and
26B A4B** (a mixture-of-experts model with ~3.8–4 B active parameters); a **12B Unified**
multimodal variant followed on June 3, 2026
([Gemma releases page](https://ai.google.dev/gemma/docs/releases),
[Google announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)).
So "gemma4:31b" and "gemma4:26b" are real Ollama tags, not misrememberings
([ollama.com/library/gemma4](https://ollama.com/library/gemma4)).

Headline claims from the announcement and the
[HuggingFace launch post](https://huggingface.co/blog/gemma4):

- Apache 2.0 license; built on Gemini 3-generation research.
- **Natively trained on 140+ languages** (German included).
- **256K context** on 12B/26B/31B (128K on E2B/E4B).
- **Native function calling, structured JSON output, and system instructions** — directly relevant
  to our extraction pipeline.
- MMLU-Pro: 31B **85.2**, 26B A4B **82.6**, vs Gemma 3 27B **67.6**. LMArena (text): ~1452 (31B) /
  ~1441 (26B). No IFEval numbers were published in the launch materials.

## 2. What MedGemma 27B actually is

- MedGemma (May 20, 2025) is a set of **Gemma 3** fine-tunes. The 27B exists as **text-only**
  (`medgemma-27b-text-it`) and, since July 2025, multimodal
  ([HF model card](https://huggingface.co/google/medgemma-27b-text-it),
  [releases page](https://ai.google.dev/gemma/docs/releases)).
- Its wins over base Gemma 3 27B are on **medical QA benchmarks** (MedQA 89.8 vs 74.9, MedMCQA
  74.2 vs 62.6) — knowledge/reasoning, not extraction. The card explicitly warns MedGemma "may make
  it **more sensitive to the specific prompt** used than Gemma 3", and the
  [MedGemma 1.5 technical report](https://arxiv.org/html/2604.05081v1) notes medical tuning causes
  "degradation in general knowledge reasoning" vs base Gemma 3.
- **MedGemma 1.5 (Jan 13, 2026) is 4B-only and still Gemma 3-based** — there is **no MedGemma on
  Gemma 4** and no refreshed 27B
  ([model card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card)).
- [`alibayram/medgemma:27b`](https://ollama.com/alibayram/medgemma:27b) is a **community
  re-upload** (Google does not publish MedGemma in the official Ollama library): Q4_K_M GGUF of the
  text-only 27B, **17 GB**, 128K context. Functionally fine, but unmaintained by Google.

## 3. Extraction from noisy OCR + JSON fidelity

- The MedGemma 1.5 report does benchmark **structured JSON extraction from lab reports**
  (name/result/unit/range… macro-F1 of 64–91 % across four datasets), showing Google positions
  MedGemma for this task — but it publishes **no MedGemma-vs-base-Gemma comparison on extraction**;
  the head-to-head wins are all QA ([report](https://arxiv.org/html/2604.05081v1)).
- Gemma 4's launch materials, by contrast, make **first-party claims of native structured JSON
  output and function calling** ([announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)),
  plus a ~17-point MMLU-Pro jump over the Gemma 3 27B that MedGemma is built on.
- Net: extraction from noisy OCR is mostly an **instruction-following + schema-fidelity** problem,
  not a medical-knowledge problem. Medical tuning helps normalize terminology, but MedGemma's
  documented prompt sensitivity and general-reasoning regression cut the other way.

## 4. German

- Gemma 4: natively trained on **140+ languages**
  ([announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)).
- MedGemma: tuning corpus and all published evaluations are **English**; the card documents no
  multilingual results and red-teaming used "primarily English language prompts"
  ([HF card](https://huggingface.co/google/medgemma-27b-text-it),
  [MedGemma 1.5 card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card)).
  German medical letters are outside its evaluated envelope; it inherits German only from base
  Gemma 3.

## 5. VRAM on a 24 GB card (Ollama, from [gemma4 tags](https://ollama.com/library/gemma4/tags))

| Tag | Weights | Notes |
|---|---|---|
| `alibayram/medgemma:27b` (Q4_K_M) | ~17 GB | current default; ~6 GB left for KV cache |
| `gemma4:26b` (= 26b-a4b-it, Q4_K_M) | ~18 GB | MoE, **~4 B active** → much faster; `26b-a4b-it-qat` is 16 GB |
| `gemma4:31b` (Q4_K_M) | ~20 GB | dense; tight — `31b-it-qat` (19 GB) leaves ~4–5 GB for KV |
| `gemma4:31b-it-q8_0` | 34 GB | does not fit |

All fit at Q4, but 256K context is theoretical — on 24 GB keep `num_ctx` modest (8–16K covers even
long letters). The 31B at 20 GB risks CPU offload once the KV cache grows; prefer the QAT tag.

## Recommendation

**Switch, pending a cheap A/B.** MedGemma 27B's edge is English medical *QA*; our task is
schema-faithful *extraction* from noisy *German* text, where Gemma 4's native JSON/structured
output, 140+ language training, and large capability jump over its own base (Gemma 3 27B) should
dominate. There is no Gemma 4-based MedGemma to wait for, and `alibayram/medgemma` is a community
re-upload frozen at May 2025.

- **Primary candidate: `gemma4:26b`** (~18 GB, ~4 B active params). Comfortable on 24 GB with room
  for KV cache, and per-document latency should drop sharply vs the dense 27B.
- **Quality fallback: `gemma4:31b-it-qat`** (19 GB) if 26B loses the A/B — accept the tighter VRAM
  and keep `num_ctx` ≤ 8K.

**A/B is nearly free** (ADR 005: CLI owns backend+URL, admin UI owns model selection):
`ollama pull gemma4:26b`, switch the extraction model in the admin UI, re-run `/extract` on a fixed
set of ~10 real German letters/lab reports, and diff the JSON — the pipeline runs at
`temperature=0` (see `aiservice/README.md`), so outputs are directly comparable. Score field-level
correctness and JSON-parse failures. Note: `aiservice/models.json` already has a `gemma4` pattern
but only tags it for `classify`/`chat` — add `extract` to its `tasks` if the A/B wins, and update
the Model Options table in `aiservice/README.md`.
