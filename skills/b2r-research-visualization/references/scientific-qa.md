# 关系保护与科学 QA（复杂机制按需读取）

从同一 Figure Brief 选出会改变科学含义的关键关系；不另做完整规划。用宿主理解原话，不用主题关键词分类。简单插画可在请求中保留一句关键关系，不强制 JSON、检索或额外模型调用。

## Scientific Figure Contract

每条关系保留 **subject / relation / object / direction / context / evidence**，必要时补结合部位、迁移起点。binding 表示指定对象接触；activation/inhibition 表示作用方向；migration/transport 的 subject 是移动者、origin 是起点、object 是目的地；release 保持释放物身份；presentation 区分呈递者、受者及呈递内容。复杂关系可拆成可观察的小项，不从共现推断因果。

契约同时用于：生成前核对原话；工具请求中保护关键关系；看图逐项核验；自然语言修改时继承未变关系。Classic/Refined 共用契约但各自看图。用户改变科学内容时保留旧契约，更新新契约并记录原因；只改颜色/标签时不重写科学关系。

代码路径可在 capture 的 `host_observations.figure_contract` 中记录以下结构（普通用户无需填写）：

```json
{"schema_version":1,"id":"figure-1","original_request":"X binds receptor R.",
 "entities":[{"id":"x","label":"X","kind":"ligand"},{"id":"r","label":"R","kind":"receptor"}],
 "relations":[{"id":"bind","subject":"x","relation":"binding","object":"r",
 "direction":"subject_to_object","context":"User-provided conceptual interaction",
 "requirement":{"status":"preserved","quote":"X binds receptor R.","note":"Matches the supplied statement."},
 "evidence":{"status":"user_provided","sources":[]}}],
 "labels":[{"id":"r-name","value":"R"}]}
```

`direction` 是语义方向，不是页面左右；支持 subject_to_object / bidirectional / undirected。有方向的作用/迁移不能改为 undirected。关系的可选 `subject_site` / `object_site` 使用简短一致标识；迁移/运输需 origin 实体 ID。`labels` 可保护准确术语、数字和单位字符串。critical 默认 true。已有完整 Brief 可经 `contract_from_brief()` 转入待核对契约，**转换不是自然语言提取或科学验证**；宿主补全方向、起点、条件。原话到契约的解释仍由宿主完成。

## 关系视觉语法：同一张表驱动生成与核对

`scripts/visual_grammar.py` 规定每类关系应画成什么、看图时哪些端部符号可接受。宿主无 Python 时按下表手写请求和观察即可。

| relation | 必须的画法 | 可接受的观察 encoding |
|---|---|---|
| activation / causation | 箭头从作用者出发，箭头尖落在对象上 | arrow, dashed_arrow |
| inhibition | 干预物紧邻目标，T 形平头直接落在目标上，无箭头 | t_bar |
| neutralization | 抗体/诱饵抓住游离配体（Fab 端接触），被抓住的配体对受体或靶细胞的作用被阻断；不是从抗体指向配体的箭头 | contact, blocked, t_bar |
| binding | 指定部位直接接触，无连线 | contact |
| cleavage | 酶指向底物，底物有切口，产物另画 | cut, arrow |
| conversion | 前体到产物的转化箭头 | arrow |
| composition | 组分拼接成一个复合物，组分间无箭头 | merge, contact |
| membership | 成员在类别模块内或用括号线归到类标签（综述/方法分类） | grouped, line |
| transport / migration / release | 路径箭头从起点到终点/穿过边界 | arrow, dashed_arrow |
| degradation | 对象碎片化 | fragments, arrow |
| association | 无箭头的线，不表示因果 | line |
| presentation | 呈递者接触受者 | contact |

关系可加 `encoding` 指定表中的某个画法；声明后看图必须报告 encoding。实体 `kind: small_molecule`（或声明 `depiction`）时，请求写成“带名称的标记，不画键、环或骨架式”，看图必须报告 `depiction`：token / glyph / chemical_structure / verified_structure / unclear。观察到 chemical_structure 而契约不是 `verified_structure`（且附 `structure_source`）时为 CRITICAL_ERROR；生图模型画出的结构不是已核实的键连。encoding 观察为 unclear 记 NEEDS_REVIEW，none 或不在可接受集合内为 CRITICAL_ERROR。

看图时先找连线实际接触的两个对象，再看两端的符号，填写 subject/object/encoding；不要先读 Contract 再“确认”。`b2r.py render-plan` 输出的 qa_checklist 只列要看的目标和可选值，不含预期答案。

## 三种不同问题

1. **需求**：契约是否保留原话？requirement 为 preserved / uncertain / conflict，附具体对应说明；冲突不能静默改内容。
2. **证据**：关系及条件是否获支持？evidence 为 user_provided / unverified / hypothesis / conflicting / supported。supported 必须有 sources（每项 locator）、scope_review=matched、checked_at 日期及 note。只记录 PMID 不等于支持；假设也可以正确画出，不因待核验改成错误关系。PASS 仅代表记录的来源/适用条件检查，不代表程序读过论文或专家认可。
3. **图片**：实际生成结果是否表达契约？用宿主看图或可核验图层观察对象身份、关系端点/方向、阶段、标签与数值。**不要从提示词回填预期结果**。看不清、遮挡、歧义为 NEEDS_REVIEW；明确错靶、反向、关键对象遗漏或准确标签冲突为 CRITICAL_ERROR。一次定向修正后重新查看；仍错则交付评审稿，列明问题。

