"""Evaluate held-out views using the pinned Nerfstudio model's metric API.

Uses eval_setup(test_mode='test'), get_outputs_for_camera, and
get_image_metrics_and_images, the same APIs used by ns-eval. Adds per-view CSV
records and image identity mapping. PNGs are for visualization; metrics are
computed from the original float tensors before PNG quantization.
"""

import argparse
import csv
import json
import math
from pathlib import Path
import time

import numpy as np
from PIL import Image
import torch

from nerfstudio.utils.eval_utils import eval_setup

ROOT = Path(__file__).resolve().parents[1]


@torch.no_grad()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--scope", choices=["formal_test", "pilot_validation"], required=True)
    parser.add_argument("--compare-aggregate", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.render_dir:
        args.render_dir.mkdir(parents=True, exist_ok=True)
    config, pipeline, checkpoint, step = eval_setup(args.load_config, test_mode="test")
    loader = pipeline.datamanager.fixed_indices_eval_dataloader
    assert len(loader) == args.expected_count, (len(loader), args.expected_count)
    dataset = pipeline.datamanager.eval_dataset
    filenames = dataset.image_filenames
    rows = []
    start = time.perf_counter()
    for index, (camera, batch) in enumerate(loader):
        if "image_idx" in batch:
            assert int(batch["image_idx"]) == index
        outputs = pipeline.model.get_outputs_for_camera(camera)
        metrics, images = pipeline.model.get_image_metrics_and_images(outputs, batch)
        source = Path(filenames[index]).resolve()
        try:
            source_name = str(source.relative_to(ROOT / "data/raw/nerf_synthetic/lego"))
        except ValueError:
            source_name = str(source)
        row = {"index": index, "source_image": source_name}
        for key in ["psnr", "ssim", "lpips"]:
            value = float(metrics[key])
            if not math.isfinite(value):
                raise ValueError(f"Nonfinite {key} for image {index}")
            row[key] = value
        rows.append(row)
        if args.render_dir:
            image = images["img"].detach().clamp(0, 1).cpu().numpy()
            assert image.shape == (400, 800, 3), image.shape
            Image.fromarray((image * 255).astype(np.uint8)).save(args.render_dir / f"eval_img_{index:04d}.png")
        if (index + 1) % 25 == 0 or index + 1 == args.expected_count:
            print(f"EVALUATED {index + 1}/{args.expected_count}", flush=True)
    assert len(rows) == args.expected_count
    aggregate = {}
    for key in ["psnr", "ssim", "lpips"]:
        std, mean = torch.std_mean(torch.tensor([row[key] for row in rows], dtype=torch.float32))
        aggregate[key] = float(mean)
        aggregate[key + "_std"] = float(std)
    if args.compare_aggregate:
        reference = json.loads(args.compare_aggregate.read_text())["results"]
        for key, value in aggregate.items():
            if not math.isclose(value, reference[key], rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError(f"Evaluator mismatch: {key}={value}, reference={reference[key]}")
        print("MATCHES_EXISTING_NS_EVAL_METRICS", flush=True)
    with (args.output_dir / "per-view.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    result = {
        "scope": args.scope, "experiment_name": config.experiment_name,
        "method_name": config.method_name, "checkpoint": str(checkpoint),
        "step": step, "image_count": len(rows), "results": aggregate,
        "elapsed_seconds_including_image_writes": time.perf_counter() - start,
        "standard_deviation_scope": "across images, not repeated training runs",
        "evaluator": "Nerfstudio model metrics on float images; no color correction; white background",
    }
    (args.output_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
