# Projektplan – colibri-rocm

## Mission
MoE-Modelle (GLM-5.3-Flash 321B / GLM-5.2 744B, int4) per NVMe-Streaming auf dem
GMKtec EVO-X3 zum Laufen bringen – mit GPU-Beschleunigung über die Radeon 8060S.

## Phase 0 – Grundlagen (abgeschlossen 2026-09-11)
- [x] Colibri 1.10.2 CPU-Build (`/home/sascha/colibri`, venv `~/.venvs/colibri`)
- [x] Model-Store `/home/sascha/models/colibri_store`, NVMe-I/O 10.1 GB/s
- [x] Toolchain-Audit: hipcc 5.7 (Ubuntu, **zu alt für gfx1151**),
      ROCm 7.2 vorhanden unter `~/local/rocm-extract` (gfx1151-fähig, aus XTTS)
- Details: `docs/audit-2026-09-11.md`

## Phase 1 – Feasibility-Spikes (max. 2 Abende, Timebox!)
### Spike A: Vulkan-Backend (bevorzugt – existiert bereits upstream)
- Colibri `backend_vulkan.c` gegen RADV (Mesa, gfx1151) kompilieren
- Kleiner GEMM-Bench: `make vulkan && ./coli bench --gpu vulkan` o.ä.
- Erfolgskriterium: messbar schneller als CPU-Pfad (AVX-512, 16 Threads)

### Spike B: HIP-Toolchain mit ROCm 7.2
- `~/local/rocm-extract/bin/hipcc --version` → gfx1151 im Target-List?
- hipBLAS/rocBLAS in `rocm-extract/lib` vorhanden? (sonst: Teil-Build aus Source)
- Minimaler HIP-GEMM-Bench vs. CPU-Baseline

### Spike C: Ollama-Vergleichsbasis
- Qwen3.8-Flash-Next auf Ollama/ROCm als Speed-Referenz (~8–12 tok/s erwartet)

## Phase 2 – Go/No-Go (Entscheidungspunkt)
| Kriterium | Schwelle |
|---|---|
| GPU-Pfad schneller als CPU? | ≥ 1.5× |
| Portierungsaufwand vertretbar? | < 2 Wochen Teilzeit |
| Modell passt ins RAM-Budget? | ≤ 100 GB resident |

Nein → bei CPU-only bleiben, Projekt auf „beobachten" stellen.
Ja → Phase 3.

## Phase 3 – Port / Integration
- Patches gegen upstream in `patches/` (ableitbar von `git diff`)
- Memory-Tiering: Colibri-Layer mit unified memory konfigurieren (kein PCIe-Paging)
- `coli serve --port 8090` als systemd-Service, OpenAI-kompatibel

## Phase 4 – Modell & Betrieb
- Download GLM-5.3-Flash int4 (~195 GB) via `hf` mit Resume → Store-Verzeichnis
- Erster Chat-Start, Token/s messen, in `docs/benchmarks.md` protokollieren
- Optional: Kernel-Tuning (`vm.max_map_count`, AIO), numactl-Interleave

## Geschätzter Gesamtaufwand
- Phase 1: 2–4 h
- Phase 3: 1–3 Wochen (nur bei Go)
- Phase 4: 1 Tag + Download-Zeit

## Regeln
- Kein 370-GB-Download vor Phase-2-Entscheidung.
- Upstream respektieren: Patches maintainable halten, ggf. PR einreichen.
- Alle Messungen in `docs/` ablegen (Datum, Kommando, Ergebnis).
