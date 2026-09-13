# Strix Halo Toolboxes — Recherche 2026-09-13

> Quelle: github.com/kyuz0/amd-strix-halo-toolboxes (daniel capitella)
> Pre-built llama.cpp-Container für GENAU unsere Hardware: AMD Ryzen AI Max+ 395,
> gfx1151 (Radeon 8060S), 128 GB Unified Memory.

## Was das Projekt bietet

1. **Stabile Container** (auto-rebuild bei llama.cpp-master-Update):
   - `vulkan-radv` — Vulkan (Mesa RADV), "most stable, recommended for most users"
   - `rocm-10.0` — ROCm 10.0 (Fedora 44), AMDs offizieller gfx1151-Paketsatz

2. **Experimentelle Container** (Strix-Halo-spezialisierte Forks):
   - `rocm-10.0-qwen-3.8-flash-next` — **Qwen3.8-Flash-Next auf llama.cpp!**
     (drluoto/llama.cpp:strix-halo-flash-next): natives MTP, ngram-mod,
     **GPU TOP_K** (MoE-Expert-Selection auf der GPU — genau was glm53.c fehlt),
     GGML_HIP_NO_VMM=ON, kein rocWMMA
   - `rocm-10.0-engramhalo` — EngramHalo.cpp-Port, SSD-gestützte engram-Loads,
     MTP-Sidecar, sparse QSA gather
   - `vulkan-radv-performance` — Nathanw1014/llama.cpp:strix-halo-vulkan:
     Strix-Halo-Flash-Attention, KV-Cache- und MoE-Performance-Work
   - `rocm-10.0-rocmfpx` — ROCmFPX mit **ROCmI4/W4A4 und FP3/FP4/FP6/FP8**
     Gewichtsformaten + MTP + agent-aware presets (HIP-only, kein rocWMMA nötig!)

3. **Host-Tuning** (das fehlt bei uns komplett!):
   - Kernel-Parameter `amd_iommu=off` (in den Benchmark-Metadaten!)
   - TuneD-Profil `accelerator-performance`
   - GPU-Workload-Watcher (systemd): Framework-Kühlung + TuneD-Umschaltung,
     erkennt llama.cpp, DS4, hipfire, vLLM, Halogen Flash API
   - `gguf-vram-estimator.py` für Memory-Planung mit Kontext-Overhead

4. **ROCm-Workaround** für llama.cpp#25992 (Host-Buffer-Bug auf iGPUs):
   verhindert ROCm-Host-Buffer-Selektion auf integrierten GPUs —
   erklärt vermutlich unsere HIP-Build-Probleme.

## Benchmark-Daten (gleiche Hardware: 128 GB, Radeon 8060S)

### toolbox-performance-results.json (360 Punkte)

| Modell | Quant | Backend | tok/s (gen, ctx=128) |
|---|---|---|---|
| Qwen3.5-122B-A10B | Q4_K_XL | ROCm 7.2.4 | **21.6** |
| Qwen3.5-122B-A10B | Q4_K_XL | ROCm 7.2.4, ctx=65664 | 15.4 |
| DeepSeek-V4-Flash | IQ2_XXS | ROCm 7.14 | **16.2** |
| DeepSeek-V4-Flash | IQ2_XXS | vulkan-radv | 9.1 |
| DeepSeek-V4-Flash | IQ3_XXS | vulkan-radv-performance | 19.8 |
| Qwen3.6-35B-A3B | Q4_K_XL | vulkan-radv | 62.8 |
| Qwen3.6-35B-A3B | Q8_K_XL | ROCm 7.2.4 | 48.1 |
| Qwen3.6-27B (dense) | Q8_0 | ROCm 7.2.4 | 7.8 |
| gemma-4-26B-A4B | Q8_K_XL | ROCm 7.2.4 | 41.8 |

### Vergleich mit unserem Setup

| Modell | Aktiv/Token | Stack | tok/s |
|---|---|---|---|
| Qwen3.5-122B-A10B | 10B | llama.cpp + ROCm | **21.6** |
| DeepSeek-V4-Flash | ~10B | llama.cpp + ROCm | **16.2** |
| Qwen3.8 (Halogen) | ? | Halogen binary + hipBLASLt | 29 |
| **GLM-5.3-Flash (colibri)** | **9.7B** | **CPU-Expert-Pfad** | **0.34** |

**Schlussfolgerung:** Ein 9-10B-aktives MoE erreicht auf dieser Hardware
15-22 tok/s. Unser GLM-5.3 liegt Faktor 50 darunter — reines Software-Problem
(CPU-Experten in glm53.c), kein Hardware-Limit. Option A (GPU-Umbau, Potenzial
10-15 tok/s) ist durch Fremddaten validiert.

## Was wir daraus übernehmen sollten

1. **Sofort umsetzbar (Host-Tuning):**
   - `amd_iommu=off` Kernel-Boot-Parameter prüfen/setzen
   - TuneD-Profil `accelerator-performance` installieren
   - GPU-Workload-Watcher für Kühlung (Framework-Geräte)

2. **Als Alternative zu Halogen (open source, gleiche Modellklasse):**
   - `rocm-10.0-qwen-3.8-flash-next` Container: Qwen3.8-Flash-Next auf
     llama.cpp mit MTP + GPU TOP_K — open, getestet, für unsere Hardware gebaut

3. **Für ein anderes großes MoE lokal (llama.cpp-kompatibel):**
   - DeepSeek-V4-Flash GGUF (16.2 tok/s) oder Qwen3.5-122B-A10B (21.6 tok/s)

4. **Für GLM-5.3 bleibt:** Option A (Colibri-Expert-Pfad auf GPU umbauen),
   da GLM-5.3-Flash nicht als GGUF vorliegt (colibri-Container-Format, exklusiv).

5. **ROCm-Workaround patch** (toolboxes/llama-cpp-25992-rocm-host-buffer.patch)
   dokumentiert, warum unser HIP-Build auf der iGPU scheiterte — für den
   Fall dass wir später doch den ROCm-Weg für glm53 gehen wollen.