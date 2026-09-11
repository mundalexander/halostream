# Spike A – Vulkan-Build (2026-09-11)

## Ergebnis: ✅ BUILD SUCCESS (EXIT=0, 0 errors, 2 warnings)

Artefakte (in `/home/sascha/colibri/c`):
- `colibri` – 724 KB, linked gegen `libvulkan.so.1`, 29 `coli_vk*`-Symbole
- `shaders/qmatmul.spv` (upstream-gecheckt), `qmatmul_gate_up.spv`,
  `attention_absorb.spv`, `rmsnorm.spv` (heute mit glslc kompiliert)
- Build-Log: `spike/vulkan_build.log`

## Toolchain ohne sudo assembled

Es fehlen `libvulkan-dev`, `glslc`, `pkg-config` (apt braucht sudo, keins verfügbar).
Workaround – alles unter `spike/`, kein System-Eingriff:

1. **Vulkan-Headers:** `git clone --depth 1 KhronosGroup/Vulkan-Headers`
   → `spike/third_party/Vulkan-Headers/include` (via `C_INCLUDE_PATH`)
2. **glslc + libshaderc:** `apt-get download glslc libshaderc1` (ohne root!),
   `dpkg-deb -x` → `spike/pkg/`; Wrapper `spike/bin/glslc` setzt LD_LIBRARY_PATH
3. **Link-Lib:** Symlink `spike/lib/libvulkan.so` → System-`libvulkan.so.1`
   (Runtime 1.3.275 ist ohnehin installiert) → via `LIBRARY_PATH`

Build-Kommando (reproduzierbar):

```bash
cd /home/sascha/colibri/c
C_INCLUDE_PATH=/home/sascha/colibri-rocm/spike/third_party/Vulkan-Headers/include \
LIBRARY_PATH=/home/sascha/colibri-rocm/spike/lib \
make -j4 colibri VK=1 \
  GLSLC=/home/sascha/colibri-rocm/spike/bin/glslc
```

## Warnings

2x `-Warray-bounds`-Hinweis in `colibri.c` (Zeile ~5949, `vcls[64]` –
upstream-bekannt, harmlos). Keine fehlenden Header.

## Nebenbefund

Upstream-Repo enthält bereits eine vorkompilierte `qmatmul.spv` → Shader sind
ohne glslc lauffähig; für die drei anderen braucht es den Wrapper oben.

## Nächster Schritt (wartet auf LM-Studio-Pause)

Run-Test gemäß docs/vulkan.md, RAM-schonend mit tiny-Modell:

```bash
COLI_VULKAN=1 COLI_VK_DENSE=1 COLI_VK_ATTN=1 COLI_NO_OMP_TUNE=1 \
./coli run "Hello" --topp 0.7   # erst wenn LM Studio pausiert
```

Erfolgskriterium Spike A: Vulkan-Pfad auf RADV/gfx1151 initialisiert durch und
GEMM-Bench ≥ 1.5× CPU-Baseline (Phase-2-Schwelle).
