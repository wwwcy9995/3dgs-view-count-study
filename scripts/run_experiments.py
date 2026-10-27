"""Run the frozen Lego protocol: train every group before testing any group."""

import argparse
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(TZ).isoformat()


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(2**20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def plain(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, type):
        return value.__module__ + "." + value.__qualname__
    if isinstance(value, Enum):
        return plain(value.value)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(x) for x in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, float, int, bool)):
        return value
    return str(value)


def preflight(protocol):
    assert protocol["steps"] == 30000 and protocol["train_views"] == [10,20,40]
    assert protocol["resolution"] == [400,400] and protocol["test_views"] == 200
    initialization = json.loads((ROOT / protocol["initialization_manifest"]).read_text())
    assert digest(ROOT / protocol["initial_point_cloud"]) == initialization["sha256"]
    saved = json.loads((ROOT / "records/data/lego-splits.json").read_text())
    train_sets = []
    common_test = None
    raw = ROOT / "data/raw/nerf_synthetic/lego"
    for count in protocol["train_views"]:
        directory = ROOT / f"data/splits/lego/n{count:03d}"
        train = json.loads((directory / "transforms_train.json").read_text())
        test = json.loads((directory / "transforms_test.json").read_text())
        assert len(train["frames"]) == count and len(test["frames"]) == protocol["test_views"]
        names = {str(Path(f["file_path"]).relative_to(raw)) for f in train["frames"]}
        assert names == {str(Path(name)) for name in saved["groups"][str(count)]["files"]}
        train_sets.append(names)
        if common_test is not None:
            assert test == common_test, "Test views differ between groups"
        common_test = test
        for frame in train["frames"] + test["frames"]:
            assert Path(frame["file_path"] + ".png").is_file()
    assert train_sets[0] < train_sets[1] < train_sets[2]
    assert len({f["file_path"] for f in common_test["frames"]}) == 200
    reference = json.loads((ROOT / "records/setup/environment.json").read_text())
    for name, version in reference["packages"].items():
        assert importlib.metadata.version(name) == version, f"Environment changed: {name}"
    result = {"checked_at": now(), "initialization_sha256": initialization["sha256"],
              "splits_sha256": digest(ROOT / "records/data/lego-splits.json"),
              "common_test_json_sha256": hashlib.sha256(json.dumps(common_test, sort_keys=True).encode()).hexdigest(),
              "packages": reference["packages"], "nested_training_sets": True, "common_test_count": 200}
    return result


