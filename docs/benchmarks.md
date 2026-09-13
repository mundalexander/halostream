# HaloStream Benchmarks

## GLM-5.3-Flash CPU/SSD Smoke Test

- Datum: 2026-09-13
- Modell: `/home/sascha/models/colibri_store/glm53_i4`
- Modellgröße: 194.7 GB, 62 Shards
- Kommando: `NGEN=8 CTX=512 bash scripts/first_run.sh`
- Ergebnis: `decode 8 token in 5.8s = 1.371 tok/s`
- Expert-I/O: 1,507 Hits, 4,322 Misses, 61,181,263,872 Bytes gelesen
- Status: **PASS** für Laden, Routing und korrekte Textausgabe
- GPU: nicht aktiviert; `coli doctor --deep` meldete keine unterstützte GPU
- Einschränkung: `coli bench` wurde mangels Python-Modul `datasets` übersprungen

Der Lauf bestätigt den CPU/SSD-Streamingpfad. Die Zielschwelle von 3 tok/s ist
damit noch nicht erreicht; Vulkan und Storage-Tuning bleiben die nächsten
Messpunkte.

## GLM-5.3-Flash Vulkan Smoke Test

- Kommando: `COLI_VULKAN=1 COLI_VK_SHADERS=/home/sascha/colibri/c/shaders/qmatmul.spv /home/sascha/colibri/c/glm53 --model /home/sascha/models/colibri_store/glm53_i4 --prompt 'Antworte mit genau zwei kurzen Sätzen: Was ist NVMe-Streaming?' --greedy 4`
- Ergebnis: `Radeon 8060S Graphics (RADV GFX1151)`, Vulkan aktiv, Exit 0
- Ausgabe: `decode 4 token in 11.1s = 0.360 tok/s`
- Expert-I/O: 1,117 Hits, 3,032 Misses, 42,920,312,832 Bytes gelesen
- Speicher: maximale RSS 51.8 GiB, kein Swap während des Prozesses
- Status: **PASS** für Vulkan-Initialisierung; GPU-Pfad ist auf residente
  Matrizen begrenzt, während Expert-Gewichte weiter über RAM/SSD laufen

## Next-Layer-Prefetch Probe

- Implementiert in `glm53.c` als opt-in `GLM53_PREFETCH=1`
- Strategie: Die gerade gerouteten Expert-IDs werden für den nächsten Layer mit
	`POSIX_FADV_WILLNEED` im OS-Page-Cache angekündigt; sie werden nicht vorab
	in den Modellcache kopiert und die Router-Semantik bleibt unverändert.
- Runtime-Messung: noch offen; ein Test wurde durch einen parallel laufenden
	`coli serve --ram 68`-Prozess verfälscht und lief in den Timeout.
- Produktionsstatus: deaktiviert (`GLM53_PREFETCH=0`), bis ein isolierter
	Cold-/Warm-Vergleich einen Gewinn zeigt.

## GLM-5.3-Flash Vulkan Expert-Tier Probe

- Kommando: `COLI_VULKAN=1 COLI_VK_SHADERS=/home/sascha/colibri/c/shaders/qmatmul.spv GLM53_VK_EXPERTS=1 GLM53_EXPERT_GB=4 /home/sascha/colibri/c/glm53 --model /home/sascha/models/colibri_store/glm53_i4 --prompt 'Antworte mit einem Wort.' --greedy 1`
- GPU-Tier: 6 Expert-Slots pro Layer, ca. 3.6 GB resident
- Ergebnis: `decode 1 token in 2.5s = 0.404 tok/s`, Exit 0, kein Swap
- Vergleich CPU: `decode 1 token in 3.8s = 0.267 tok/s`
- Ergebnis: ca. **1.5x Decode-Speedup** in diesem kleinen, kalten Probe-Lauf
- Einschränkung: Ein Token ist kein stabiler End-to-End-Benchmark; längere
	Warm-/Cold-Läufe und Prefill müssen noch separat gemessen werden.

## Expert-Cache Größenvergleich

- Prompt: `Antworte mit vier kurzen Wörtern.`; jeweils `--greedy 4`
- Vulkan + Expert-Tier, 32 GB: `0.426 tok/s`, 987 Hits, 2,182 Misses
- Vulkan + Expert-Tier, 48 GB: `0.602 tok/s`, 1,023 Hits, 2,146 Misses
- Vulkan + Expert-Tier, 60 GB: `0.739 tok/s`, 1,023 Hits, 2,146 Misses
- CPU/SSD bei 60 GB: `0.468 tok/s`, 1,003 Hits, 2,228 Misses

Der kurze Vergleich zeigt einen maximalen Vulkan-Gewinn von ca. **1.6x** gegen
den CPU-Lauf und ca. **1.7x** zwischen 32 und 60 GB Vulkan-Cache. Die Läufe
waren kalt und kurz; insbesondere die nahezu gleichen Hit-Zahlen bei 48 und
60 GB müssen mit längeren Warm-Läufen überprüft werden.

Nach dem Vergleich wurden die Modellprozesse beendet; es waren wieder etwa
113 GiB RAM verfügbar.

## GPU-Auslastungsprobe

- Messung: 2026-09-13, `GLM53_EXPERT_GB=60`, `GLM53_VK_EXPERTS=1`, 4 Tokens
- Engine: `Radeon 8060S Graphics (RADV GFX1151)`, Vulkan aktiv
- AMD-GRBM2-Compute-Telemetrie: 120 Samples, Maximum 1%, 1 nicht-null Sample
- Interpretation: Die GPU wird verwendet, arbeitet aber nur in sehr kurzen
	Bursts. Der dominante Engpass ist weiterhin CPU-Routing, SSD-Streaming und
	synchrones Readback, nicht fehlende GPU-Initialisierung.

## Vulkan-Expert-Batching Probe

- Änderung: Tokens eines einzelnen Experts werden in einem Vulkan-Expert-Group-
	Dispatch gebündelt.
- Ergebnis: 8 Tokens bei 60 GB Cache, `0.601 tok/s`, Exit 0, kein Swap
- Vorheriger Vergleichslauf: `0.634 tok/s`
- Bewertung: Der erste Token-Batching-Versuch war noch kein Gewinn; der
	anschließende gemeinsame Submit für die gerouteten Experten ist im nächsten
	Abschnitt separat gemessen.

## Vulkan-Expert-Group-Batching

- Aktivierung: zusätzlich zu `GLM53_VK_EXPERTS=1` auch `GLM53_VK_BATCH=1`
- 4 Tokens: `0.981 tok/s` gegenüber `0.601 tok/s` ohne Gruppierung
- 8 Tokens: `0.755 tok/s` gegenüber `0.601 tok/s` im Vergleichslauf
- Speicher: maximale RSS ca. `43.1 GiB`, kein Swap, Exit 0
- Ergebnis: Der gemeinsame Submit für die gerouteten Experten verbessert den
	kurzen Decode-Test um etwa 26%. Der Schalter bleibt opt-in, bis längere
	Warm-Läufe und Output-Korrektheit gegen eine Referenz geprüft sind.

Frühere Läufe wurden vom Kernel beendet: `glm53` erreichte ca. 49--52 GiB RSS,
danach wurde der zugehörige VS-Code-App-Scope ebenfalls beendet. Das ist kein
Shared-Storage-Fehler. Inference-Tests müssen außerhalb von VS Code und ohne
parallel geladene LM-Studio-Modelle laufen.