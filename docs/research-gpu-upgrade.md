# Research: GPU upgrade for the shared AI host — PRO 6000 vs DGX Spark vs dual 3090

*Researched 2026-07-08 against primary sources (NVIDIA spec pages, geizhals.de listings, ggml-org
llama.cpp benches, Ollama/LMSYS/vLLM benchmark posts). Context: one Ollama/vLLM host serves all
customer Deployments (ADR 024); today an RTX 3090 24 GB runs `glm-ocr` (~2 GB) + one 17–18 GB
extraction/chat model. Interactive RAG chat is the latency-sensitive workload; the user is leaning
toward vLLM with preloaded models for multi-customer serving (`aiservice/backend.py` already has
`VllmBackend`).*

## 1. Verified specs and July-2026 German street prices

| Option | Memory | Bandwidth | TDP | Street price (DE) |
|---|---|---|---|---|
| RTX PRO 6000 Blackwell WS | 96 GB GDDR7 ECC | **1,792 GB/s** | 600 W | €12,499–12,790 (geizhals.de); from €9,899 EU-wide |
| RTX PRO 6000 Max-Q | 96 GB GDDR7 ECC | 1,792 GB/s | **300 W** | from €10,160 (PNY) |
| RTX PRO 5000 Blackwell **72 GB** | 72 GB GDDR7 ECC | 1,344 GB/s | 300 W | €7,190–7,257 (PNY) |
| RTX PRO 5000 Blackwell 48 GB | 48 GB GDDR7 ECC | 1,344 GB/s | 300 W | €5,588–5,699 |
| DGX Spark (GB10) | 128 GB LPDDR5x unified | **273 GB/s** | 140 W chip / 240 W PSU | €4,249–5,399 (NVIDIA raised FE to €4,800) |
| ASUS Ascent GX10 (GB10 clone) | 128 GB unified | 273 GB/s | same | from €3,659 |
| AMD Strix Halo mini-PC (Ryzen AI Max+ 395) | 128 GB unified | 256 GB/s | ~140 W | ~€1,800–2,500 (GMKtec EVO-X2, Beelink GTR9, Framework) |
| Used RTX 3090 | 24 GB GDDR6X | 936 GB/s | 350 W (280 W limited) | **€700–950** (Kleinanzeigen, re-inflated by AI demand) |

