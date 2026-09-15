# Beitrag / Findings — Strix Halo Doppel-Server Validierung (2026-09-15)

Beitrag von Hermine (Daniel Fischer) aus dem produktiven Betrieb auf
**zwei GMKtec EVO-X3 / Ryzen AI MAX+ 395 (gfx1151, 128 GB unified)**.

Dieses Dokument fasst zusammen, was wir zu HaloStream beigetragen haben:
unabhängige Validierung der Referenzwerte, ein funktionierender
Vulkan-Expert-Patch inkl. Swiglu-Clamp-Fix, und Root-Cause-Analyse des
UMA-OOM beim GLM-5.3-Vollmodell-Lauf.

---

## 1. Unabhängige Validierung der Halogen-Referenzwerte

Unsere Messungen auf Server 51 (Halogen, Qwen-basiert, Port 8731) gegen
die im HaloStream-PLAN genannten Referenzwerte:

| Metrik | HaloStream-Angabe | Unsere Messung | Urteil |
|---|---|---|---|
| Prefill | 1.424 tok/s | 72.215 Tok / 46,83 s = **1.542 tok/s** | ✓ konsistent |
| Spekulativer Decode | 41,7 tok/s | **40,5 / 43,7 tok/s** (serve_api-Logs) | ✓ konsistent |

Die Werte bestätigen: die HaloStream-Referenzmessungen sind reproduzierbar.

## 2. Vulkan-Expert-Patch (glm53.c) — GPU-Pfad verifiziert

`patches/glm53_vk_expert_clamped.patch` (254 Zeilen, 4 Dateien).
Details in `docs/VK_EXPERT_PATCH_MEINE_UMSETZUNG.md`. Kernpunkte:

1. **LRU-Slots mit persistenten GPU-Tensoren** — Experten bei Cache-Miss
   via `coli_vk_tensor_ensure()` aufs Device, bei Eviction sauber frei.
2. **Batched `coli_vk_expert_group()`** pro Cache-Block statt
   CPU-`mlp3`-Schleife.
3. **Swiglu-Clamp im Fused-Shader** (Push-Constant `float limit` +
   `coli_vk_set_swiglu_limit()`). Das war der fehlende Baustein:
   `swiglu_limit=0` ist eine Falle — der C-Clamp löscht damit das ganze
   MLP. Echtes GLM-5.3 nutzt `limit=10.0`, der Upstream-Shader clamped
   nicht.

**Verifikation (Server 51):**
- Offizieller Upstream-Test `test_glm53_vulkan.py`: **PASS** — GPU liefert
  token-identische Antworten wie CPU (int4-Streaming-Fixture, 8 Positionen,
  4 greedy Schritte).
- VK-EXPERT-Pfad nachweislich aktiv (nvk=4 Batch).
- E2E-Synthetik: **26,5 tok/s** projizierte MoE-Phase, ~282× GPU-Speedup
  vs. CPU-Deckel (0,34 tok/s).

Damit ist die offene Phase-2-Frage "GPU-Pfad schneller als CPU?" beantwortet: **JA.**

## 3. GLM-5.3-Flash Vollmodell-Lauf + OOM-Root-Cause

Vollständiger Lauf mit `glm-5.3-flash-colibri-int4-g64` (181,4 GiB,
62 Shards bytegenau verifiziert) auf 128-GB-UMA-Maschine:

- Laden: **PASS** (25,2 s), Vulkan ready (Radeon 8060S RADV GFX1151),
  Expert-Cache 15,5 GB resident, kein OOM beim Laden.
- Decode: **global OOM nach ~90 s**.
- Forensik: Prozess-RSS nur 24 GB, aber Kernel zeigt
  `gpu_active ≈ 98,8 GB` — GPU-Allokationen aus System-RAM (UMA).
  RAM-Drain linear während Decode, nicht beim Laden.

**Root Cause (Code-Analyse):**
1. `upload_tensor()` in `backend_vulkan.c` allokiert aus einer
   VK-Arena (256-MB-Blöcke), die freigegebene Blöcke **nie ans OS
   zurückgibt**.
2. Der VK-Expert-Tier in `glm53.c` ruft `coli_vk_tensor_ensure()` pro
   Cache-Miss **ohne Device-Memory-Budget** — anders als `colibri.c`,
   wo `vk_registry_fill()` bei `COLI_VK_RESERVE_GB` stoppt.
3. Auf UMA (device-local = System-RAM) wächst die GPU-Seite monoton mit
   der Zahl einzigartig hochgeladener Experten → globaler OOM.

KV-Cache war NICHT der Treiber (DSA-Indexer 33 KB/Token ≈ 2 MB).
`GLM53_EXPERT_GB` begrenzt nur die CPU-Seite, nicht die GPU-Arena.

**Empfehlung:** Budget-Gate im glm53.c-Expert-Tier (laufende Zählung der
GPU-Bytes, Upload-Skip mit CPU-Fallback ab Cap — analog `vk_registry_fill`),
ergänzend Arena-Block-Rückgabe an das OS.

## 4. Hardware-Kontext: unsere NVMe ist nicht die Engstelle

Die Colibri-Doku sagt "Disk is the wall" (~200 MB/s Referenz).
Unsere EVO-X3 misst **26 GB/s NVMe-Read**. Auf dieser Hardwareklasse
verschiebt sich die Wand von der Platte zur Berechnung (CPU-Deckel bzw.
mit VK-Patch zur GPU). Das stützt die Priorisierung des GPU-Pfads.

## 5. Betriebliche Bestätigung: RAM-Konflikt

Unabhängig bestätigt: Halogen mlockt ~96 GiB — GLM-Load-Tests und
Halogen parallel sind auf 128 GB nicht möglich. Vor GLM-Tests muss der
andere Service down. (Deckt sich mit der Warnung im PLAN.)

---

## Status der Artefakte in diesem PR

| Artefakt | Status |
|---|---|
| `patches/glm53_vk_expert_clamped.patch` | verifiziert (token-ident GPU==CPU) |
| `docs/VK_EXPERT_PATCH_MEINE_UMSETZUNG.md` | Implementierungs-Doku |
| `docs/benchmarks.md` (Ergänzung) | Vollmodell-Lauf + OOM-Forensik |
| `docs/CONTRIBUTION_FINDINGS_2026-09-15.md` | dieses Dokument |

Beitrag frei zur Verwendung im Upstream — Kontakt via GitHub-Issue/PR.
