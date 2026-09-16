# Contributing to HaloStream

Danke fuer dein Interesse! Dieses Repo sammelt Deployment-, Patch- und
Messarbeiten fuer den Betrieb von GLM-5.3-Klasse MoE-Modellen auf
AMD Strix Halo (gfx1151) via der Colibri-Engine.

## Repo-Struktur

| Verzeichnis | Inhalt |
|---|---|
| `docs/` | Messungen, Audits, Architekturentwuerfe — jede Messung mit **Datum, Kommando, Ergebnis** |
| `patches/` | Maintainable Patches gegen Upstream (Colibri u.a.) |
| `spike/` | Experimentelle Artefakte, Logs, Audits |
| `scripts/` | Operative Automatisierung (idempotent, klares Logging) |
| `deploy/` | Docker-/Compose-Definitionen |
| `tools/` | Lokales Tooling (GUI, Monitore, Serve-Skripte) |

## Konventionen

1. **Messungen** gehoeren nach `docs/` mit Datum, exaktem Kommando und
   Ergebnis. Keine Zahl ohne Reproduktionsweg.
2. **Patches** maintainbar halten: minimale Hunks, Kommentare im Code
   warum (nicht nur was), kompatibel mit moeglichst aktuellem Upstream-Stand.
   Im Patch-Header: Basis-Commit und Verifikationsstatus angeben.
3. **Decision Gates respektieren**: Keine grossen Downloads (>50 GB) oder
   Modell-Operationen ohne explizite Freigabe (siehe PLAN.md).
4. **GPU/Vulkan nicht als fertig annehmen**, solange nicht explizit
   verifiziert dokumentiert.
5. **Keine privaten Daten**: keine IPs, Passwoerter, Klarnamen oder
   privaten Kontaktdaten in Commits, Logs oder Doku.

## Patch einreichen

1. Fork des Repos, eigener Branch pro Thema.
2. Patch unter `patches/<name>.patch` ablegen, zusaetzlich Doku/
   Verifikationsnotiz in `docs/`.
3. PR mit: Was aendert sich, warum, welche Verifikation wurde gefahren.

## Verifikations-Philosophie

Das Gold-Kriterium fuer Inferenz-Patches: **token-identische Ausgabe
GPU == CPU** gegen den offiziellen Upstream-Test
(`test_glm53_vulkan.py`, int4-Streaming-Fixture). Ein Patch, der
schneller ist, aber andere Token liefert, ist kein Beitrag sondern ein
Bug. Qualitaet vor Rate.

## Hardware-Voraussetzungen

- AMD Strix Halo (gfx1151), z.B. GMKtec EVO-X3
- 96+ GB unified RAM empfohlen (GLM-5.3-Flash int4-g64 Container ~195 GB
  on-disk, streamingfaehig ab ~24 GB Resident-Budget)
- NVMe mit >2 GB/s Read (mehr ist besser; Streaming-Pfad skaliert mit der
  Plattenleistung)
- Mesa RADV (Vulkan) fuer GPU-Pfad-Bauten (`-DCOLI_VULKAN`)

## Bekannte offene Baustellen

- UMA-OOM im glm53 VK-Expert-Tier (Budget-Gate noetig — Draft vorhanden:
  `patches/glm53_vk_arena_budget_draft.patch`)
- Vulkan-Runtime-Device-Erkennung in der Standard-Engine

Fragen? Issue aufmachen.
