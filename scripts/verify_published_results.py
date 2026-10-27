"""Verify published numeric evidence with the Python standard library only."""
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "records/experiments/20261027_134747_lego_main"

def main():
    result = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
    session = json.loads((RUN / "session.json").read_text(encoding="utf-8"))
    assert session["status"] == "complete"
    split = json.loads((ROOT / "records/data/lego-splits.json").read_text(encoding="utf-8"))
    sets = [set(split["groups"][str(n)]["files"]) for n in [10,20,40]]
    assert sets[0] < sets[1] < sets[2]
    assert len(set(split["test_files"])) == 200
    assert not sets[2].intersection(split["test_files"])
    common_names = None
    for row in result["rows"]:
        n = row["train_views"]
        with (RUN / f"n{n:03d}/test/per-view.csv").open(encoding="utf-8", newline="") as f:
            images = list(csv.DictReader(f))
        assert len(images) == 200 and [int(i["index"]) for i in images] == list(range(200))
        names = [i["source_image"] for i in images]
        assert common_names is None or names == common_names
        common_names = names
        for metric, key in [("psnr","psnr_db"),("ssim","ssim"),("lpips","lpips")]:
            values = [float(i[metric]) for i in images]
            assert all(math.isfinite(v) for v in values)
            assert math.isclose(mean(values),row[key],abs_tol=1e-5,rel_tol=1e-5)
        stages = session["groups"][str(n)]["stages"]
        assert len(stages) == 3 and all(s["exit_code"] == 0 for s in stages)
        print(f"{n} views: 200 images and all three successful stages verified")
    fingerprints = json.loads((RUN / "common-training-settings.json").read_text(encoding="utf-8"))["fingerprints"]
    assert len(set(fingerprints.values())) == 1
    provenance = json.loads((RUN / "analysis-provenance.json").read_text(encoding="utf-8"))
    # The manifest checks public copies; original provenance remains archival.
    manifest = json.loads((ROOT / "publication-manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        assert hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["published_sha256"], entry["path"]
    print("Nested splits, fixed test identities, common settings and publication hashes verified.")
    print("This checks archived evidence; it does not rerun training or assert model files are present.")

if __name__ == "__main__":
    main()
