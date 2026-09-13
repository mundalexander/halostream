# GLM-5.3-Flash Benchmark & Diagnose — 2026-09-13

## Ergebnis

| Konfiguration | tok/s | Anmerkung |
|---|---|---|
| CPU-Build (alte Binary) | 0.2 | `--ngen 1` Bug → 1 Token/Request |
| Vulkan-Build, kalter Cache | **0.34** | 150 Tokens in 7:22 min, kohärenter Text ✓ |
| Vulkan-Build, warmer Cache | **< 0.25** | Kein Speedup — CPU-limitiert |

**Vergleich Halogen (Qwen3.8):** 29 tok/s (hipBLASLt auf GPU, gleiche Hardware)

## Gefundene und gefixte Bugs heute

1. **`--ngen 1` = Token-Limit 1** — alle bisherigen Benchmarks generierten genau 1 Token
   (deshalb leere Antworten, `finish_reason: "length"`, completion_tokens: 1)
   → Fix: Server ohne `--ngen` starten (default = unbegrenzt)
2. **`--ram 0` = auto, aber falsch** — der Python-Wrapper `if a.ram:` ist bei 0 falsy,
   GLM53_EXPERT_GB wird nicht gesetzt, Engine misst selbst (freier RAM - 3 GB)
   → Fix: `--ram 68` → Wrapper setzt GLM53_EXPERT_GB=60.0 korrekt
3. **Fehlende Shader** — `rmsnorm.spv`, `attention_absorb.spv`, `qmatmul_gate_up.spv`
   mussten mit `glslc` aus `.comp` kompiliert werden (heute 14:23 erledigt, alle 4 aktiv)
4. **`coli serve` nutzt das Binary aus seinem Repo-Verzeichnis** (`/home/sascha/colibri/c/glm53`),
   nicht aus .venvs — Vulkan-Binary dort installiert (Backup: glm53.cpu.bak)

## Architektur-Erkenntnis (aus glm53.c Zeile 905-909)

> *"Mit COLI_VK=1 gehen die residenten Matrizen (Dense-Gewichte) durch Vulkan.
> Die Experten NICHT — das ist kein Versehen: Sie kommen bei jeder Nutzung von
> der Disk... Die brauchen ein VRAM-Residency-Level — das ist etwas anderes."*

**Die Engine-Architektur:**
- Dense-Gewichte (Attention, Norm, Router): → GPU via Vulkan ✓ funktioniert
- MoE-Experten (45 Layer × 288 Experten, 8 aktiv/Token): → **CPU** (int4-GEMM, AVX2)
- RAM-LRU-Cache (60 GB): reduziert NVMe-Misses, aber die CPU-GEMM-Rechenlast bleibt

## Warum kein Cache-Speedup?

Bei 0.3 tok/s = 3.3 s/Token werden 45 Layer × 8 Experten = **360 int4-GEMMs**
(à ~12.6 MB Gewicht) auf der CPU berechnet — ~4.5 GB Dequant+GEMM pro Token.
Der RAM-Cache eliminiert die Disk-Reads, aber die **CPU-Dequant-Leistung ist der
Flaschenhals**. 25 Kerne schaffen ~1.4 GB/s int4-GEMM — das ist das Deckel.

## Der GPU-Pfad ist MESSTECHNISCH VERIFIZIERT

Der offizielle VK_TEST-Harness (14:55 Uhr) beweist: **Alle Vulkan-Kernel laufen
korrekt und schnell auf GFX1151:**

```
expert_group fmt=2  8 experts | GPU-only 0.1374 ms/expert (ROCm 0.179)
expert_group fmt=5 32 experts | GPU-only 0.2107 ms/expert (ROCm 0.179)
BATCHED fused gate_up int4 6144->2048: 0.0711 ms (N=64)
fmt=5 S=1 I=16384 O=6144 | gpu=0.587 ms  cpu_ref=106.400 ms  → 181× schneller
```

**Potenzial mit GPU-Expert-Pfad:** 360 Experten × 0.15 ms ≈ 54 ms/Token für die
MoE-Phase → **~10-15 tok/s** erreichbar (Attention + Overhead eingerechnet).

## Nächste Schritte (Entscheidung nötig)

**Option A — Expert-Pfad auf GPU umbauen (Feature-Arbeit in C):**
`coli_vk_expert_group()` ist im Backend implementiert und getestet, wird aber von
glm53.c nicht aufgerufen. Umbau: Expert-Forward im RAM-Cache-Hit-Fall von CPU-matmul
auf `coli_vk_expert_group()` umstellen (Upload RAM→GTT ist auf Strix Halo zero-copy).
Aufwand: ~3-6h C-Arbeit. Potenzial: 0.34 → ~10-15 tok/s.

**Option B — Halogen als primäre Engine (läuft bereits):**
Qwen3.8-Flash-Next, 29 tok/s, Port 8731, GUI fertig (commit aa73a90).

## Infrastruktur-Status

- Vulkan SDK: installiert (`libvulkan-dev`, `glslc`)
- Vulkan-Binary: `/home/sascha/colibri/c/glm53` (mit 29 coli_vk_* Symbolen)
- Shader: `/home/sascha/colibri_shaders/*.spv` (4 Stück, alle kompiliert)
- Server-Script: `halostream/tools/glm_serve_gpu.sh start|stop|status`
- GLM int4-Container: `/home/sascha/models/colibri_store/glm53_i4` (194.7 GB, 62 Shards)