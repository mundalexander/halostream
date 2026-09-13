# HALOSTREAM Architecture
**Hybrid VRAM/NVMe MoE Inference für Strix Halo gfx1151**

GLM-5.3-Flash (321B MoE, 45 Layer, 288 Experts/Layer) auf der Ryzen AI Max+ 395 APU.

---

## Hardware-Beleg

```
Ryzen AI Max+ 395 (Strix Halo APU)
├── gfx1151 GPU (Radeon 8060S)
│   ├── ROCm 7.2.0        ✅
│   ├── OpenCL 2.1          ✅
│   ├── Vulkan 1.2+ (AMD RADV)  ✅
│   └── GPU-adressierbar: 128 GB Unified Memory (GTT-Pool: 137 GB)
│
└── NVMe: ~3.5 GB/s sequentiell

Halogen (Qwen3.8-Flash-Next) läuft darauf bereits mit ~29 tok/s.
```

---

## Die 3 Referenz-Systeme

### 1. Colibri (`github.com/JustVugg/colibri`) — Engine
- **C-Engine**, 8 MoE-Familien inkl. GLM-5.3
- **Backend-Vulkan**: `backend_vulkan.c/h` — Attention + MoE-Compute auf GPU
- **Backend-CUDA**: `backend_cuda.h` — Resident pipeline, `COLI_CUDA_PIPE=2`
- **Expert-Tiering**: `expert_store.h` — LRU über VRAM/RAM/NVMe
- **1-Layer-Ahead Prefetch**: Routing-History → Expert-Prefetch
- **Persistent KV**: `kv_persist.h` — Multi-Turn Warmth
- **Build mit Vulkan**:
  ```bash
  COLI_VULKAN=1 make glm53   # aktiviert backend_vulkan
  COLI_VK_VRAM=96 make glm53  # 96 GB GTT für Expert-Cache
  ```

### 2. Slotstream (`github.com/carloslfu/slotstream`) — Slot-Cache
- **Qwen3.8-Flash-Next auf Mac**, SSD-Streaming
- **Slot-Cache**: Fester Pool, alle 48 Layer teilen sich die Slots
- **Trust the OS Page Cache**: OS cached Expert-Dateien natürlich (~71% Hit Rate)
- **1-Layer-Ahead Prefetch**: Routing-basierte Vorhersage
- **Speculative Decoding**: MTP-Draft-Head, 86% Acceptance
- **Auto-Memory-Target**: 33 GB default, 70% RAM, 2 GB unter Metal-Limit

### 3. Flash-MoE (`github.com/danveloper/flash-moe`) — Pipeline
- **Qwen3.5-397B auf MacBook Pro M3 Max**, 48 GB RAM
- **Per-Token Pipeline**:
  ```
  CMD3(prev) → [GPU] Attention + delta-net      [1.22ms]
             → [CPU] Flush results               [0.01ms]
             → [GPU] o_proj + Norm + Routing   [0.55ms]
             → [CPU] Softmax + TopK            [0.003ms]
             → [SSD] pread K=4 Experts          [2.41ms]
             → [GPU] Expert Forward (DEFERRED)
  ```
- **Deferred GPU Expert Compute**: Expert-Forward läuft parallel zum Prefill
- **Trust the OS**: Kein Custom-Cache — OS Page Cache ist schneller als jede LRU-Implementierung
- **FMA Dequant Kernel**: `fma(nibble, scale*x, bias*x)` — 12% schneller als Naive

---

## HALOSTREAM Design

### GLM-5.3 MoE Memory-Tiering

```
Expert-Größe: 16384 × 4096 × 0.5 bytes (int4) = ~33 MB
288 Experts/Layer × 45 Layer = 288 × 45 = 12.960 Experts total
8 Aktive Experts pro Token

Memory-Tier 1 (GTT, 0–96 GB):
  • Embedding + LM Head         ~3 GB
  • Attention QKV (batch)       ~2 GB
  • KV Pool (persistent,warm)  ~16 GB
  • Hot Experts (Top-8)         ~264 MB
  • Expert-Cache LRU (GTT)     bis 96 GB

Memory-Tier 2 (NVMe, Streaming):
  • Kalte Experts (Streaming-on-Demand)
  • 1-Layer-Ahead Prefetch
  • Read-Ahead via Routing-History
```

### HALOSTREAM Stack

```
┌─────────────────────────────────────────────┐
│  OpenAI-API (Port 18790)                     │
│  coli serve --vulkan --vram 96 --ram 64     │
├─────────────────────────────────────────────┤
│  Request Scheduler                           │
│  • Batch Multi-Head Attention (GPU)         │
│  • KV Pool Manager (persistent, warm)       │
│  • Expert Router (Top-8)                   │
├─────────────────────────────────────────────┤
│  GPU (gfx1151)                              │
│  • Vulkan: Attention + MoE (GEMM auf GTT)    │
│  • FMA Dequant Kernel (flash-moe)           │
│  • Deferred Expert Compute (flash-moe)      │
│  • RoPE + Norm + Residual                   │
├─────────────────────────────────────────────┤
│  Tier 1: GTT (0–96 GB)                     │
│  • Expert-Cache LRU (colibri)               │
│  • 1-Layer-Ahead Prefetch (slotstream)      │
│  • Trust OS Page Cache (flash-moe)           │
├─────────────────────────────────────────────┤
│  Tier 2: NVMe/SSD                          │
│  • O_DIRECT Expert-Reads (colibri)          │
│  • Kalte Expert-Experts                     │
└─────────────────────────────────────────────┘
```

---

## Implementierungs-Phasen

### Phase 1: GLM-Engine mit Vulkan bauen
```bash
# Prüfe Vulkan SDK
pkg-config --cflags --libs vulkan && echo "Vulkan SDK: OK"

# Colibri mit Vulkan für gfx1151
cd /home/sascha/colibri/c
COLI_VULKAN=1 \
COLI_VK_DEVICE=gfx1151 \
COLI_VK_VRAM=96 \
make glm53_vulkan

# Test
./glm53 serve \
  --model /home/sascha/models/colibri_store/glm53_i4 \
  --vulkan \
  --vram 96 \
  --ram 64 \
  --port 18790
```

### Phase 2: Expert-Streaming integrieren
- `expert_store_registry.c` → GTT-Pool (96 GB)
- Routing-History → 1-Layer-Ahead Prefetch
- NVMe O_DIRECT → kalte Tier

### Phase 3: HALOSTREAM GUI Preset
- GUI: GLM-5.3 Preset auf 18790
- tok/s Benchmark live anzeigen
- Server-Start/Stop aus dem GUI

---

## Offene Fragen (zu klären vor Phase 1)

- [ ] **Vulkan SDK**: `pkg-config --cflags vulkan`
- [ ] **ROCm HIP**: Kann gfx1151 als HIP-Device?
- [ ] **Colibri Vulkan Backend**: Kompiliert auf dieser Maschine?
- [ ] **NVMe O_DIRECT**: Verfügbar + benchmark-bar?
