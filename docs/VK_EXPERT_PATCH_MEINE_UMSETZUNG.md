# HaloStream — VK-Expert-Forward Patch (eigene Implementierung)

**Datum:** 2026-09-14 | **Hardware:** GMKtec/Strix Halo, Radeon 8060S (gfx1151), Server 51
**Patch:** `patches/glm53_vk_expert_clamped.patch` (254 Zeilen, 4 Dateien)
**Basis:** JustVugg/colibri v1.11.0+ (commit f028d26)

## Problem
GLM-5.3-Flash (321B MoE) decode auf glm53.c: 0.34 tok/s — CPU int4-Dequant-Deckel (~1.4 GB/s).
Der VK-Expert-Tier existierte nur in colibri.c (andere Engine); glm53.c nutzte Vulkan nur fuer dichte Matrizen.
Alexanders Patch (tools/patches/) war gegen aelteren Code und nicht anwendbar.

## Loesung (drei Teile)
1. **Slot-Tensoren** (glm53.c): LRU-Slots bekommen `void *vk[3]` (gate/up/down ColiVkTensor),
   persistent auf dem Device; `coli_vk_tensor_ensure` beim Cache-Miss, `coli_vk_tensor_free`
   bei LRU-Eviction (nur seriell, nie im OMP-Read-Loop).
2. **Batched Expert-Forward** (glm53.c ffn_layer): pro Cache-Block werden alle ensurebaren
   Experten als EIN `coli_vk_expert_group()`-Call gerechnet; CPU-Fallback nur fuer Nicht-VK-Experten.
3. **Swiglu-Clamp im Shader** (qmatmul_gate_up.comp + backend): neues Push-Constant-Feld
   `float limit`; Shader clamped wie C `swiglu_clamped` (g=min(g,L); u=clamp(u,-L,L)).
   Backend-API: `coli_vk_set_swiglu_limit()` — glm53.c setzt es beim Modell-Load.

## Wichtigste Learnings
- `swiglu_limit == 0` bedeutet NICHT "kein Clamp": C-Clamp mit 0 loescht das MLP.
  Echtes GLM-5.3 nutzt limit=10.0. Guard `limit==0 -> VK` war ein Trap.
- Der Upstream fused gate_up Shader clamped NICHT — ohne Shader-Aenderung GPU!=CPU.
- VK_TEST-Harness fmt=5: 0.112-0.20 ms/expert auf 8060S; 282x Speedup vs naive CPU.
- Build: `make VK=1 glm53 -j8` (glslc kompiliert .comp -> .spv automatisch).

## Verifikation (Server 51, 2026-09-14)
- `tests/test_glm53_vulkan.py` mit int4-Streaming-Fixture (glm53_mm_i4):
  **PASS — GPU == CPU, identische Token** (8 Positionen, 4 greedy Schritte)
- Debug-Log bestaetigt VK-EXPERT-Pfad aktiv (nvk=4 Batch, 16 Experten)
- E2E-Synthetik: 26.5 tok/s MoE-Phase projiziert (e2e_result.txt)

## Fixture-Rezept (Tiny int4, ohne 195GB-Download)
```
python3 tools/make_glm53_multimodal_tiny.py --output glm53_mm_tiny
python3 tools/convert_glm53.py --indir glm53_mm_tiny --outdir glm53_mm_i4
cp glm53_mm_tiny/{config.json,tokenizer.json,ref.json,patches.f32} glm53_mm_i4/
python3 tests/test_glm53_vulkan.py --binary ./glm53 --fixture glm53_mm_i4
```

## Naechste Schritte
1. Echtes Modell (Justvugg/GLM-5.3-Flash-colibri-int4-g64, 194.7 GB) — Speicherplatz fehlt noch (51: 173G frei)
2. Warm-Tier-Benchmark: COLI_VK_RESERVE_GB, Tier-Fill aus usage-History
3. Upstream-PR einreichen (Patch ist maintainable, 4 Dateien)
4. Attention-Absorb-Pfad fuer glm53.c (coli_vk_attention_absorb existiert, glm53.c nutzt ihn noch nicht)
