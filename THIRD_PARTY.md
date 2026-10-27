# 来源与使用说明

## 方法与实现

- 原始 3D Gaussian Splatting：Kerbl 等，*3D Gaussian Splatting for Real-Time Radiance Field Rendering*，SIGGRAPH 2023。https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/
- 本项目实际使用 **Nerfstudio Splatfacto**，不是原论文官方训练实现。源码仓库：https://github.com/nerfstudio-project/nerfstudio ，使用标签 v1.1.5，实际提交号记录于 `records/setup/nerfstudio-commit.txt`。
- Nerfstudio 为 Apache-2.0 许可证。下载的上游源码放在 WSL 的 `${UPSTREAM_DIR}/`，保留其许可证和版权说明，不声称由课程作者原创；不将整个上游仓库重复上传。使用 Linux 原生目录避免 NTFS 的 Git 权限问题。
- Gaussian 光栅化后端：gsplat 1.4.0，https://github.com/nerfstudio-project/gsplat 。使用上游发布的 PyTorch 2.1 / CUDA 11.8 / Python 3.10 Linux 预编译包，保留上游包的许可证说明。

## 数据

- 首轮场景：**NeRF Synthetic Lego**，来自 Mildenhall 等的 NeRF 研究，ECCV 2020。项目：https://github.com/bmild/nerf 。
- 下载地址依据作者仓库的 `download_example_data.sh`，使用 HTTPS 获取 UC San Diego 托管的 `nerf_example_data.zip`，仅提取 Lego 场景。
- 数据是合成渲染图片；自带 Blender 相机参数。报告需称为图片/图像，不能称为自己拍摄的真实照片。
- 不将代码许可证推断为所有数据和原始 3D 资产的再分发许可；项目仓库只提供获取脚本和来源，不重新分发数据。
- 下载来源、实际图片数、归档 SHA-256 记录于 `records/data/lego-source.json`。
- 相机参数由原数据集提供，不从少量图片估计。本实验不评价相机位姿恢复能力，也不声称端到端稀疏重建。
- 初始化点云由固定随机数生成，不从训练、验证或测试图像提取。所有数量组使用同一文件，其参数与校验值记录于 `records/data/initialization.json`。

## 评估依赖

- PSNR、SSIM、LPIPS 由实际运行的评估代码计算；不预填指标。
- Splatfacto 的 LPIPS 评估依赖 torchvision 的预训练 AlexNet 权重。这是感知指标的特征网络，不是预训练 3D 场景模型。
- PyTorch、torchvision、TorchMetrics 等保留各自上游许可证和来源。

## 课程作者与 AI 辅助的工作

本项目的环境准备、下载检查、划分清单、实验调度、指标汇总与分析需要单独记录。使用 AI 协助编写和排错，最终报告应披露其用途；课程作者应实际运行并理解实验。上游算法与实现按上述来源引用。

## 本仓库的公开范围

只发布实验脚本、配置、日志、数值、对比图及报告，不重新分发完整数据集、训练模型或上游源码。原始训练代码快照保存在 records 中，维护中的启动脚本已改为可配置路径。使用 OpenAI Codex 协助环境排错、脚本编写、结果整理和报告编辑。公开可见不代表上游材料的许可证发生变化。
