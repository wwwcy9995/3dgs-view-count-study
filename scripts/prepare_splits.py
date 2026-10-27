"""Make nested training splits and a validation-only pipeline pilot.

The original test views never become training/validation views. Selection uses
camera geometry only, without reading test pixels or scoring any model output.
"""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/nerf_synthetic/lego"


def pose_key(frame):
    matrix = np.asarray(frame["transform_matrix"], dtype=np.float64)
    return hashlib.sha256(np.round(matrix, 6).tobytes()).hexdigest()


def spread_order(frames):
    """Deterministic farthest-point traversal of camera viewing directions."""
    positions = np.array([f["transform_matrix"] for f in frames], dtype=np.float64)[:, :3, 3]
    directions = positions / np.linalg.norm(positions, axis=1, keepdims=True)
    chosen = [0]
    distances = np.full(len(frames), np.inf)
    for _ in range(1, len(frames)):
        distances = np.minimum(distances, np.sum((directions - directions[chosen[-1]]) ** 2, axis=1))
        distances[chosen] = -1
        chosen.append(int(np.argmax(distances)))
    return chosen


def write_dataset(directory, train, validation, test, metadata):
    directory.mkdir(parents=True, exist_ok=True)
    for name, frames in [("train", train), ("val", validation), ("test", test)]:
        output = copy.deepcopy(metadata)
        output["frames"] = copy.deepcopy(frames)
        for frame in output["frames"]:
            relative = Path(frame["file_path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unexpected source image path")
            image = RAW / (str(relative) + ".png")
            if not image.is_file():
                raise FileNotFoundError(image)
            # BlenderDataParser strips './' globally; use absolute Linux paths
            # rather than '../' references. Regenerate after moving the project.
            frame["file_path"] = str((RAW / relative).resolve())
        (directory / f"transforms_{name}.json").write_text(json.dumps(output, indent=2), encoding="utf-8")


def main():
    source = {name: json.loads((RAW / f"transforms_{name}.json").read_text()) for name in ["train", "val", "test"]}
    assert all(np.isclose(source[name]["camera_angle_x"], source["train"]["camera_angle_x"], rtol=0, atol=1e-10) for name in source)
    train = source["train"]["frames"]
    test = source["test"]["frames"]
    test_keys = {pose_key(frame) for frame in test}
    train_keys = {pose_key(frame) for frame in train}
    if train_keys & test_keys:
        raise ValueError("Original training and test sets contain overlapping camera poses")
    validation = [frame for frame in source["val"]["frames"] if pose_key(frame) not in test_keys | train_keys]
    if len(validation) < 8:
        raise ValueError("Not enough validation views independent of the official training/test sets")
    order = spread_order(train)
    val_order = spread_order(validation)
    pilot_val = [validation[i] for i in val_order[:8]]
    manifest = {
        "scene": "lego",
        "selection": "farthest-point traversal on normalized camera centers, first original training view as anchor",
        "training_order_original_indices": order,
        "source_train_count": len(train),
        "source_val_count": len(source["val"]["frames"]),
        "disjoint_validation_count": len(validation),
        "test_count": len(test),
        "groups": {},
        "test_files": [f["file_path"] for f in test],
        "validation_files": [f["file_path"] for f in validation],
        "pilot": {"train_count": 10, "evaluation_source": "8 official validation images; NOT formal test metrics", "evaluation_files": [f["file_path"] for f in pilot_val]},
        "point_cloud": "no SfM or reconstruction from full data; use fixed image-independent initialization",
        "camera_parameters": "ground-truth Blender camera parameters supplied by original synthetic dataset",
    }
    for count in [10, 20, 40]:
        if count > len(train):
            raise ValueError("Requested training view count exceeds available images")
        indices = sorted(order[:count])
        selected = [train[i] for i in indices]
        write_dataset(ROOT / f"data/splits/lego/n{count:03d}", selected, validation, test, source["train"])
        manifest["groups"][str(count)] = {"indices": indices, "files": [f["file_path"] for f in selected]}
    write_dataset(ROOT / "data/splits/lego/pilot", [train[i] for i in sorted(order[:10])], pilot_val, pilot_val, source["train"])
    records = ROOT / "records/data"
    records.mkdir(parents=True, exist_ok=True)
    (records / "lego-splits.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # A common, image-independent initialization eliminates full-dataset SfM
    # leakage and also makes the exact initial points identical across groups.
    initial = ROOT / "data/initialization/lego_random_seed42.ply"
    initial.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    points = rng.uniform(-1.5, 1.5, (10000,3)).astype(np.float32)
    with initial.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("ply\nformat ascii 1.0\nelement vertex 10000\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for point in points:
            stream.write(f"{point[0]:.9g} {point[1]:.9g} {point[2]:.9g} 128 128 128\n")
    (records / "initialization.json").write_text(json.dumps({
        "kind": "image-independent random points, not SfM and not a reconstructed scene",
        "count": 10000, "seed": 42, "rng": "numpy.default_rng/PCG64",
        "bounds": [[-1.5,-1.5,-1.5],[1.5,1.5,1.5]], "rgb": [128,128,128],
        "file": "data/initialization/lego_random_seed42.ply",
        "sha256": hashlib.sha256(initial.read_bytes()).hexdigest(),
        "policy": "Use this exact point cloud for every view-count group; no input image is used to generate it",
    }, indent=2), encoding="utf-8")
    print(json.dumps({"nested_train_counts": [10,20,40], "official_test_count": len(test), "pilot_validation_count": len(pilot_val)}, indent=2))


if __name__ == "__main__":
    main()
