"""Redraw archived metric trends without models, datasets or a GPU."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from verify_published_results import main as verify

ROOT = Path(__file__).resolve().parents[1]
def main():
    verify()
    record = ROOT / "records/experiments/20261027_134747_lego_main"
    rows = json.loads((record / "summary.json").read_text(encoding="utf-8"))["rows"]
    out = ROOT / "local/replotted-results"
    out.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1,3,figsize=(10.5,3.7),layout="constrained")
    for ax, key, label in zip(axes,["psnr_db","ssim","lpips"],["PSNR (dB; higher is better)","SSIM (higher is better)","LPIPS (lower is better)"]):
        x = [r["train_views"] for r in rows]; y = [r[key] for r in rows]
        ax.plot(x,y,"o-")
        ax.set(xlabel="Training views",ylabel=label,xticks=x)
        ax.grid(axis="y",alpha=.2)
    fig.suptitle("Lego | 30,000 steps | 200 fixed test views | one seed")
    fig.savefig(out / "quality-vs-views.png",dpi=180)
    plt.close(fig)
    print(out / "quality-vs-views.png")
if __name__ == "__main__":
    main()
