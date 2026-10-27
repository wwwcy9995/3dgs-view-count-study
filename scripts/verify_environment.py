"""Exercise CUDA and the installed gsplat forward/backward implementation."""

import importlib.metadata as metadata
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import torch
from gsplat.rendering import rasterization

ROOT = Path(__file__).resolve().parents[1]


def main():
    assert torch.cuda.is_available(), "PyTorch cannot use CUDA"
    torch.manual_seed(42)
    device = "cuda"
    means = (torch.rand((32,3), device=device) - 0.5)
    means[:, 2] += 3.0
    means.requires_grad_(True)
    quats = torch.zeros((32,4), device=device)
    quats[:,0] = 1.0
    scales = torch.full((32,3), 0.1, device=device)
    opacity = torch.full((32,), 0.5, device=device)
    colors = torch.rand((32,3), device=device)
    matrices = torch.eye(4, device=device)[None]
    intrinsics = torch.tensor([[50.,0.,32.],[0.,50.,32.],[0.,0.,1.]], device=device)[None]
    start = time.perf_counter()
    rendered, alpha, _ = rasterization(means=means, quats=quats, scales=scales, opacities=opacity, colors=colors, viewmats=matrices, Ks=intrinsics, width=64, height=64)
    rendered.mean().backward()
    torch.cuda.synchronize()
    assert rendered.shape == (1,64,64,3)
    assert torch.isfinite(rendered).all() and torch.isfinite(means.grad).all()
    assert means.grad.abs().sum() > 0
    versions = {name: metadata.version(name) for name in ["torch","torchvision","gsplat","nerfstudio","numpy","torchmetrics","tyro","viser"]}
    result = {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": versions,
        "torch_cuda_runtime": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
        "cuda_compute_capability": list(torch.cuda.get_device_capability(0)),
        "gsplat_forward_backward_passed": True,
        "render_shape": list(rendered.shape),
        "test_elapsed_seconds": time.perf_counter() - start,
        "scope": "component verification only; not a scene quality experiment",
    }
    records = ROOT / "records/setup"
    records.mkdir(parents=True, exist_ok=True)
    (records / "environment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    # Splatfacto initializes LPIPS, which uses torchvision's pretrained AlexNet.
    # Download this evaluation dependency now rather than during scene training.
    from download_eval_weights import prepare_alexnet
    prepare_alexnet()
    from torchmetrics.image.lpip import LearnedPerceptualImagePatchSimilarity
    lpips = LearnedPerceptualImagePatchSimilarity(normalize=True)
    with torch.no_grad():
        score = lpips(torch.zeros(1,3,64,64), torch.zeros(1,3,64,64))
    assert torch.isfinite(score)
    weight_files = []
    for file in (ROOT / ".cache/torch/hub/checkpoints").glob("*.pth"):
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(2**20), b""):
                digest.update(chunk)
        weight_files.append({"file": file.name, "bytes": file.stat().st_size, "sha256": digest.hexdigest()})
    from torchvision.models import AlexNet_Weights
    (records / "evaluation-weights.json").write_text(json.dumps({
        "purpose": "LPIPS evaluation dependency; not a pretrained 3D scene",
        "torch_home": str(ROOT / ".cache/torch"),
        "same_image_score": float(score),
        "alexnet_weights_url": AlexNet_Weights.IMAGENET1K_V1.url,
        "files": weight_files,
    }, indent=2), encoding="utf-8")
    print("CUDA_GSPLAT_AND_LPIPS_READY", flush=True)


if __name__ == "__main__":
    main()
