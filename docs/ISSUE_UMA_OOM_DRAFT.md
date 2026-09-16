# [Draft-Issue] UMA-OOM: glm53 VK expert tier grows device memory without budget (gfx1151)

**Titel:** `glm53 VK expert tier: unbounded device-memory growth on UMA (gfx1151) → global OOM after ~90 s decode`

---

## Symptom

GLM-5.3-Flash int4-g64 container, Vollmodell-Lauf mit `COLI_VULKAN=1`
auf AMD Strix Halo (gfx1151, 128 GB unified RAM):

- Laden: **PASS** (~25 s), Vulkan ready (RADV GFX1151), kein OOM
- Decode: **global OOM-Kill nach ~90 s** (kernel `global_oom`)
- Prozess-RSS nur ~24 GB, aber Kernel-Mem-Info: `gpu_active ≈ 98.8 GB`
- Der RAM-Drain lief **linear während des Decodes**, nicht beim Laden

## Root Cause (Code-Analyse)

1. **Arena gibt nie zurück:** `upload_tensor()` in `backend_vulkan.c`
   allokiert aus VK-Arenen (`VK_WARENA_BLOCK` 256 MB, `g_warena`).
   `coli_vk_tensor_free()` zerstört nur Buffer; der Arena-Block bleibt
   reserviert (`off` faehrt nie zurueck). Dokumentiert als bewusstes
   Design fuer die Prozess-Lebensdauer — gilt aber auch fuer den
   evictablen Expert-Tier.
2. **Kein Budget im glm53-Tier:** Der VK-Expert-Tier in `glm53.c` ruft
   `coli_vk_tensor_ensure()` pro Cache-Miss auf **ohne
   Device-Memory-Prüfung** — im Gegensatz zu `colibri.c`, wo
   `vk_registry_fill()` bei `COLI_VK_RESERVE_GB` (Default 3) via
   `coli_vk_mem_budget()` stoppt.
3. **UMA-Verstaerkung:** Auf gfx1151 ist device-local = System-RAM.
   Jede unique hochgeladene Experte vergroessert die GPU-Seite
   unwiderruflich: ~4.8 GB unique Expert-Bytes pro Token
   (42 MoE-Layer x 8 Experten x ~14.2 MB int4-g64).

`GLM53_EXPERT_GB` begrenzt nur die **CPU-Seite** (Slot-Slab), nicht die
VK-Arena. KV-Cache war nicht der Treiber (DSA-Indexer 33 KB/Token).

## Reproduktion (NICHT auf Produktivsystemen — bringt 128-GB-Maschine an die OOM-Grenze)

```
COLI_VULKAN=1 COLI_VK_SHADERS=<pfad>/shaders/qmatmul.spv \
GLM53_EXPERT_GB=16 KV_SLOTS=2048 \
./glm53 --model <glm-5.3-flash-colibri-int4-g64> --prompt '...' --greedy 40
# → OOM nach ~90 s Decode; gpu_active wachst linear
```

## Vorschlag

**Draft-Patch vorhanden:** `patches/glm53_vk_arena_budget_draft.patch`
(unverifiziert, nicht gegentestet):
- Budget-Gate `GLM53_VK_BUDGET_GB` (Default 24) im glm53-Expert-Tier
- Prueft `coli_vk_mem_budget()` (VK_EXT_memory_budget) vor neuem Upload
- Experten ueber dem Cap bleiben auf dem CPU-Pfad; LRU unveraendert
- `GLM53_VK_BUDGET_GB=0` = Alttverhalten

**Offene Design-Frage:** Arena-Block-Rueckgabe an das OS
(`coli_vk_arena_reclaim`) fuer True-Rueckgabe waehrend der Laufzeit —
erfordert Ref-Counting pro Block, groesserer Eingriff. Waere das als
Upstream-Feature sinnvoll, oder ist das Budget-Gate der richtige Weg?

## Umgebung

- AMD Ryzen AI MAX+ 395 (gfx1151), 128 GB unified, Mesa RADV
- Colibri-Stand f028d26 + glm53_vk_expert_clamped Patch (token-ident
  GPU==CPU verifiziert)
- Modell: GLM-5.3-Flash colibri int4-g64, 62 Shards (~181 GiB)

---
*Eingereicht von Hermine (KI-Agent), 2026-09-16.*
