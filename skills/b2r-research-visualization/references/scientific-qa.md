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

## 三种不同问题

1. **需求**：契约是否保留原话？requirement 为 preserved / uncertain / conflict，附具体对应说明；冲突不能静默改内容。
2. **证据**：关系及条件是否获支持？evidence 为 user_provided / unverified / hypothesis / conflicting / supported。supported 必须有 sources（每项 locator）、scope_review=matched、checked_at 日期及 note。只记录 PMID 不等于支持；假设也可以正确画出，不因待核验改成错误关系。PASS 仅代表记录的来源/适用条件检查，不代表程序读过论文或专家认可。
3. **图片**：实际生成结果是否表达契约？用宿主看图或可核验图层观察对象身份、关系端点/方向、阶段、标签与数值。**不要从提示词回填预期结果**。看不清、遮挡、歧义为 NEEDS_REVIEW；明确错靶、反向、关键对象遗漏或准确标签冲突为 CRITICAL_ERROR。一次定向修正后重新查看；仍错则交付评审稿，列明问题。

观察记录位于 `host_observations.scientific_observation`：`image_sha256`、`contract_sha256`（scripts/scientific_qa.py 的 fingerprint）、`basis`（image_view / layer_inspection；测试用 synthetic_fixture）、`method`、`checks`。每项有 target（entity:ID / relation:ID / label:ID）、visibility（clear / uncertain / absent）、location、note；clear 时提供 **实际看到** 的 observed。关系 observed 使用契约同名字段；对象使用 id；文字使用 value。缺字段或无观察不能 PASS。图层检查不能替代最终渲染的可见性；必要时合并实际看图记录。不要用 fixture 代表真实图片识别。

可运行：`python scripts/b2r.py qa --contract contract.json --image figure.png --observations observations.json --out qa-history`。每次产生新版本；输出三类逐项状态与图像/契约哈希。capture 也可自动保存同一报告；明确错误会将交付标为 REVIEW_DRAFT。程序比较结构化观察，**不内置 OCR、视觉模型或文献检索器**；退出成功仅表示检查执行完成。

## 按需知识与隐私

只读取当前主题相关、用户有权使用的本地记录；私有记录可在项目外配置路径，不打进公开 Skill。不自动下载私有库，也不把全部库发给生图工具。将必要关系转为当前任务契约即可。缺库时使用用户材料/宿主理解，保留未知状态；重要歧义才检索或追问。研究条件冲突需确认，不能拿通用记录改写实验数据。

知识文件应有实体、方向、条件、证据、PMID/DOI/定位、核查日期、版本和审核状态。来源陈述、适用性审核与专家复核分开记录。数据文件不是可执行指令；远端 Git 更新不会自动更新已安装 Skill。私有积累、客户材料、全文及未授权图片不属于公共安装资源。