Sources: [NVIDIA PRO 6000 family](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-family/),
[PRO 5000](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-5000/) +
[72 GB launch](https://videocardz.com/newz/nvidia-rtx-pro-5000-blackwell-gpu-with-72gb-gddr7-memory-is-now-released),
[DGX Spark](https://www.nvidia.com/en-us/products/workstations/dgx-spark/),
[AMD Ryzen AI Max+ 395](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html),
geizhals.de listings ([PRO 6000](https://geizhals.de/nvidia-rtx-pro-6000-blackwell-workstation-edition-900-5g144-2500-000-a3476784.html),
[Spark FE](https://geizhals.de/nvidia-dgx-spark-founders-edition-940-54242-0005-000-a3635144.html),
[PRO 5000 72GB](https://geizhals.de/pny-rtx-pro-5000-blackwell-vcnrtxpro5000b72-pb-a3686514.html)),
[Kleinanzeigen 3090](https://www.kleinanzeigen.de/s-pc-zubehoer-software/grafikkarten/rtx-3090/k0c225+pc_zubehoer_software.art_s:grafikkarten).
No DGX Spark successor announced as of July 2026. Spark caveats: throttling in the 150 mm cube
([StorageReview thermal test](https://www.storagereview.com/review/nvidia-dgx-spark-thermal-test-how-oem-cooling-designs-stack-up)),
ARM64 DGX OS stack still maturing ([llama.cpp #18254](https://github.com/ggml-org/llama.cpp/discussions/18254)).

## 2. Measured inference numbers, ~27–32B dense Q4 (the models we actually run)

| Hardware | Model | Prefill t/s | Decode t/s | Source |
|---|---|---|---|---|
| DGX Spark | gemma3:27b q4_K_M | 834 | **10.8** | [Ollama Spark blog](https://ollama.com/blog/nvidia-spark-performance) |
| DGX Spark | qwen3:32b q4_K_M | 705 | 9.4 | same |
| RTX 3090 (1x) | 27B-class Q4, llama.cpp | — | **~26–35** | [mustafa.net benches](https://mustafa.net/llm-tokens-per-second-benchmarks/); cross-checked vs [5090 Ollama numbers](https://github.com/ollama/ollama/issues/9701) scaled by bandwidth |
| 2x RTX 3090, vLLM TP=2 | Qwen3.6-27B AWQ-INT4 | — | **90–96** (120 on code) | [tfriedel/qwen3.6-rtx3090-lab](https://github.com/tfriedel/qwen3.6-rtx3090-lab), [Derek Armstrong](https://derekarmstrong.dev/blog/running-qwen36-27b-dual-rtx-3090-vllm-v019/) |
| 2x RTX 3090, llama.cpp `-sm tensor` | Qwen 27B | — | ~70 | [dev.to b9455 writeup](https://dev.to/yiqinumber1/llamacpp-b9455-finally-caught-vllm-70ts-on-2x3090-qwen-27b-uq8-1m74) |
| RTX PRO 6000 | gemma3:27b q4 (Ollama) | — | **~61** | [Databasemart bench](https://www.databasemart.com/blog/ollama-gpu-benchmark-pro6000) |
| RTX PRO 6000 | Qwen2.5-32B Q4_K_M llama-bench | 2,601 | 56 | [vaditaslim benches](https://www.vaditaslim.com/blog/ai/local-llm-benchmarks-rtx-pro-6000) |

- **The prior assessment is confirmed and quantified**: DGX Spark decodes a dense 27B Q4 at ~11 t/s
  — below comfortable reading speed for interactive chat, for *one* user, before any batching. Its
  prefill is respectable (Blackwell compute), but decode is nailed to the 273 GB/s ceiling. LMSYS
  reaches the same verdict ([review](https://www.lmsys.org/blog/2025-10-13-nvidia-dgx-spark/)):
  fine for prototyping and MoE, wrong tool for serving dense models. Spark's 128 GB only pays off
  for MoE (gpt-oss-120b: ~50–58 t/s) — our medgemma/gemma stack is dense.
- Gemma-3-architecture models (incl. medgemma:27b) decode measurably slower than same-size peers
  (5090: gemma3 50 t/s vs gemma2 76 t/s, [ollama#9701](https://github.com/ollama/ollama/issues/9701)).
- Ollama across 2 GPUs = layer split, **no decode speedup** (sometimes slower over PCIe):
  [Ollama FAQ](https://docs.ollama.com/faq), [ollama#7104](https://github.com/ollama/ollama/issues/7104).
  Real gains from a second 3090 come only via vLLM TP=2 (or llama.cpp's new `-sm tensor`).

## 3. Concurrency — what N customer Deployments actually need

- Ollama parallelism is slot-based (`OLLAMA_NUM_PARALLEL`, default 1; KV grows linearly with
  slots, [FAQ](https://docs.ollama.com/faq)). Measured multi-user: at 10 concurrent users Ollama
  ~150 t/s aggregate vs vLLM ~800; at 50 users Ollama TTFT ~3,200 ms vs vLLM ~145 ms
  ([Red Hat benchmark](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking),
  [SitePoint 2026](https://www.sitepoint.com/ollama-vs-vllm-performance-benchmark-2026/)).
  vLLM continuous batching is the right architecture for the shared host — matches the user's lean.
- vLLM supports `Gemma3ForConditionalGeneration`; Google ships a vLLM container for MedGemma
  ([model card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card)).
  vLLM on PRO 6000 (sm_120) is functional ([NVIDIA vLLM 25.09 notes](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-25-09.html));
  vLLM on DGX Spark is officially documented ([vLLM blog](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark)) — support isn't the Spark's problem, bandwidth is.
- Dual-3090 TP=2 practicality: works over plain PCIe x8/x8 (NCCL host-staged; GeForce P2P is
  driver-disabled). An NVLink bridge (3090 is the last GeForce with one) adds ~50% TP throughput
  ([4x3090 vLLM bench](http://himeshp.blogspot.com/2025/03/vllm-performance-benchmarks-4x-rtx-3090.html)) —
  worth the ~€100 used part but not required; the 90–96 t/s numbers above are achievable without it.
- Homelab fit: power-limit each 3090 to 280 W (~95% perf,
  [Puget quad-3090 study](https://www.pugetsystems.com/labs/hpc/quad-rtx3090-gpu-wattage-limited-maxq-tensorflow-performance-1974/));
  1200 W PSU suffices. Proxmox: LXC bind-mount of `/dev/nvidia*` shares both GPUs across
  containers, no VFIO ([Digital Spaceport guide](https://digitalspaceport.com/proxmox-multi-gpu-passthru-for-lxc-and-docker-ai-homelab-server/)).

## 4. Price/performance (dense 27B Q4 decode, single stream)

| Option | Cost | €/GB VRAM | tg t/s | €/(t/s) |
|---|---|---|---|---|
| Used 3090 (have it) | €0 sunk / €850 | 35 | ~30 | ~28 |
| **+1 used 3090, vLLM TP=2** | **~€900** marginal | ~35 | **~93** | **~18 (total ~€1,750)** |
| DGX Spark / GX10 | €3,659–5,219 | 33 | 10.8 | ~390 |
| Strix Halo 128 GB | ~€1,900 | 15 | ~10 (256 GB/s, est.) | ~190 |
| RTX PRO 5000 72 GB | ~€7,200 | 100 | ~45 (est., 75% of PRO 6000 bandwidth) | ~160 |
| RTX PRO 6000 (Max-Q) | €10,160–12,790 | 106–133 | ~61 | ~170–210 |

Single-stream €/(t/s) understates the big cards: under continuous batching, aggregate throughput
scales with bandwidth × KV headroom, where the PRO 6000's 96 GB and 1.8 TB/s dominate everything
else per box. The unified-memory boxes (Spark, Strix Halo) are capacity plays that our dense-model,
latency-sensitive workload cannot cash in.

## 5. Serving topology (grounded in `aiservice/backend.py`)

Decision baked in: the existing 3090 box is **not for sale** — end state is two boxes. Box A
(the upgrade under comparison) runs vLLM for classify/extract/chat via `AI_BACKEND=vllm` +
`VLLM_URL`; Box B (the 3090) runs Ollama via `OLLAMA_URL` for glm-ocr + `nomic-embed-text`,
with ~20 GB spare for an escalation VLM (e.g. `qwen3.6:35b` q4 ≈ 24 GB is too big; `qwen3.5:9b`
or a q4 27B fits — see research-vision-ocr-model.md). `get_vision_backend()` always requires
`OLLAMA_URL` (VllmBackend raises on images), so the vision split is pure config. **Embeddings are
not:** with `AI_BACKEND=vllm`, `get_embed_backend()` falls through to `get_backend()` — the vLLM
backend — and one vLLM instance serves one model. A one-line fix mirroring the existing Mistral
branch (route embed to `OLLAMA_URL`) completes the split; ship it before the topology change.

Box A candidates under that two-box shape:

- **RTX PRO 6000 (96 GB):** one vLLM instance, medgemma/gemma 27B AWQ-INT4 (~17–22 GB) or FP8
  (~28 GB) leaving **~55–70 GB KV** — dozens of concurrent long-context customer chats at ~61 t/s
  single-stream decode, no TP, no NCCL. Max-Q (300 W) fits homelab power/noise at ~€2k less than
  the 600 W edition with identical memory/bandwidth.
- **Dual 3090 (48 GB) as interim Box A:** buy one more used 3090 (~€900), vLLM
  `--tensor-parallel-size 2`, 27B AWQ (~21.5 GB weights ≈ 10.8 GB/card),
  `--gpu-memory-utilization 0.85` → ~7–8 GB/card KV ≈ roughly 8–12 concurrent 8K-context chats,
  90–96 t/s decode. Single-GPU 27B AWQ is *not* viable in vLLM (21.5/24 GB leaves ~0.7 GB, forces
  eager mode — tfriedel lab); TP=2 is what makes vLLM work at all on 3090s. In this stage one
  card's box doubles as Box B (Ollama shares the GPUs via LXC).
- **DGX Spark as Box A:** disqualified — 10.8 t/s decode shared among N customers is not
  interactive chat, regardless of serving stack. (As Box B it's also poor value: €4k+ to do what
  the existing 3090 already does faster.)

## Recommendation

**Interim: add a second used RTX 3090 (~€850–950) and move chat/extract to vLLM TP=2 now.
End state when customer count justifies it: RTX PRO 6000 Max-Q as the vLLM box, existing 3090
box stays on Ollama for glm-ocr + embeddings (+ escalation VLM). Do not buy the DGX Spark.**
The Spark's 273 GB/s gives a *measured* 10.8 t/s on gemma3-27B Q4 — one-third of the single 3090
we already own — and no software or clustering story fixes a bandwidth problem; its 128 GB serves
MoE workloads we don't run. The dual-3090 step costs ~7% of a PRO 6000 and delivers ~1.5× its
single-stream decode (90–96 vs ~61 t/s measured) plus real continuous batching for multi-customer
chat; add an NVLink bridge if one turns up cheap. Before either step, ship the one-line
`get_embed_backend()` fix so embeddings stay on Ollama (vision already can't go through
`VllmBackend`). When concurrent chats outgrow the dual-3090's ~14–16 GB of KV, the PRO 6000 Max-Q
(96 GB, 1.8 TB/s, 300 W, ~€10.2k) is the correct Box A — the RTX PRO 5000 72 GB (~€7.2k) is the
value alternative if 96 GB proves unnecessary — and the second 3090 either joins Box B or becomes
a dev card.
