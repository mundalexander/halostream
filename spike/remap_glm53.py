#!/usr/bin/env python3
"""
Zero-Copy GLM-5.3-Flash Tensor Remap Script
============================================
Patches model.safetensors.index.json to strip the 'model.language_model.' prefix
so Colibri's C-loader (expecting 'model.layers.N.*') can find tensors.

PHYSICAL WEIGHT BYTES: NEVER TOUCHED. Read-only operation.
Only the JSON index file is patched (in-place, no duplication).
"""

import json
import shutil
import sys
import os

MODEL_DIR = "/home/sascha/models/colibri_store/glm53_flash"
INDEX_FILE = os.path.join(MODEL_DIR, "model.safetensors.index.json")
BACKUP_FILE = os.path.join(MODEL_DIR, "model.safetensors.index.json.pre_remap")

REMAPPED_PREFIXES = [
    ("model.language_model.", "model."),   # GLM-5.3-Flash -> Colibri expectation
    ("model.visual.", "model.visual."),      # Vision encoder (keep as-is)
]

def log(msg):
    print(f"[remap] {msg}", flush=True)

def remap_key(key: str) -> str:
    """Apply all remapping rules to a tensor key."""
    for old_prefix, new_prefix in REMAPPED_PREFIXES:
        if key.startswith(old_prefix):
            return new_prefix + key[len(old_prefix):]
    return key

def run() -> bool:
    log(f"Starting zero-copy GLM-5.3-Flash tensor remap")
    log(f"Model dir: {MODEL_DIR}")
    log(f"Index file: {INDEX_FILE}")

    if not os.path.exists(INDEX_FILE):
        log(f"ERROR: Index file not found: {INDEX_FILE}")
        log(f"Have you downloaded the model yet?")
        return False

    # Backup original
    shutil.copy2(INDEX_FILE, BACKUP_FILE)
    log(f"Backed up original to: {BACKUP_FILE}")

    with open(INDEX_FILE, 'r') as f:
        index = json.load(f)

    wm = index.get("weight_map", {})
    original_keys = set(wm.keys())

    # Apply remapping
    new_wm = {}
    changes = {}

    for key, shard_path in wm.items():
        new_key = remap_key(key)
        new_wm[new_key] = shard_path
        if new_key != key:
            changes[key] = new_key

    # Update index
    index["weight_map"] = new_wm

    # Update metadata to reflect remapping
    if "metadata" not in index:
        index["metadata"] = {}
    index["metadata"]["remapped_from"] = "glm53_flash_v1"
    index["metadata"]["remap_script"] = __file__

    # Write patched index
    with open(INDEX_FILE, 'w') as f:
        json.dump(index, f, indent=2)

    log(f"Remapped {len(changes)} tensor keys")
    log(f"Total tensors in index: {len(new_wm)}")

    # Summary of key changes
    if changes:
        log(f"Sample changes (first 10):")
        for old, new in sorted(changes.items())[:10]:
            log(f"  {old}")
            log(f"    -> {new}")

    # Verify critical tensors are present after remap
    critical = [
        "model.layers.0.input_layernorm.weight",
        "model.layers.44.post_attention_layernorm.weight",
        "model.norm.weight",          # may not exist in Glm5Next
        "model.lm_head.weight",
        "model.embed_tokens.weight",
    ]
    log(f"\nCritical tensor check after remap:")
    for tensor in critical:
        status = "FOUND" if tensor in new_wm else "MISSING"
        shard = new_wm.get(tensor, "N/A")
        log(f"  {status}: {tensor}  [{shard}]")

    log(f"\nRemap complete. Physical shard files were NOT modified.")
    log(f"Original index backed up to: {BACKUP_FILE}")
    log(f"Patched index written to: {INDEX_FILE}")
    return True

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
