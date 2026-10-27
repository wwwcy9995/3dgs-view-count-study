"""Train, render, evaluate and export a small validation-only Splatfacto pilot."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=1000)
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    records = ROOT / "records/pilot" / stamp
    records.mkdir(parents=True, exist_ok=False)
    output = ROOT / "outputs/pilot/lego-pilot-10/splatfacto" / stamp
    config = output / "config.yml"
    env = os.environ.copy()
    env.update({"TORCH_HOME": str(ROOT / ".cache/torch"), "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1", "TORCH_COMPILE_DISABLE": "1", "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4"})
    command = [
        "ns-train", "splatfacto", "--output-dir", str(ROOT / "outputs/pilot"),
        "--experiment-name", "lego-pilot-10", "--timestamp", stamp,
        "--vis", "tensorboard", "--max-num-iterations", str(args.steps),
        "--steps-per-save", str(args.steps), "--steps-per-eval-image", "0",
        "--steps-per-eval-all-images", "1000000", "--machine.seed", "42",
        "--logging.steps-per-log", "50",
        "--pipeline.datamanager.camera-res-scale-factor", "0.5",
        "--pipeline.datamanager.cache-images", "cpu",
        "--pipeline.model.background-color", "white",
        "--pipeline.model.num-downscales", "0",
        "--pipeline.model.random-init", "False",
        "--pipeline.model.camera-optimizer.mode", "off",
        "blender-data", "--data", str(ROOT / "data/splits/lego/pilot"),
        "--alpha-color", "white",
        "--ply-path", str(ROOT / "data/initialization/lego_random_seed42.ply"),
    ]
    stages = [
        ("training", command),
        ("validation_evaluation_and_rendering", ["ns-eval", "--load-config", str(config), "--output-path", str(records / "validation-metrics.json"), "--render-output-path", str(output / "renders")]),
        ("export", ["ns-export", "gaussian-splat", "--load-config", str(config), "--output-dir", str(output / "export")]),
    ]
    record = {
        "status": "running", "kind": "pipeline pilot; validation metrics only, not the formal test experiment",
        "train_views": 10, "validation_views": 8, "resolution": [400,400],
        "steps": args.steps, "seed": 42, "config": str(config),
        "initialization_manifest": "records/data/initialization.json",
        "torch_compile_disabled": True, "cpu_math_threads": 4, "stages": [],
    }
    def save():
        (records / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    save()
    for name, command in stages:
        stage = {"name": name, "command": command, "started_at": datetime.now().isoformat()}
        record["stages"].append(stage)
        save()
        print("STAGE", name, flush=True)
        start = time.perf_counter()
        with (records / f"{name}.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            returncode = process.wait()
        stage.update({"wall_clock_seconds": time.perf_counter() - start, "exit_code": returncode})
        if returncode:
            record["status"] = "failed"
            save()
            raise SystemExit(returncode)
        save()
    record["status"] = "complete"
    record["checkpoint_bytes"] = sum(p.stat().st_size for p in output.rglob("*.ckpt"))
    record["export_ply_bytes"] = sum(p.stat().st_size for p in (output / "export").glob("*.ply"))
    save()
    (ROOT / "records/pilot/latest-run.txt").write_text(str(records), encoding="utf-8")
    print("PILOT_COMPLETE", records, flush=True)


if __name__ == "__main__":
    main()
