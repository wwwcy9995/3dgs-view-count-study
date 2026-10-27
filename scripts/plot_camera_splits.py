"""Plot supplied camera positions for the actual, saved training subsets."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def centers(frames):
    return np.asarray([frame["transform_matrix"] for frame in frames])[:, :3, 3]


def main():
    raw = ROOT / "data/raw/nerf_synthetic/lego"
    manifest = json.loads((ROOT / "records/data/lego-splits.json").read_text())
    train = centers(json.loads((raw / "transforms_train.json").read_text())["frames"])
    test = centers(json.loads((raw / "transforms_test.json").read_text())["frames"])
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 11})
    figure = plt.figure(figsize=(10.5, 4), layout="constrained")
    for panel, (count, color) in enumerate([(10,"#d65a31"),(20,"#247ba0"),(40,"#23856d")], 1):
        axis = figure.add_subplot(1, 3, panel, projection="3d")
        selected = train[manifest["groups"][str(count)]["indices"]]
        axis.scatter(*test.T, c="#c0c5ca", s=8, alpha=0.35, label="Fixed test (200)")
        axis.scatter(*selected.T, c=color, s=25, edgecolors="white", linewidths=0.3, label=f"Training ({count})")
        axis.scatter(0,0,0,c="#303840",marker="*",s=45)
        axis.set(xlabel="X",ylabel="Y",zlabel="Z",xlim=(-4.5,4.5),ylim=(-4.5,4.5),zlim=(-0.5,4.5),title=f"{count} training views")
        axis.set_box_aspect((1,1,0.6))
        axis.view_init(elev=24,azim=42)
        axis.legend(loc="upper left",fontsize=7,frameon=False)
    figure.suptitle("Lego: nested training subsets and fixed test cameras",fontsize=13)
    output = ROOT / "records/data/camera-coverage.png"
    figure.savefig(output,dpi=180,facecolor="white",bbox_inches="tight",pad_inches=0.2)
    figure.savefig(output.with_suffix(".svg"),facecolor="white",bbox_inches="tight",pad_inches=0.2)
    plt.close(figure)
    print(output)


if __name__ == "__main__":
    main()
