# HaloStream

**GLM-5.3-Flash lokal auf dem GMKtec EVO-X3 betreiben** — mit der
[Colibri](https://github.com/JustVugg/colibri)-C-Engine, NVMe-Streaming und
(geplant) GPU-Beschleunigung über Vulkan.

> Früher `colibri-rocm` — umbenannt am 2026-09-12 (GitHub-Redirect bleibt aktiv).
> Die Engine selbst heißt weiter Upstream `colibri` (JustVugg); HaloStream ist
> unser Deployment-, Port- und Betriebsprojekt.

## Zielhardware

| Komponente | Spec |
|---|---|
| CPU | AMD Ryzen AI MAX+ 395, 16C/32T, Zen5, AVX-512 (inkl. BF16/VNNI) |
| GPU | Radeon 8060S iGPU, **gfx1151**, 40 CUs |
| RAM | 128 GB unified (CPU+GPU geteilt!) |
| Storage | NVMe, ~10 GB/s gemessen |

## Mission

1. **GLM-5.3-Flash** (321B MoE, fp8, 328 GB) per NVMe-Streaming auf der CPU
   betreiben — erste Inference heute abend.
2. GPU-Pfad über Vulkan evaluieren (Spike A: Build SUCCESS, Runtime-Test
   ausstehend — Colibri lädt nur volle Modelle, keine Tiny-Fixtures).
3. **Halogen** (peonist-ai/halogen-flash-server) als Serving-Referenz für
   Qwen3.8-Flash-Next auf demselben Silicon — Messlatte: 1.424 tok/s Prefill,
   41,7 tok/s spekulativer Decode. Ziel: schneller als unser aktuelles
   LM-Studio-Setup.

## Modell-Fakten (GLM-5.3-Flash)

- Architektur: `Glm5NextForConditionalGeneration` (model_type `glm5_next`,
  VL-Wrapper — deshalb Prefix-Remap nötig)
- 45 Transformer-Layer, **288 geroutete + 1 shared Experten**, 8 aktiv/Token
- MLA + MQA + DeepSeek-Sparse-Indexer, MTP-Head (`num_nextn_predict_layers=1`)
- Checkpoint: **fp8**, 62 Shards, 76.108 Tensoren, **328 GB**
  (zai-org/GLM-5.3-Flash — es gibt KEINE int4-Variante auf HF)
- Colibri-Loader erwartet `model.layers.N.*` → Zero-Copy-Remap über die
  Index-JSON (`spike/remap_glm53.py`; physische Shards unberührt, Backup
  `.pre_remap`)
- Engine-Support nativ: `c/glm53.c` im Upstream
  („GLM-5.3-Flash inference engine in pure C"); Streaming-Design ist für
  genau diese Größe gebaut (Upstream-Kommentar: „391 GB container, 25 GB RAM")

## Status (2026-09-13)

- [x] Phase 0: Colibri-Build (venv `~/.venvs/colibri`), Model-Store, 10,1 GB/s NVMe-I/O
- [x] Umbenennung colibri-rocm → **HaloStream** (GitHub + lokal)
- [x] Vulkan-Spike A: **BUILD SUCCESS** (Runtime-GPU-Test braucht das Modell)
- [x] GLM-5.3-Flash in Colibri-Container konvertiert (62 Shards, ca. 195 GB)
- [~] Halogen-Checkpoint (~130 GB): Auto-Kette startet nach GLM-Finish
      (`halogen-ckpt-chain` → `/home/sascha/models/halogen_store`)
- [x] Erster Load + Chat mit `coli` auf CPU/SSD-Streaming
- [ ] Vulkan-Laufzeitpfad auf gfx1151 verifizieren
- [ ] Halogen-Deployment per Docker + Benchmark vs LM Studio

## Struktur

- `PLAN.md` — Phasen, Entscheidungen, Runbook
- `docs/` — Audits & Benchmarks
- `patches/` — Patches gegen Upstream (maintainable, ggf. PR einreichen)
- `scripts/` — Betriebsskripte (`chain_halogen_download.sh`)
- `spike/` — Spike-Artefakte (Remap-Skript, Audits, Halogen-Inspektion)

## Regeln

- Kein 370-GB-Download (GLM-5.2 int4) vor der Phase-2-Entscheidung.
- Upstream respektieren: Patches maintainable halten, ggf. PR einreichen.
- Alle Messungen in `docs/` ablegen (Datum, Kommando, Ergebnis).
- Große Downloads nur als systemd-User-Units (Session-Kinder sterben mit
  Gateway-Restarts — gelernt am 2026-09-12).