def config_fingerprint(path, protocol):
    # These YAMLs were produced by this runner's own pinned ns-train process.
    config = yaml.load(path.read_text(), Loader=yaml.Loader)
    assert config.max_num_iterations == protocol["steps"] and config.machine.seed == protocol["seed"]
    assert config.load_dir is None and config.load_checkpoint is None
    manager = config.pipeline.datamanager
    assert manager.camera_res_scale_factor == protocol["image_scale"]
    assert manager.dataparser.ply_path == ROOT / protocol["initial_point_cloud"]
    assert manager.dataparser.alpha_color == "white"
    assert config.pipeline.model.background_color == "white"
    assert config.pipeline.model.num_downscales == 0
    assert config.pipeline.model.camera_optimizer.mode == "off"
    common = {"model": plain(config.pipeline.model), "optimizers": plain(config.optimizers),
              "seed": config.machine.seed, "steps": config.max_num_iterations,
              "camera_res_scale_factor": manager.camera_res_scale_factor,
              "cache_images": manager.cache_images, "cache_images_type": manager.cache_images_type,
              "steps_per_eval_image": config.steps_per_eval_image,
              "steps_per_eval_all_images": config.steps_per_eval_all_images}
    return common, hashlib.sha256(json.dumps(common, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", help="Existing run id; completed stages are reused, unfinished training restarts from scratch")
    args = parser.parse_args()
    lock_dir = Path.home() / ".cache/splat-course"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = (lock_dir / "experiment.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    protocol_file = ROOT / "configs/lego-main.json"
    protocol = json.loads(protocol_file.read_text())
    check = preflight(protocol)
    env = os.environ.copy()
    env.update({"TORCH_HOME": str(ROOT / ".cache/torch"), "TORCH_COMPILE_DISABLE": "1", "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1",
                "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4"})
    if args.resume:
        if not re.fullmatch(r"\d{8}_\d{6}_lego_main", args.resume):
            raise ValueError("Invalid run id")
        run_id = args.resume
        records = ROOT / "records/experiments" / run_id
        state = json.loads((records / "session.json").read_text())
        assert state["protocol"] == protocol, "Protocol changed; create a new run instead"
        assert state["preflight"]["splits_sha256"] == check["splits_sha256"]
        assert state["preflight"]["initialization_sha256"] == check["initialization_sha256"]
    else:
        run_id = datetime.now(TZ).strftime("%Y%m%d_%H%M%S_lego_main")
        records = ROOT / "records/experiments" / run_id
        records.mkdir(parents=True, exist_ok=False)
        state = {"run_id": run_id, "started_at": now(), "status": "running", "protocol": protocol, "preflight": check,
                 "script_sha256": {name: digest(ROOT / name) for name in ["scripts/run_experiments.py", "scripts/evaluate_views.py", "configs/lego-main.json"]},
                 "groups": {str(n): {"train_views": n, "stages": []} for n in protocol["train_views"]}}
        save_json(records / "protocol-frozen.json", protocol)
        # Preserve the exact script sources that generated this experiment.
        for name in ["run_experiments.py", "evaluate_views.py"]:
            target = records / "code" / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes((ROOT / "scripts" / name).read_bytes())
    state["status"] = "running"
    state_path = records / "session.json"
    save_json(state_path, state)
    save_json(ROOT / "records/experiments/active-run.json", {"run_id": run_id, "session": str(state_path.relative_to(ROOT))})
    print("FORMAL_RUN", run_id, flush=True)

    def completed(group, name):
        return any(s["name"] == name and s["status"] == "complete" for s in group["stages"])

    def stage(group, name, command):
        attempt = sum(s["name"] == name for s in group["stages"]) + 1
        group_dir = records / f"n{group['train_views']:03d}"
        group_dir.mkdir(parents=True, exist_ok=True)
        log_path = group_dir / f"{name}-a{attempt}.log"
        entry = {"name": name, "attempt": attempt, "started_at": now(), "status": "running", "command": command, "log": str(log_path.relative_to(ROOT))}
        group["stages"].append(entry)
        state["current_group"] = group["train_views"]
        state["current_stage"] = name
        save_json(state_path, state)
        print(f"STAGE n{group['train_views']:03d} {name}", flush=True)
        start = time.perf_counter()
        last_step = -1
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            entry["pid"] = process.pid
            save_json(state_path, state)
            for line in process.stdout:
                log.write(line); log.flush()
                clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
                match = re.match(r"\s*(\d+)\s+\([\d.]+%\)", clean)
                if match and int(match[1]) > last_step:
                    last_step = int(match[1])
                    entry["last_logged_step"] = last_step
                    save_json(state_path, state)
                    if last_step % 1000 == 0 or last_step == protocol["steps"] - 1:
                        print(f"PROGRESS n{group['train_views']:03d} {last_step}/{protocol['steps']}", flush=True)
                elif name != "training" and ("EVALUATED" in line or "checkpoint" in line):
                    print(clean.rstrip(), flush=True)
            code = process.wait()
        entry.update({"exit_code": code, "wall_clock_seconds": time.perf_counter() - start, "finished_at": now(), "status": "complete" if code == 0 else "failed"})
        if code:
            state["status"] = "failed"
            save_json(state_path, state)
            print(log_path.read_text()[-10000:], flush=True)
            raise SystemExit(code)
        save_json(state_path, state)
        print(f"DONE n{group['train_views']:03d} {name} {entry['wall_clock_seconds']:.2f}s", flush=True)

    # No formal test images are evaluated until every training process succeeds.
    for count in protocol["training_order"]:
        group = state["groups"][str(count)]
        if completed(group, "training"):
            assert (ROOT / group["config"]).is_file()
            continue
        attempt = sum(s["name"] == "training" for s in group["stages"]) + 1
        stamp = f"{run_id}_a{attempt}"
        output = ROOT / f"outputs/experiments/{run_id}/lego-n{count:03d}-s42/splatfacto" / stamp
        group["output"] = str(output.relative_to(ROOT))
        group["config"] = str((output / "config.yml").relative_to(ROOT))
        command = ["ns-train", "splatfacto", "--output-dir", str(ROOT / "outputs/experiments" / run_id),
                   "--experiment-name", f"lego-n{count:03d}-s42", "--timestamp", stamp, "--vis", "tensorboard",
                   "--max-num-iterations", str(protocol["steps"]), "--steps-per-save", "5000",
                   "--steps-per-eval-image", "0", "--steps-per-eval-batch", "0", "--steps-per-eval-all-images", "0",
                   "--machine.seed", "42", "--logging.steps-per-log", "500", "--logging.local-writer.max-log-size", "1",
                   "--pipeline.datamanager.camera-res-scale-factor", "0.5", "--pipeline.datamanager.cache-images", "cpu",
                   "--pipeline.model.background-color", "white", "--pipeline.model.num-downscales", "0",
                   "--pipeline.model.random-init", "False", "--pipeline.model.camera-optimizer.mode", "off",
                   "blender-data", "--data", str(ROOT / f"data/splits/lego/n{count:03d}"), "--alpha-color", "white",
                   "--ply-path", str(ROOT / protocol["initial_point_cloud"])]
        stage(group, "training", command)
        checkpoint = output / "nerfstudio_models/step-000029999.ckpt"
        assert checkpoint.is_file(), "Final checkpoint is missing"
        group["checkpoint"] = str(checkpoint.relative_to(ROOT))
        save_json(state_path, state)
    fingerprints = {}
    for count in protocol["train_views"]:
        group = state["groups"][str(count)]
        common, fingerprint = config_fingerprint(ROOT / group["config"], protocol)
        fingerprints[str(count)] = fingerprint
    assert len(set(fingerprints.values())) == 1, "Training settings are not identical"
    save_json(records / "common-training-settings.json", {"fingerprints": fingerprints, "settings": common})
    assert digest(ROOT / protocol["initial_point_cloud"]) == check["initialization_sha256"]
    print("ALL_TRAINING_COMPLETE_AND_SETTINGS_IDENTICAL", flush=True)
    for count in protocol["train_views"]:
        group = state["groups"][str(count)]
        output = ROOT / group["output"]
        group_records = records / f"n{count:03d}"
        if not completed(group, "evaluation"):
            stage(group, "evaluation", ["python", "-u", "scripts/evaluate_views.py", "--load-config", str(ROOT / group["config"]),
                  "--output-dir", str(group_records / "test"), "--render-dir", str(output / "test-renders"),
                  "--expected-count", "200", "--scope", "formal_test"])
        if not completed(group, "export"):
            stage(group, "export", ["ns-export", "gaussian-splat", "--load-config", str(ROOT / group["config"]), "--output-dir", str(output / "export")])
        ply = output / "export/splat.ply"
        with ply.open("rb") as stream:
            for _ in range(200):
                line = stream.readline().decode("ascii").strip()
                if line.startswith("element vertex "):
                    group["gaussians"] = int(line.split()[-1])
                if line == "end_header":
                    break
        group["artifacts"] = [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest(path)} for path in [ROOT / group["checkpoint"], ply]]
        save_json(state_path, state)
    state["status"] = "complete"
    state["finished_at"] = now()
    state.pop("current_stage", None)
    save_json(state_path, state)
    save_json(ROOT / "records/experiments/latest-run.json", {"run_id": run_id, "session": str(state_path.relative_to(ROOT))})
    print("FORMAL_EXPERIMENTS_COMPLETE", run_id, flush=True)


if __name__ == "__main__":
    main()
