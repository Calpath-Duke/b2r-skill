# 同一 Brief，按宿主工具渲染

需要工具映射、版本收录或无工具交接时读取。普通已知工具可直接执行 SKILL.md；不为每次绘图先诊断 Python 或生成能力报告。

## 统一生成要求

由当前宿主在一次理解/规划中将原话组织成简洁请求：
**科研内容与关系 → 关键区室/步骤与阅读顺序 → 风格 → 准确标签及保护内容。**

先确定共享科学内容及英文标签（用户指定语言优先）。请求顺序：标题/用途 → 风格段 → 版式结构与区域位置 → 关键交互（抑制、中和、裂解、带位点结合）→ 其余关系（线性关系合并为链，多源汇聚写成一句）→ 对象表现 → 准确标签 → 排除项。风格段用具体约束而不是形容词：Classic 写白底、统一描边、单色平涂、无渐变/高光/纹理/投影；Refined 写形内柔和明暗、膜细节、淡色语境背景、仍无高光球与三维渲染。A/B 的其余正文逐字相同。避免“polished / not a flowchart / medical detail”这类会把 Classic 推向精美插画的措辞。用户指定单图/风格时只组织对应请求。保留机制与术语，不因宿主不同而改内容；不要求固定字数、完整 JSON 或新模型调用。

有 Python 时可由 `b2r.py render-plan --contract contract.json --plan layout-plan.json [--ledger ledger.json] --out 任务/请求` 编译：输出 request-classic2d.txt、request-refined2d.txt、render-plan.json（含 qa_checklist、未放置实体告警、被 CONFLICTED 挡下的关系）。它只组织宿主已规划的内容，不理解科学、不调用模型。

## 依据真实能力调用

查看实际工具契约，不假定支持一次返回两张。默认双图用两次独立调用，共用同一请求正文；引用 A 编辑得到 B 只在当前宿主实测能真正换风格时使用，且须核对内容漂移和文字。分别保存完整分辨率文件；失败/额度限制仅交付实际完成项，第二方案生成不是质量重试。额外修正仅针对具体错误或用户反馈。未暴露的模型/种子/费用写未知。

| 观察到的能力 | 执行 |
|---|---|
| 可生成 | 直接调用并取得真实图片；提示文件不能代替成图 |
| 支持参考图/局部编辑 | 先看当前图，再按真实路径/附件契约引用；没有 mask/锁定就不承诺局部像素不变 |
| 有独立对象/文字/箭头处理 | 复用 artwork/edit 或任务专用 SVG，把精确信息放在可修改层 |
| 只有整图位图 | 短标签可随图；查错后优先能可靠修正的覆盖层或图片编辑，不能把原错字留在底层当已修好 |
| 无可调用生图 | 说明限制；可交付清楚标识的结构稿或设计交接，不能称 AI 插画成功 |

看图发现端点错接、T 形端方向反、药物标记离开目标或标签错位时，优先用 artwork 以原图为 image 底层，叠加遮盖块、矢量 T 形端/箭头（可连接不可见的目标区域）与独立文字，再看合成结果；被遮盖处的轮廓/分隔线需一并补画。位图引用编辑适合形态、配色、整体风格，不适合移动对象或改单个标签：实测中它未移动目标对象，且把改名写到了相邻对象上。

文字易错或编号/箭头容易错位时，不降低模型评级：短标签、预留标签净空，必要时生成主体后加独立层；数字/统计从真实表格程序化绘制。只改少量文字优先编辑源层，复用 [artwork-and-edits.md](artwork-and-edits.md)。同图统一图例编码，编号按实际步骤；核对箭头端点与标签归属。对未知宿主先用当前任务验证，不增加多轮探针或强制测试图。

## 少量宿主说明

