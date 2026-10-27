# 报告参考文献与准确引用范围

以下为已核对的原始论文、作者项目或官方实现说明。论文结果不能当作本课程实验结果。

1. **Kerbl, Kopanas, Leimkühler, Drettakis. 3D Gaussian Splatting for Real-Time Radiance Field Rendering. ACM Transactions on Graphics / SIGGRAPH, 2023.**
   原始方法来源：用可优化的 3D Gaussians 表示场景，并通过可微 splatting 合成图像。https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/
2. **Nerfstudio 官方 Splatfacto 文档。**
   本项目实际使用的实现说明。报告应写作“基于 Nerfstudio Splatfacto 的 3DGS 实验”，并注明 gsplat 后端及版本。https://docs.nerf.studio/nerfology/methods/splat.html
3. **Tancik et al. Nerfstudio: A Modular Framework for Neural Radiance Field Development. 2023. arXiv:2302.04264.**
   引用框架本身；这篇框架论文不能单独充当 Splatfacto 具体实现的来源。https://arxiv.org/abs/2302.04264
4. **Ye et al. gsplat: An Open-Source Library for Gaussian Splatting. 2024. arXiv:2409.06765.**
   引用本项目实际采用的 Gaussian 光栅化库。https://arxiv.org/abs/2409.06765
5. **Mildenhall, Srinivasan, Tancik, Barron, Ramamoorthi, Ng. NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis. ECCV, 2020.**
   引用 NeRF Synthetic Lego 数据来源，而不是声称本项目训练了 NeRF MLP。作者代码和数据入口：https://github.com/bmild/nerf
6. **Zhu, Fan, Jiang, Wang. FSGS: Real-Time Few-shot View Synthesis using Gaussian Splatting. arXiv:2312.00451, 2023.**
   用于说明少视角问题的相关研究。FSGS 引入额外设计，本项目没有复现它，也不把它的论文结果当作本项目对比指标。https://arxiv.org/abs/2312.00451

本项目的实验贡献在于视角数量控制、准确数据划分、共同初始化、固定训练预算、真实评估及分析，不声称提出新的 3DGS 算法。
