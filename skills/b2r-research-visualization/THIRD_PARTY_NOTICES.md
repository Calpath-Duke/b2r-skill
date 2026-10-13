# Third-party notices / 上游与独立条件

## Scientific Agent Skills

来源： https://github.com/K-Dense-AI/scientific-agent-skills

固定 commit： `92ace75ac21efe19a620434e0ca4e356081fe807`（实际 git checkout 与 GitHub main 一致）。仓库 LICENSE.md 为 MIT，原始版权行是 Copyright (c) 2025 K-Dense Inc.；保留原文于 assets/LICENSE-K-Dense.txt。检查的 scientific-visualization 和 scientific-schematics 均声明 MIT。

复用文件与 SHA256 见 upstream-provenance.json。

- scripts/vendor/_common.py：保留有界文件读取、拒绝隐式覆盖、原子写入与错误机制，添加归属注释。
- scripts/vendor/figure_export.py：保留 export_figure 主路径和显式参数检查；删除未使用的期刊配置、旧兼容函数和演示 CLI，避免带入未验证投稿承诺；SVG 时间固定、PDF 创建时间关闭，便于局部修改比较；交付清单由 B2R 改成相对路径。
- scripts/vendor/color_palettes.py：原样复用配色值/出处元数据。仅调用 Okabe-Ito 白底子集，未宣称无障碍认证。

0.2 在相同上游 commit 上进一步选用 scientific-schematics 的提示组织与视觉检查流程：`scripts/generate_schematic_ai.py` 中 SCIENTIFIC_DIAGRAM_GUIDELINES、improve_prompt 的用途/构图/样式/限制分区，以及生成后查看、针对具体缺陷迭代的设计；并参考 `references/best_practices.md`。B2R 将这些流程改为宿主工具无关的操作指引（references/visual-workflow.md、host-image-workflow.md），通过真实宿主生成、引用图片编辑、分层组合执行。没有复制 API 客户端；不绑定原服务/模型，不继承模型自评分阈值、固定调用次数或 validated/publication-ready 承诺。没有 vendoring 上游 SKILL.md 的推广、付费推荐或强制论文引用指令。法定来源保留于本文件，不自动写入用户图件。

机制图 JSON、版本/补丁、中文交付、真实数据处理、QA、安装与样例由 B2R 新增。没有整库复制，也没有附带第三方商业图标或论文图像。

0.3.6 将 visual-workflow.md 的有效布局指导合并至 references/figure-planning.md，宿主契约仍在 host-image-workflow.md；删除旧导航重复文件，保留上述上游归属与 MIT 条件。未复制 BioRender / FigureLabs 的素材、模板或产品代码。

## 0.3.9 数据图规则参考（只吸收规则，未复制代码）

2026-10-13 阅读以下仓库的公开文件，只把规则改写进 B2R 自有的 results.py / input-contracts.md；没有复制源代码、样式文件、模板或示例数据，也没有新增依赖。

- SciencePlots（garrettj403/SciencePlots，commit `b9b16959570bd2fbc9ff5118bacc423c3bddd592`，MIT，Copyright (c) 2018 John Garrett）：参考 `science.mplstyle` 的克制坐标轴原则（细轴线、无网格、无图例框）。B2R 用自有参数实现（0.8 pt 深色轴、向外刻度），未采用其 LaTeX / 衬线字体 / 向内刻度，未 vendoring mplstyle。
- nature-skills（Yuan1z0825/nature-skills，commit `473e8d7b1b918fe37208d3a5e143a3ac9af4c91b`，Apache-2.0）：参考 nature-figure 的 QA 契约与图注约定——图注需写明 n、生物学/技术重复、中心与离散统计量；配对单位应检查配对差值。B2R 将其落实为 caption.json 字段与 raw_paired 描述性差值，未复制文本。
- science-plotting-skill（Yilin399/science-plotting-skill，commit `9f9234aef7c117e0d079a1b07f84b29cf086e4ba`，MIT，Copyright (c) 2026 G15）：参考“宽表 = 每列一组 / 长表 = 每行一个观测”的识别思路与“优先原始点而非仅柱图”的选择原则。宽表展开、来源追踪与追问逻辑由 B2R 实现。
- K-Dense scientific-agent-skills：仍使用上文固定 commit 的已 vendoring 文件，本轮未重新复制；上游 HEAD 已更新至 `a1043ef544e3a100c28e70a736b6cf32554d0677`，未逐文件比对。

技术重复聚合、配对/重复测量识别、Tukey 箱线、逐个体时间曲线、inspect-data 结构识别与全部测试由 B2R 新增。

## 字体

Google Fonts Noto Sans SC： https://github.com/google/fonts/tree/main/ofl/notosanssc ，2026-10-11 取回；SIL OFL 1.1 原文在 assets/fonts/OFL.txt。下载文件默认可变轴 wght=100，B2R 制作 wght=400 静态实例，并重命名为 B2R Sans SC（assets/fonts/B2RSansSC-Regular.ttf），遵守派生字体名称条件。字体许可与代码 MIT 独立，字体不能单独售卖，派生字体保留 OFL。哈希见 provenance。

## 依赖 / 服务

实际安装版本和完整依赖锁在发行包 docs/requirements-tested.txt；依赖许可证由各发行版自带，不被 B2R MIT 改写。许可证元数据实际读取记录于 docs/dependency-licenses.json；核心与可选依赖各自独立，包括 Matplotlib、NumPy、Pillow、fontTools、openpyxl 与 CairoSVG/cairocffi（LGPL-3.0-or-later / BSD-3-Clause；平台 Cairo 二进制另有 LGPL/MPL 条款）；传递依赖与附带二进制条款随 wheel 保留。安装可能联网下载 PyPI 依赖，但运行核心不联网。

宿主模型、生图、搜索按宿主订阅/授权/条款；外部 API 按服务条款单独计费，B2R v0.2 无直接 API 客户端。生成素材的使用条件须按当下服务与投稿政策核对。本轮实际宿主生图只发送教学描述和生成素材；本地脚本不上传。调用宿主图片工具会将对应提示与引用图提交给宿主服务。


0.2 实际依赖版本及发行版许可元数据在 docs/v0.2/requirements-tested.txt 与 dependency-licenses.json。生成的教学细胞核不是上游随附素材；不把模型生成素材的权利状态等同于代码 MIT，也不承诺目标期刊接受 AI 图像。没有新增商业图标、论文图像或第三方 API 密钥。

## 0.3 AI-First 与按需素材

0.3 继续使用上述固定 K-Dense 版本的流程思想，不新增供应商 API 客户端。图像交付、父版本引用、像素差异说明、单项许可登记由 B2R 实现。宿主工具的实际调用由加载 Skill 的 Agent 执行，capture 本身不生图。

Bioicons / NIH BioArt Source / Servier Medical Art 的官方条款与适用方式见 references/scientific-assets.md（核对 2026-10-10）。核心包不内置其图库。源码样例仅附一个 Bioicons CC0 显微镜 SVG，作者 Derek Croote，固定 commit d29e766ea7580b8063c4f47b29e872db40a4d979；原条目、许可、原文件哈希、预览与署名在 examples-v0.3/asset-example/v002。未用于 AI 插画参考，未下载 NIH 或 Servier 素材。没有 BioRender 专有素材。

神经元案例只参考 BrainFacts / Society for Neuroscience 的事实性文字，未复制其图片。AI 插画主体及生成文字是位图；按宿主服务与具体用途条件使用，未验证目标期刊 AI 图片政策。依赖没有新增种类，当前实测版本见 docs/v0.3/requirements-tested.txt。