- **当前 Work Mode/Codex 实测路径**：工具名 image_gen.imagegen 只是此宿主示例。新图传 prompt；本地引用编辑先查看，再传 referenced_image_paths；没有本地路径时按会话图契约引用。返回中的实际路径/附件用于后续文件接续，不猜文件名。宿主额度不等于额外 API 额度。
- **Cursor GenerateImage 实测（2026-10-13）**：抗体 Y 形朝向是最顽固的错误。旧 ADC 图与本轮两次重新生成中，ADC 和抗 PD-1 都画成正立 Y、Fc 杆朝向靶点，即使请求写明 Fab 端朝靶点、必要时倒置 Y。按修改请求进行的位图编辑会重绘整图（约 10% 像素在编辑区外显著变化），并可能删掉未要求修改的对象。抗体朝向、T 形端方向这类问题优先用矢量覆盖修正。
- **Cursor GenerateImage 实测路径（2026-10-12）**：新图传 description 与 aspect_ratio；参考图用 reference_image_paths 传本地绝对路径；返回 JPG 路径用于后续接续。后端模型未暴露。在该宿主上，参考图（代码骨架或已核对的 A）都不能可靠地“保留拓扑同时换风格”。
- **WorkBuddy / Hy4 Preview / Kimi K3 / 豆包工作**：用户报告的历史测试与本轮 trace 分开。核对当前工具是否能分别生成、接受参考图或处理图层；同名工具不代表同一后端。缺少当前记录时保留未验证，不按语言模型名称猜能力或增加专属 Skill 副本。
- **设计创意模式**：分别记录“该模式自己生成”“B2R 已读取并参与本次生成”“B2R 仅提供交接要求”。最后一种可保存 design-handoff.md，含原话、简短 Brief、逐字标签、已授权参考图/父版本、期望文件与保护内容；状态为 HANDOFF_READY。取得真实图后才能转回查看/交付。当前会话无调用工具时不宣称 Ardot 集成，也不探测未授权内部接口。

对照时固定原始需求、用途、语言、比例/风格及可确认的渲染设置。记录实际工具请求和调用数；有后端标识才确认是否相同。将语言模型的规划完整性与图像后端的渲染差异分开描述，不以一次漂亮结果证明普遍质量或效率优势。

## 实际文件与版本

保留原始图，查看并交付 PNG/所需格式。没有 Python 也可用宿主附件及简短制作记录。文件能力不足时说明不能生成离线包。第三方图像发送须符合既有授权，来源/许可随任务保存；不记录密钥或带签名临时 URL。

双图用清楚的 A/Classic、B/Refined 顺序与文件映射，记录各自状态、共享 Brief 和实际请求。文件可命名 figure_v001_classic2d.png / figure_v001_refined2d.png；使用 capture 时按 classic2d/v001、refined2d/v001 分支目录，不把 B 当成替代 A 的第二版。用户选择后只在所选分支保存 v002；调用父图必须是该分支实际成功的文件。跨风格组合记录布局参考与材质参考，仍只交付用户要求的修改版。无需新增项目系统。

需要标准版本目录时使用现有 capture（只收录，**不调用模型**）：

```sh
python "<SKILL_DIR>/scripts/b2r.py" capture --image "实际返回.png" --record "record.json" --out "交付/图件"
# 修改时再加 --parent "上一次成功返回的目录/figure.png"
```

record 必需 brief（原话）、prompt（实际请求）、tool、model（未知可写未暴露）、status:succeeded、output_reference；可选 visual_review、scientific_questions、evidence、asset_credits、limitations、usage、references。编辑再写 requested_change、change_origin:user_feedback/visual_qa，可加 expected_regions（0—1 矩形列表）。不要伪造用户反馈。

非标准元数据放 host_observations，额外局部核对用 targeted_edit_review。失败可能占用版本号，parent 使用真实成功路径。capture 保留原图、PNG、静态位图 PDF、来源/版本与像素差异线索；像素差不是科学结论。总体 GENERATED_REVIEW_PENDING 与专家 PENDING 不因看图自动升级。

可选 `host_observations.figure_option` 为 classic2d 或 refined2d，配合完全相同的 figure_brief 收录；source/manifest 保存方案名和科学规划哈希，便于追踪选图。哈希仅证明记录相同，不证明两张图片内容相同。无此元数据的旧调用记录继续兼容。

