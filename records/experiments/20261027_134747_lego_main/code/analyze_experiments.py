"""Summarize completed experiments and draw predetermined view comparisons."""

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def csv_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    args = parser.parse_args()
    run_id = args.run_id or json.loads((ROOT / "records/experiments/latest-run.json").read_text())["run_id"]
    records = ROOT / "records/experiments" / run_id
    session = json.loads((records / "session.json").read_text())
    assert session["status"] == "complete", "Experiments have not completed"
    protocol = session["protocol"]
    figures = records / "figures"
    figures.mkdir(exist_ok=True)
    rows = []
    per_view = {}
    ordered_names = None
    for count in protocol["train_views"]:
        group = session["groups"][str(count)]
        result = json.loads((records / f"n{count:03d}/test/metrics.json").read_text())
        assert result["scope"] == "formal_test" and result["image_count"] == 200 and result["step"] == 29999
        values = result["results"]
        image_rows = csv_rows(records / f"n{count:03d}/test/per-view.csv")
        assert len(image_rows) == 200
        assert [int(row["index"]) for row in image_rows] == list(range(200))
        names = [row["source_image"] for row in image_rows]
        if ordered_names is not None:
            assert names == ordered_names, "Test image order differs"
        ordered_names = names
        per_view[count] = image_rows
        for key in ["psnr", "ssim", "lpips"]:
            assert all(math.isfinite(float(row[key])) for row in image_rows)
            assert math.isclose(float(np.mean([float(row[key]) for row in image_rows])), values[key], rel_tol=1e-5, abs_tol=1e-5)
        renders = list((ROOT / group["output"] / "test-renders").glob("eval_img_*.png"))
        assert len(renders) == 200
        training = [stage for stage in group["stages"] if stage["name"] == "training" and stage["status"] == "complete"][-1]
        clock_span=(datetime.fromisoformat(training["finished_at"])-datetime.fromisoformat(training["started_at"])).total_seconds()
        ply = next(artifact for artifact in group["artifacts"] if artifact["path"].endswith(".ply"))
        ckpt = next(artifact for artifact in group["artifacts"] if artifact["path"].endswith(".ckpt"))
        rows.append({"scene": "lego", "train_views": count, "test_views": 200, "steps": 30000, "seed": 42,
                     "psnr_db": values["psnr"], "ssim": values["ssim"], "lpips": values["lpips"],
                     "psnr_image_std": values["psnr_std"], "ssim_image_std": values["ssim_std"], "lpips_image_std": values["lpips_std"],
                     "train_process_elapsed_seconds": training["wall_clock_seconds"],
                     "start_finish_clock_seconds":clock_span,
                     "clock_gap_seconds":clock_span-training["wall_clock_seconds"],
                     "gaussians": group["gaussians"], "ply_bytes": ply["bytes"], "ply_mib": ply["bytes"]/2**20,
                     "checkpoint_bytes": ckpt["bytes"]})
    write_csv(records / "summary.csv", rows)
    differences = []
    for low, high in [(10,20),(10,40),(20,40)]:
        for metric in ["psnr","ssim","lpips"]:
            sign = -1 if metric == "lpips" else 1
            delta = np.array([sign * (float(b[metric])-float(a[metric])) for a,b in zip(per_view[low],per_view[high])])
            differences.append({"comparison": f"{high}_vs_{low}", "metric": metric,
                                "positive_means": "higher-view-count model improves",
                                "mean_improvement": float(delta.mean()),
                                "improved_images": int((delta>0).sum()), "worse_images": int((delta<0).sum()),
                                "unchanged_images": int((delta==0).sum()), "test_images": len(delta)})
    write_csv(records / "paired-view-differences.csv", differences)

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1,3,figsize=(10.5,3.7),layout="constrained")
    for axis, metric, label, color in zip(axes,["psnr_db","ssim","lpips"],["PSNR (dB; higher is better)","SSIM (higher is better)","LPIPS (lower is better)"],["#247ba0","#23856d","#d65a31"]):
        xs=[row["train_views"] for row in rows]
        ys=[row[metric] for row in rows]
        axis.plot(xs,ys,"o-",color=color,lw=1.6,ms=6)
        for x,y in zip(xs,ys):
            axis.annotate(f"{y:.3f}",(x,y),xytext=(0,8),textcoords="offset points",ha="center",fontsize=9)
        axis.set(xlabel="Training views",ylabel=label,xticks=xs)
        axis.margins(x=.15,y=.25)
        axis.grid(axis="y",alpha=.2)
    fig.suptitle("Lego | 30,000 steps | 200 fixed test views | one training seed",fontsize=12)
    fig.savefig(figures/"quality-vs-views.png",dpi=180,bbox_inches="tight",pad_inches=.15)
    fig.savefig(figures/"quality-vs-views.svg",bbox_inches="tight",pad_inches=.15)
    plt.close(fig)
    fig, axes = plt.subplots(1,2,figsize=(7.5,3.5),layout="constrained")
    for axis,key,label in [(axes[0],"train_process_elapsed_seconds","Elapsed process timer (seconds)"),(axes[1],"ply_mib","Exported Gaussian PLY (MiB)")]:
        values=[row[key] for row in rows]
        axis.bar([str(row["train_views"]) for row in rows],values,color=["#d65a31","#247ba0","#23856d"],width=.6)
        axis.set(xlabel="Training views",ylabel=label)
        axis.set_ylim(0,max(values)*1.18)
        for i,value in enumerate(values):
            axis.text(i,value+max(values)*.025,f"{value:.2f}",ha="center",fontsize=9)
    fig.suptitle("Same 30,000-step budget; monotonic timer includes startup/loading",fontsize=11)
    fig.savefig(figures/"time-and-size.png",dpi=180,bbox_inches="tight",pad_inches=.15)
    plt.close(fig)

    crop_records = []
    for index in protocol["comparison_indices"]:
        panels = []
        reference_gt = None
        for count in protocol["train_views"]:
            group = session["groups"][str(count)]
            file = ROOT / group["output"] / f"test-renders/eval_img_{index:04d}.png"
            with Image.open(file) as image:
                pair = np.asarray(image.convert("RGB"))
            assert pair.shape == (400,800,3)
            gt,prediction = pair[:,:400],pair[:,400:]
            if reference_gt is None:
                reference_gt = gt.copy(); panels.append(gt)
            else:
                assert np.array_equal(reference_gt,gt), "Ground truth differs between groups"
            panels.append(prediction)
        mask=np.any(reference_gt<250,axis=2)
        ys,xs=np.where(mask)
        assert len(xs)>0
        cx,cy=(xs.min()+xs.max())/2,(ys.min()+ys.max())/2
        width=max(8,int((xs.max()-xs.min()+1)*.4));height=max(8,int((ys.max()-ys.min()+1)*.4))
        x0=max(0,int(cx-width/2));y0=max(0,int(cy-height/2));x1=min(400,x0+width);y1=min(400,y0+height)
        fig,axes=plt.subplots(2,4,figsize=(11,6.2),layout="constrained")
        labels=["Ground truth","10 views","20 views","40 views"]
        for column,(panel,label) in enumerate(zip(panels,labels)):
            axes[0,column].imshow(panel,interpolation="nearest")
            axes[0,column].add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor="#c93434",linewidth=1.2))
            axes[0,column].set_title(label)
            axes[1,column].imshow(panel[y0:y1,x0:x1],interpolation="nearest")
            axes[1,column].set_title(label+" crop",fontsize=9)
            axes[0,column].axis("off");axes[1,column].axis("off")
        fig.suptitle(f"Fixed test view {index:04d} | 30,000 steps | same crop in every column",fontsize=12)
        fig.savefig(figures/f"test-view-{index:04d}.png",dpi=180,bbox_inches="tight",pad_inches=.15)
        plt.close(fig)
        crop_records.append({"index":index,"source_image":ordered_names[index],"crop_xyxy":[x0,y0,x1,y1],"policy":protocol["crop_policy"]})
    (records/"comparison-crops.json").write_text(json.dumps(crop_records,indent=2),encoding="utf-8")
    table="\n".join(f"| {r['train_views']} | {r['psnr_db']:.4f} | {r['ssim']:.6f} | {r['lpips']:.6f} | {r['train_process_elapsed_seconds']:.2f} | {r['ply_mib']:.3f} | {r['gaussians']} |" for r in rows)
    clock_notes="\n".join(f"- {r['train_views']} 视角：单调计时 {r['train_process_elapsed_seconds']:.3f} 秒，系统起止时刻跨度 {r['start_finish_clock_seconds']:.3f} 秒，差值 {r['clock_gap_seconds']:.3f} 秒。" for r in rows)
    diff_lines="\n".join(f"- {d['comparison']}，{d['metric']}：平均有利变化 {d['mean_improvement']:.6f}，改善 {d['improved_images']}/200 张、变差 {d['worse_images']}/200 张。" for d in differences)
    summary=f"""# Lego 正式视角数量对比

运行编号：{run_id}。以下指标来自实际完成的 200 张固定测试图评估，所有组均从共同初始化点云开始，训练 30000 步、400×400、种子 42。训练全部结束后才开始测试；没有根据测试结果调整设置。

| 训练视角 | PSNR/dB | SSIM | LPIPS | 训练进程单调计时/s | PLY/MiB | Gaussian 数量 |
| --- | --- | --- | --- | --- | --- | --- |
{table}

PSNR、SSIM 越高越好，LPIPS 越低越好。进程计时使用 time.perf_counter，包含启动和模型/数据加载，评估与导出另行记录；它与系统挂起或宿主时钟变化后的日历时间跨度可能不同。原记录字段名 wall_clock_seconds 保留，汇总中准确标为进程单调计时。模型文件大小统一采用导出的 Gaussian PLY；训练检查点大小保留在 summary.csv。每张测试图的原始指标在各组 test/per-view.csv。

### 时间记录核对

{clock_notes}

本次出现的显著时钟差值保留在记录中，不把它解释为模型训练变慢。时间只能作为本机单次运行的描述性记录，不据此作严格性能排序；图像指标与固定 30000 次训练更新的比较另外核对。

## 同一测试图上的配对差异

下述“有利变化”对 PSNR/SSIM 定义为更多视角组减更少视角组，对 LPIPS 定义为更少视角组减更多视角组。这里只描述本次运行，不进行显著性推断。

{diff_lines}

## 图像对照与局限

figures/ 中包含指标趋势图、时间和大小图，以及预先固定的测试视角 0、50、100、150 的同视角全图和局部放大。局部区域取真实图前景包围盒的中心，宽、高各取 40%，对所有组使用相同坐标；裁剪清单在 comparison-crops.json。

- 方法是 Nerfstudio Splatfacto，实现后端为 gsplat，不能与原论文训练实现混称。
- 数据是公开合成场景，使用数据集提供的真实相机参数；没有从少量图像估计位姿，不是端到端稀疏重建实验。
- 初始化为所有组共用的 10000 个随机点，与所有图像独立；不使用全量 SfM 点云。
- 10/20/40 组从原 100 个训练候选相机中按方向最远点遍历构造嵌套子集，使用公开候选相机参数，不为每组重新估计位姿。
- 这是固定训练步数预算下的比较，每张训练图被采样的次数会随训练图总数变化。
- Splatfacto 采用自适应增密和裁剪，各组最终 Gaussian 数量可能不同；已记录规模，但没有强制相同最终参数量。
- 目前只有一个场景、一个训练种子；图像之间的标准差不等于重复训练的波动，不能推广为所有场景必然遵循的规律。
- 使用相同软件环境、白背景、关闭相机优化与 torch.compile。训练日志中的 cuDNN nvrtc 回退提示保留在记录中。
"""
    (records/"summary.md").write_text(summary,encoding="utf-8")
    (records/"summary.json").write_text(json.dumps({"run_id":run_id,"rows":rows,"paired_differences":differences},indent=2),encoding="utf-8")
    print(json.dumps(rows,indent=2),flush=True)
    print("ANALYSIS_READY",records,flush=True)


if __name__ == "__main__":
    main()
