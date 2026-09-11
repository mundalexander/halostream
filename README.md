# colibri-rocm

Portierung der [Colibri](https://github.com/JustVugg/colibri)-C-Engine auf AMD ROCm/HIP,
um MoE-Modelle der GLM/Kimi-Klasse (300B–744B) per NVMe-Streaming auf dem
GMKtec EVO-X3 (AMD APU, unified memory) laufen zu lassen.

## Zielhardware

| Komponente | Spec |
|---|---|
| CPU | AMD Ryzen AI MAX+ 395, 16C/32T, Zen5, AVX-512 (inkl. BF16/VNNI) |
| GPU | Radeon 8060S iGPU, **gfx1151**, 40 CUs |
| RAM | 128 GB unified (CPU+GPU geteilt!) |
| Storage | NVMe, ~10 GB/s gemessen |

## Ausgangslage (Stand 2026-09-11)

- ✅ Colibri 1.10.2 CPU-Build läuft (`/home/sascha/colibri`, venv `~/.venvs/colibri`)
- ✅ `coli` CLI funktioniert, Model-Store `/home/sascha/models/colibri_store` (10.1 GB/s I/O)
- ✅ `hipcc` 5.7 vorhanden (Ubuntu-Paket) — **aber zu alt für gfx1151**
- ✅ ROCm 7.2 liegt bereits unter `~/local/rocm-extract` (aus XTTS-Projekt, gfx1151-fähig)
- ❌ Kein HIP-Backend in Colibri (nur CUDA, Metal, Vulkan)
- ❌ hipBLAS/rocBLAS für ROCm 7.2 noch nicht verifiziert

## Strategische Optionen

1. **Vulkan-Pfad** — Colibri hat bereits `backend_vulkan.c`. Wenn der auf RADV
   (gfx1151) läuft, ist das der mit Abstand günstigste Weg. **Zuerst evaluieren!**
2. **HIP-Port** — `backend_cuda.cu` → HIP mit ROCm 7.2 Toolchain.
   Vorteil unified memory: kein PCIe-Kopieren nötig, GPU sieht dieselben PAGES.
3. **CPU-only AVX-512** — funktioniert bereits, ~0.5–2 tok/s, nur als Fallback/Baseline.

## Meilensteine

- [ ] M0: Toolchain-Audit (erledigt, siehe `docs/audit-2026-09-11.md`)
- [ ] M1: Feasibility-Spike — Vulkan-Backend auf gfx1151 testen; hipBLAS-Bench mit ROCm 7.2
- [ ] M2: Go/No-Go — Entscheidung Vulkan vs. HIP vs. CPU-only
- [ ] M3: Backend-Port (Kernel + Memory-Tiering-Anbindung)
- [ ] M4: Integration `coli serve` Port 8090, OpenAI-API
- [ ] M5: Benchmark GLM-5.3-Flash (321B int4, ~195 GB) vs. Baseline

## Risiken

- gfx1151-Support in ROCm 7.2 ist für XTTS (PyTorch) bewährt, aber rocBLAS-GEMM
  auf einer 40-CU-iGPU bringt evtl. wenig Gewinn gegenüber 16 Zen5-Kernen.
- Unified Memory: GPU-Compute konkurriert mit CPU um dieselbe RAM-Bandwidth (~256 GB/s).
  Der Colibri-Bottleneck ist aber ohnehin Storage→RAM Streaming.
- 370 GB Modell-Download: nur mit `hf` resume-fähig laden, Store bleibt auf NVMe.

## Projektstruktur

```
colibri-rocm/
├── README.md          # dieses Dokument
├── PLAN.md            # detaillierter Phasenplan
├── docs/              # Audits, Messungen, Entscheidungen
├── spike/             # Wegwerf-Tests (Vulkan/HIP-Benchmarks)
└── patches/           # Patches gegen upstream colibri
```

Upstream: https://github.com/JustVugg/colibri (Patches fließen idealerweise zurück).
