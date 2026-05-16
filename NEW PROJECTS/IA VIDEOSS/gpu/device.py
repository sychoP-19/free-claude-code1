"""GPU device detection and management."""

import os


def get_device(config: dict) -> str:
    device = config.get("gpu", {}).get("device", "auto")
    if device != "auto":
        return device

    # Auto-detect
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon
    except ImportError:
        pass

    # Check ROCm
    if os.path.exists("/opt/rocm/bin/rocm-smi"):
        return "rocm"

    return "cpu"


def set_memory_limit(limit_gb: float | None):
    if limit_gb is None:
        return
    try:
        import torch
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_mem
            limit_bytes = int(limit_gb * 1024**3)
            if limit_bytes < total:
                os.environ["PYTORCH_CUDA_ALLOC_CONF"] = f"max_split_size_mb:{limit_bytes // (1024**2)}"
    except ImportError:
        pass
