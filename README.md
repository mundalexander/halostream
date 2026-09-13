# HaloStream

**Lokale Inference für 100B+ MoE-Modelle auf AMD Strix Halo Hardware** — NVMe-Streaming, GPU-Beschleunigung über Vulkan, Open-Source.

---

## Was ist HaloStream?

HaloStream ist ein Projekt, um extrem große Mixture-of-Expert-Modelle (300+ GB) direkt auf Consumer-Hardware mit AMD Strix Halo Prozessoren (gfx1151) betreibbar zu machen. Der Fokus liegt auf:

- **NVMe-Streaming**: Modelle werden direkt von der NVMe SSD gestreamt — kein vollständiges Laden in den RAM nötig
- **GPU-Beschleunigung**: Vulkan-Pfad für Expert-Auswahl auf der iGPU (gfx1151)
- **CPU-Fallback**: AVX-512/VNNI Support auf Zen5 für robuste CPU-Inference
- **Serving**: HTTP-Server mit Streaming-Response, kompatibel zu bestehenden Clients

## Zielhardware

| Komponente | Spec |
|---|---|
| CPU | AMD Ryzen AI MAX+ 395, 16C/32T, Zen5, AVX-512 (inkl. BF16/VNNI) |
| GPU | Radeon 8060S iGPU, **gfx1151**, 40 CUs |
| RAM | 128 GB unified (CPU+GPU geteilt!) |
| Storage | NVMe, ~10 GB/s gemessen |

## Warum dieses Projekt?

Die nächste Generation von Sprachmodellen wird noch größer. 100B+ Parameter sind keine Ausnahme mehr. Die Hardware-Community braucht Lösungen, die diese Modelle auf verfügbarer Consumer-Hardware betreibbar machen — ohne Cloud-Abhängigkeit. Strix Halo mit seiner unified Memory-Architektur ist dafür ein idealer Kandidat.

## Architektur

HaloStream nutzt eine **Hybrid VRAM/NVMe MoE**-Architektur:

1. **NVMe-Streaming-Pfad**: Modell-Shards werden on-demand von der SSD geladen und direkt in den unified Memory gemappt (Zero-Copy)
2. **GPU-Beschleunigung**: Die Expert-Auswahl (routing) läuft auf der Radeon iGPU über Vulkan — signifikant schneller als CPU-only
3. **Serving-Schicht**: HTTP-Server mit Streaming-Response, kompatibel zu bestehenden LLM-Clients

## Status

- [x] NVMe-Streaming-Pfad implementiert und getestet
- [x] Vulkan-Build für gfx1151 erfolgreich
- [x] CPU-Inference mit AVX-512/VNNI optimiert
- [ ] Vulkan-Laufzeitpfad auf gfx1151 verifizieren
- [ ] Serving-Benchmarks dokumentieren
- [ ] Dokumentation und Einsteiger-Guide vervollständigen

## Mitmachen

Du kannst auf verschiedene Weise beitragen:

- **Benchmarking**: Teste mit anderen Modellen oder Hardware-Konfigurationen
- **Dokumentation**: Hilfreiche Guides, Tutorials, Fehlerbehebung
- **Code**: Vulkan-Optimierung, neue Modell-Unterstützung, Serving-Features
- **Ideen**: Was würdest du gerne auf Strix Halo laufen lassen?

Issues und PRs sind willkommen!

## Struktur

- `PLAN.md` — Phasen, Entscheidungen, Runbook
- `docs/` — Audits & Benchmarks
- `patches/` — Patches gegen Upstream (maintainable, ggf. PR einreichen)
- `scripts/` — Betriebsskripte
- `spike/` — Spike-Artefakte und Experimente
- `tools/` — Hilfsprogramme

## Lizenz

[Bitte Lizenz hinzufügen]