## 可选 Brief / 质量记录契约

仅在需要审查/脚本收录时使用；普通任务可以不生成。相同 `host_observations.figure_brief` 支持简短非空文本或旧结构化对象；文本保存为 figure-brief.md，结构化保存为 figure-brief.json，不维护两套业务逻辑。

旧对象：original_request/topic/purpose；entities 每项 id/label/kind/status/source/visual；relations 每项 id/subject/object/type/status/source；stages/outcomes/labels/protected_values/unknowns/locks 字符串列表；composition 含 layout/reading_order/regions；style 含 name/reason，name 可为用户指定风格。source 为文本或含 excerpt/citation/locator 的对象，可保留 verified 布尔值。
- relation type：composition/binding/activation/inhibition/transport/conversion/release/causation/association。
- status：user_provided/source_statement/user_hypothesis/author_hypothesis/ai_inference/visual_simplification。视觉简化不能支持新增方向性机制。
- source 的核验状态与事实/假设性质分别保存。

可选 host_observations.quality_gate：image_sha256（实际查看原图哈希）、method、checks，每项 target/status/observation。status 为 observed/issue/not_verified。文本 Brief 的目标为 content/relations/labels/values/order/identity/style/layout/file；结构化目标为 entity:<id>、relation:<id>、label:<从0开始序号>、value:<序号> 及 order/identity/style/layout/file。只记录实际所见，额外修改检查不要自造 edit:* 目标。

capture 检查来源记录结构、目标覆盖和文件哈希，不读图，也不能证明宿主看过或生物学正确。缺记录 PENDING，缺项 INCOMPLETE，问题 HAS_FINDINGS；全部记录 HOST_REVIEW_RECORDED 仍不是专家通过。该契约兼容旧版本，不强迫轻量任务进入完整台账。

PNG 输入按实际解码格式保留原字节（含元数据），使观察哈希与交付 figure.png 一致。其他格式转为 PNG 时，source.json / scientific-qa.json 的 image_delivery 记录原文件、最终文件、两者哈希及转换方式；原 QA 仍绑定实际观察的输入文件，final_png_review 为 NEEDS_REVIEW。重新查看最终 PNG 并提交新观察后才能核对该文件；不替换旧观察哈希来继承 PASS。SAME_ARTIFACT_AS_SOURCE 只表示文件相同，不表示原图已通过检查。

复杂机制可在已有 host_observations 中加 figure_contract / scientific_observation，收录时保存三维 QA；字段与状态见 [scientific-qa.md](scientific-qa.md)。仅有正确请求或共同 Brief 哈希不能证明两张图片科学正确。修改必须重新查看并绑定新图哈希。

复杂机制有外部核验时，将同一 `evidence_ledger` 放入现有 capture record 的 `host_observations`，与 `figure_contract` 和每张图各自的 `scientific_observation` 一起收录。capture 保存独立台账与 Evidence QA，不执行额外搜索。台账格式见 [evidence-verification.md](evidence-verification.md)；普通任务无需这些文件。
# 文件结构与可审计性

`capture` 的 qa.json 在 file_checks 中分列实际 PNG 解码和位图 PDF 导出属性，并将内部文字排版、内部几何审计明确标为 `NOT_AUDITABLE`。文件成功、可解码或 PDF 头尾完整不表示文字、编辑性或科学内容通过；已有宿主查看记录与 Scientific QA disposition 仍单独保留。

程序化图件的 file_checks 按实际 SVG 结构记录 text/vector/image 元素；嵌入位图仅能部分审计独立矢量层，不声称整图可编辑。原生 SVG 中无 text 元素时不声称文字独立可编辑；外部或无法识别的 image 资源保持未分类。任意 PDF 仅做头尾检查时不推断内部是矢量；capture 的 Raster-only PDF 分类来自已知位图导出过程及实际图像 XObject。所有文件属性是能力与结构说明，不是新的 QA PASS。