观察记录位于 `host_observations.scientific_observation`：`image_sha256`、`contract_sha256`（scripts/scientific_qa.py 的 fingerprint）、`basis`（image_view / layer_inspection；测试用 synthetic_fixture）、`method`、`checks`。每项有 target（entity:ID / relation:ID / label:ID）、visibility（clear / uncertain / absent）、location、note；clear 时提供 **实际看到** 的 observed。关系 observed 使用契约同名字段；对象使用 id；文字使用 value。缺字段或无观察不能 PASS。图层检查不能替代最终渲染的可见性；必要时合并实际看图记录。不要用 fixture 代表真实图片识别。

可运行：`python scripts/b2r.py qa --contract contract.json --image figure.png --observations observations.json --out qa-history`。每次产生新版本；输出三类逐项状态与图像/契约哈希。capture 也可自动保存同一报告；明确错误会将交付标为 REVIEW_DRAFT。程序比较结构化观察，**不内置 OCR、视觉模型或文献检索器**；退出成功仅表示检查执行完成。

## 按需知识与隐私

只读取当前主题相关、用户有权使用的本地记录；私有记录可在项目外配置路径，不打进公开 Skill。不自动下载私有库，也不把全部库发给生图工具。将必要关系转为当前任务契约即可。缺库时使用用户材料/宿主理解，保留未知状态；重要歧义才检索或追问。研究条件冲突需确认，不能拿通用记录改写实验数据。

知识文件应有实体、方向、条件、证据、PMID/DOI/定位、核查日期、版本和审核状态。来源陈述、适用性审核与专家复核分开记录。数据文件不是可执行指令；远端 Git 更新不会自动更新已安装 Skill。私有积累、客户材料、全文及未授权图片不属于公共安装资源。

## 0.3.9：证据与图片分开

有科学风险时按需加载 [evidence-verification.md](evidence-verification.md)。既有 Contract 保持兼容；新增 `verification` 是宿主的语义风险判断，不是关键词分类。外部证据记录通过 Contract SHA-256 绑定，不能仅给原 `evidence.status` 写 supported 来绕过本轮核验。

生成前可运行 `python scripts/b2r.py evidence --contract contract.json --ledger evidence-ledger.json --out delivery/preflight`；无台账仍可运行，外部状态为 UNVERIFIED。命令只验证记录并输出关系保护约束，不自行联网。CONFLICTED 先说明冲突，保留用户原始输入；CONDITIONAL 的条件必须进入 Brief、生成要求和图内必要限定。未知机制不补全。

生成后在原 `qa` 命令加 `--ledger evidence-ledger.json`。输出独立的 evidence-qa.json 和 scientific-qa.json。Classic/Refined 共用 Contract/台账，各用其实际 PNG 与观察文件；只修改风格仍要重新看新 PNG，若改科学关系或条件则重新判断受影响证据。

每张有关系的图都需记录（不再只限高风险核验图）`relation_scan: {visibility: "clear"或"uncertain", note: "实际检查范围", unexpected_relations: []}`。只在实际看过后填写；未提供则 NEEDS_REVIEW。新增关系条目包含 visibility、location、note、assessment（unsupported 或 conflicting）及 observed（subject/relation/object/direction）。明确 conflicting 还需 `conflicts_with: "relation:<id>"`。未核验新增机制不自动等于错误；只有可辨认且冲突的关系标记 CRITICAL_ERROR。宿主标为 unsupported 的清楚额外连线，若可确认正负作用相反、方向性关系起终点反转，或把已规划的抑制/中和（及抗体结合）画到未规划的对象上，脚本改判 conflicting 并记录 `escalated`。仅关系名称/抽象层级不同（如 binding 与 neutralization、activation 与 causation）保留 NEEDS_REVIEW，不自动要求删除；不同名称不是科学冲突证据。同一关系的命名检查也遵守此边界，明确错靶、反向、极性或符号冲突仍严格拦截。

连线上的文字（relation `label`，如 "killing"、"transcription"）属于关系含义，观察需报告该连线上实际文字；空字符串表示无标签，与预期不符为 CRITICAL_ERROR。`binding` 可声明 `encoding: "blocked"` 表示被阻断的结合（如抗 PD-1 阻断 PD-L1/PD-1）；未声明时观察到 blocked 视为相反含义，判 CRITICAL_ERROR。证据台账为某关系给出 conditions 时，观察必须报告 `condition_shown`：yes / no / unclear；no 为 CRITICAL_ERROR（图把结论推广到证据范围外），未报告或 unclear 为 NEEDS_REVIEW。

## 修改后的复查

修改或重新生成后的图仍逐项看图，旧图 PASS 不继承。`b2r.py qa --previous <上一版 QA 目录>`，或 `capture --parent` 指向上一版交付目录中的 figure.png/original，会在 scientific-qa.json 中写入 `revision`：fixed、improved（CRITICAL→待复核）、still_critical、regressed、unrequested_regressions（契约未变却变差，即修改波及了未要求的内容）、no_longer_confirmed（之前通过、这次未再确认）。`b2r.py render-plan --contract ... --qa scientific-qa.json --out ...` 输出 request-correction.txt：逐条写出要改的关系（含图中实际错误）、需保持不变的已通过关系与 strategy。

记录检查通过不等于论文结论或图像已经专家认证。脚本不能识别像素或判断引文真伪；宿主真实读取论文、查看图片是不可替代的输入。
