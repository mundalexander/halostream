# Projektplan – HaloStream

## Mission
MoE-Modelle der GLM-5.3-Klasse per NVMe-Streaming auf dem GMKtec EVO-X3 betreiben —
heute über die Colibri-Engine auf CPU, perspektivich GPU-Beschleunigung über Vulkan.
Halogen dient als Serving-Referenz für Qwen3.8-Flash-Next auf demselben Silicon.

## Phase 0 – Grundlagen (abgeschlossen 2026-09-11)
- [x] Colibri 1.10.2 CPU-Build (`/home/sascha/colibri`, venv `~/.venvs/colibri`)
- [x] Model-Store `/home/sascha/models/colibri_store`, NVMe-I/O 10,1 GB/s
- [x] Toolchain-Audit: hipcc 5.7 (Ubuntu, zu alt für gfx1151),
      ROCm 7.2 unter `~/local/rocm-extract` (gfx1151-fähig)
- Details: `docs/audit-2026-09-11.md`

## Phase 1 – Feasibility (Stand 2026-09-12)

### Spike A: Vulkan-Backend
- [x] BUILD SUCCESS gegen RADV (Mesa 25.2.8, gfx1151) — `docs/spike-a-vulkan-build.md`
- [ ] Runtime-GPU-Test: blockiert, bis GLM-5.3-Flash vollständig geladen werden kann
      (Colibri lädt nur volle Modelle — kein Tiny-Fixture-Test möglich)

### Referenz: Halogen (peonist-ai, Inspektion 2026-09-12)
- Geschlossener ROCm-Binary-Server für Qwen3.8-Flash-Next auf Strix Halo
- Messlatte: 1.424 tok/s Prefill, 41,7 tok/s spekulativer Decode (32K-Prompt)
- Übertragbare Ideen: Count-Sort-Routing, Page-Cache/mlock-Strategie,
  Quality-Sidecar-Prinzip, KV-Pool-Sharing, MTP-Drafting
- Details: `spike/halogen_comparison.log`

## Phase 2 – Go/No-Go (nach erstem Load, heute abend)
| Kriterium | Schwelle |
|---|---|
| CPU-Streaming-Loop funktioniert? | Chat antwortet korrekt |
| Token-Rate interaktiv? | ≥ 3 tok/s |
| GPU-Pfad schneller als CPU? | ≥ 1,5× (nach Vulkan-Runtime-Test) |

Nein → CPU-only belassen, Projekt „beobachten". Ja → Phase 3.

## Phase 3 – Port / Integration (nur bei Go)
- Vulkan-Backend in die Serving-Pipeline integrieren
- Memory-Tiering, `coli serve` als systemd-Service, OpenAI-kompatibel
- Patches in `patches/`, Upstream-PR erwägen

## Phase 4 – Modell & Betrieb

### Runbook „Erster Start GLM-5.3-Flash" (heute abend)
1. **Download abwarten:** `systemctl --user is-active colibri-glm53-dl` → inactive.
   Sanity: `du -sh /home/sascha/models/colibri_store/glm53_flash` ≈ 328 GB, 62 Shards.
2. **Remap:** `python3 /home/sascha/halostream/spike/remap_glm53.py`
   — Zero-Copy: patched nur `model.safetensors.index.json`
   (`model.language_model.*` → `model.*`), Backup `.pre_remap`,
   verifiziert kritische Tensoren (Layer 0/44, lm_head, embed_tokens).
3. **Erster Load-Test** (konservativ starten, LM Studio ggf. Models entladen):
   `~/.venvs/colibri/bin/coli --model /home/sascha/models/colibri_store/glm53_flash chat`
   Bei Problemen: `coli doctor`, `--ram` reduzieren, `--ctx` klein halten.
   Engine-Support ist nativ (`c/glm53.c`) — Debug-Fokus: Loader-Keys & RAM-Budget.
4. **Messen:** tok/s in `docs/benchmarks.md` (Datum, Kommando, Ergebnis).
5. **Serve-Modus:** `coli --model … serve` — OpenAI-kompatibel; danach
   Optional: als Standard-Provider bei OpenClaw eintragen.

### Modell-Fakten (korrigiert 2026-09-12)
- zai-org/GLM-5.3-Flash: **fp8, 328 GB gesamt**, 62 Shards, 76.108 Tensoren.
  Die alte Plan-Zahl „int4 ~195 GB" war falsch — keine int4-Variante auf HF.
- Glm5Next: 45 Layer, 288+1 Experten (8 aktiv/Tok), MLA/MQA/Indexer, MTP-Head.
- Upstream-Kommentar: „Misurato su GLM-5.3 (391 GB di container, 25 GB di RAM)"
  — das NVMe-Streaming-Design ist exakt für diese Modellgröße gebaut.

### Halogen-Track (Qwen3.8-Flash-Next — Ziel: schneller als LM Studio)
1. Checkpoint (~130 GB): auto-gekettet nach GLM-Download
   (`systemctl --user status halogen-ckpt-chain`, Ziel `/home/sascha/models/halogen_store`)
2. Docker installieren (docker.io + docker-compose-v2) — Freigabe pending
3. Deployment: docker-compose aus `spike/halogen_ref/`
   (Engine-Loopback + API-Port 8731; Model-Store mounten)
4. Benchmark: `tools/halogen-bench.py` + `tools/bench-serving.py` (aus dem
   Halogen-Repo) gegen LM-Studio-Baseline (qwen3.8-flash-next, aktuelle Raten messen)
5. RAM-Konflikt beachten: Halogen mlock't ~96 GiB — nicht gleichzeitig mit
   GLM-Load-Tests betreiben; LM Studio vorher Modelle entladen lassen.

### GLM-5.2 int4 (glm52_i4) — PAUSIERT
- Download steht bei 251/370 GB (209 Shards offen), beim Gateway-Restart gestorben.
- Regel „kein 370-GB-Download vor Phase-2-Entscheidung" → weiter pausiert.

## Regeln
- Upstream respektieren: Patches maintainable halten, ggf. PR einreichen.
- Alle Messungen in `docs/` ablegen (Datum, Kommando, Ergebnis).
- Downloads nur als systemd-User-Units starten (Session-Kinder sterben mit
  Gateway-Restarts — gelernt am 2026-09-12).