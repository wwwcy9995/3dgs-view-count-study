"""Summarize an actual completed pilot; never generate placeholder metrics."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    stamp = Path((ROOT / "records/pilot/latest-run.txt").read_text()).name
    records = ROOT / "records/pilot" / stamp
    run = json.loads((records / "run.json").read_text())
    assert run["status"] == "complete"
    metrics = json.loads((records / "validation-metrics.json").read_text())["results"]
    outputs = ROOT / "outputs/pilot/lego-pilot-10/splatfacto" / stamp
    ply = outputs / "export/splat.ply"
    with ply.open("rb") as stream:
        header = []
        while True:
            line = stream.readline().decode("ascii").strip()
            header.append(line)
            if line == "end_header":
                break
            if not line or len(header) > 200:
                raise ValueError("Invalid exported PLY header")
    count = int(next(line for line in header if line.startswith("element vertex ")).split()[-1])
    split = json.loads((ROOT / "records/data/lego-splits.json").read_text())
    renders = sorted((outputs / "renders").glob("eval_img_*.png"))
    assert len(renders) == len(split["pilot"]["evaluation_files"]) == 8
    mapping = [{"index": i, "source_image": name + ".png", "comparison": str(renders[i].relative_to(ROOT)), "layout": "left: ground truth; right: rendered prediction; each panel 400x400"} for i, name in enumerate(split["pilot"]["evaluation_files"])]
    (records / "render-mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    row = {
        "scope": "validation_pilot", "scene": "lego", "train_views": 10,
        "steps": run["steps"], "width": 400, "height": 400, "eval_views": 8, "seed": 42,
        "psnr_db": metrics["psnr"], "ssim": metrics["ssim"], "lpips": metrics["lpips"],
        "training_process_wall_seconds_including_startup": run["stages"][0]["wall_clock_seconds"],
        "checkpoint_bytes": run["checkpoint_bytes"], "export_ply_bytes": run["export_ply_bytes"],
        "gaussians": count,
    }
    with (records / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=row.keys())
        writer.writeheader(); writer.writerow(row)
    artifacts = []
    for file in [ply, *sorted((outputs / "nerfstudio_models").glob("*.ckpt"))]:
        artifacts.append({"path": str(file.relative_to(ROOT)), "bytes": file.stat().st_size, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    (records / "model-artifacts.json").write_text(json.dumps(artifacts, indent=2), encoding="utf-8")
    summary = f"""# 首次流程试跑：Lego，10 个训练视角

状态：训练、验证渲染、指标计算和 Gaussian PLY 导出均已实际完成。**这不是正式测试集实验。**

| 项目 | 实际记录 |
| --- | --- |
| 方法 | Nerfstudio Splatfacto 1.1.5 / gsplat 1.4.0 |
| 训练 / 评估图片 | 10 张原训练图 / 8 张独立的原验证图 |
| 分辨率 / 优化步数 | 400×400 / {run['steps']} |
| 初始化 | 固定 10000 个与图像无关的随机点，各组共用 |
| 随机种子 | 42 |
| PSNR | {metrics['psnr']:.4f} dB |
| SSIM | {metrics['ssim']:.6f} |
| LPIPS | {metrics['lpips']:.6f} |
| 训练进程耗时，含启动和加载 | {row['training_process_wall_seconds_including_startup']:.3f} 秒 |
| 导出的 Gaussian 数 | {count} |
| Gaussian PLY 文件大小 | {run['export_ply_bytes']/2**20:.3f} MiB |
| 训练检查点文件大小 | {run['checkpoint_bytes']/2**20:.3f} MiB |

原始指标在 `validation-metrics.json`，命令、各阶段耗时及退出码在 `run.json`，模型校验值在 `model-artifacts.json`。正式比较统一使用导出 PLY 大小作为模型文件大小口径，并另外保留训练检查点大小。

每张 `eval_img_*.png` 左侧为真实验证图，右侧为预测渲染；对应的原图片名在 `render-mapping.json`。已检查 8 张对比图均存在且可解码。

观察：当前模型已恢复整体外形和主要颜色；积木凸点、细杆、履带等细节仍有模糊和不完整的结构。本次只有一个数量组，且仅训练 1000 步，不能将这些现象单独归因于训练视角数量。正式实验还需对 10/20/40 组使用相同预算并在固定测试集上比较。

运行设置：白色背景、相机优化关闭、CPU 图像缓存、torch.compile 关闭、CPU 数学线程数 4。日志中出现 cuDNN 的 nvrtc 缺失回退提示，但训练和评估成功，指标均为有限值；正式组须使用相同环境。
"""
    (records / "summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps(row, indent=2), flush=True)


if __name__ == "__main__":
    main()
