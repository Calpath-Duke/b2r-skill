# 结构草图与结果图契约（0.2 保留）

JSON 均 UTF-8，示例位于 assets/examples/。坐标/数值必须有限；未知字段拒绝，避免拼写错误被静默忽略。输入表不自动排除异常值、不补缺失、不替换真实结果。

宿主在未指定图件语言时准备英文标签并设置 language:en；用户指定语言/逐字内容优先。脚本不会翻译或改写原表。统计图默认单次数据绘图，不套用插画双方案。

## 机制图

必需 kind:schematic、title、purpose、language:zh/en/bilingual、nodes；其他可选 canvas、panels、edges、sources、notes。language 是图内意图，脚本不会翻译标签，宿主须生成一致实际文本。

canvas: width/height 是布局坐标（默认 1200×700），width_mm/height_mm 是物理输出（默认 240×140 mm），两者应同比例。最多 30 节点、60 关系、10 分区。标题占顶端 95 坐标单位，图例占底端 85；节点不能越界/互相重叠。复杂网络先规划分面或重构，不自动挤压。

节点：id,label,x,y,evidence 必需；x/y 为中心。w/h 默认 190/90。可选 subtitle,color,shape:box/ellipse/chain,chain_length:2..30,sources:[S1]。chain 是装饰性示意链，不表示真实原子连接、序列或分子结构，不可冒充化学结构。

关系：id,from,to,relation,evidence 必需。relation 为 activation（箭头）、inhibition（抑制横杠）、association（无方向）、flow（流程箭头）。可选 label、color、label_x/y、via（最多 8 个折点 [x,y]）、sources。自动连到节点边缘；边交叉、穿过第三节点、标签对应须查看实际输出。调整折点不自动增加科学关系。

分区：id,label,x,y,w,h 必需，x/y 是左上角，可选 color；只是布局分区。

证据枚举：user_confirmed / user_hypothesis / source_explicit / author_hypothesis / ai_inference / visual_simplification。user_hypothesis、author_hypothesis 与 ai_inference 为虚线/问号。source_explicit 与 author_hypothesis 必须关联来源。来源必需 id,citation,locator,excerpt,verified。verified 仅表示宿主核对定位/摘录，不决定是否画假设箭头，不表示脚本科学验证。作者假设即使有来源也不是实证。专业空间示意与素材组合使用 artwork-and-edits.md 中的分层路径，允许有语义的包含/膜相交。

## 结果图

必需 kind:results,title,purpose,language,mode,columns,unit；无量纲写 dimensionless。可选 xlabel/ylabel、group_order、missing_values、transform、error_definition、replication_unit、independence_confirmed、width_mm/height_mm、colors、notes、layout、design、technical_replicates、sheet。language 不翻译分组原值；双语映射由宿主维护，原表不改。

用户上传表格后，宿主先运行 `b2r.py inspect-data --data 表格 [--sheet 名称] --spec-out draft.json`：只读识别长表/宽表、分组/数值/ID/时间/技术重复列、单位、跨组共用 ID，给出建议 mode 和至多 3 个必须确认的问题（技术重复？配对？独立单位？单位？）。宿主用自然语言问用户，按回答补全 spec，再运行 results；用户不手写 JSON。建议只是起点，结构确认权在用户。

| mode | 含义 | 条件 |
|---|---|---|
| raw_points | 逐行观测，不聚合、不画误差 | group/value，可选 sample_id |
| raw_mean_sd | 原始点 + 均值 ± 样本 SD | sample_id、重复单位、独立性确认；SD ddof=1 |
| raw_mean_sem | 原始点 + 均值 ± SEM | 同上，SEM=SD/√n |
| raw_box | Tukey 箱线图 + 全部点 | 同上；每组 ≥5 个单位；中位数、线性插值四分位、1.5×IQR 内最远值为须；不另画离群符号 |
| raw_paired | 同一单位跨条件连线 + 各条件均值横线 | sample_id（宽表可按行）、配对单位、独立性确认；≥2 条件、≥2 完整配对 |
| raw_timecourse_sd/sem | 逐个体细线 + 每个 x 跨单位的均值 ± SD/SEM | x、sample_id、单位确认；每个单位只属于一组 |
| summary_point | 用户已有每组估计 | 每组一行；可选已有误差 |
| summary_bar | 已有每组估计，零基线 | 每组一行；可选已有误差 |
| line | 已有数值 x/value 序列 | 每组每 x 一行；明确缺失行保持断点 |

**宽表**（layout: wide，GraphPad 式“每列一组”）：`columns.groups` 列出作为组的列名，可选 `sample_id`。仅原始模式可用。空白格视为列长不等的填充并计数跳过；显式 NA 记为缺失。无 sample_id 时每格视为不同单位；raw_paired 宽表无 sample_id 时同一行即同一单位。plot-data.csv 保留 source_row 与 source_column。

**技术重复**（technical_replicates: mean）：同组同一 sample_id（时间曲线为同一 x）的多行先逐值变换，再取均值作为一个生物学单位；n 按单位计，技术值以空心小点显示。units.csv 记录每单位 technical_n、缺失数与来源格。未设置时重复行仍被拒绝。

**设计**（design）：同一 sample_id 出现在多个组时，均值/箱线图返回 NEEDS_INPUT，询问是否配对；确认只是编号重名后设置 design: independent。配对差值（条件 − 首个条件，只用完整配对）写入 caption/summary，仅描述性。时间曲线拒绝跨组共用单位（交叉设计本版不支持）。

columns 映射真实列名，group/value 必需；可选 sample_id、x、error、lower、upper、n。error 是对称非负长度；lower/upper 是包含估计的端点，同时提供，不能与 error 混用。已有误差需要 error_definition、n 列、replication_unit；缺失返回 NEEDS_INPUT。无法提供时可讨论移除误差映射，只画已有估计并明确限制。绘制已有结果不声称完成方法验证。

raw 模式不接收 error/n（x 仅时间曲线）；SD/SEM 仅对每组非缺失、已确认独立单位计算。不执行任何统计检验，不生成 p 值或显著性标记；用户要求检验时，须先确认检验方法、配对/重复结构与多重比较，本工具只绘制用户已有的检验结果文本。脚本不能识别所有设计问题（嵌套、批次、区组需人工说明）。

transform 仅 none/log2，log2 不加伪计数，遇零/负值拒绝。原始汇总先逐值 log2，再计算均值/SD/SEM。已有误差不自动变换，需提交同尺度估计和区间。plot-data.csv 保留 input_value 与 plot_value。

默认 missing_values 为空串、NA、N/A；0 是真实值。CSV/TSV UTF-8（可带 BOM），标题不得空/重复，最多 20 MB、20000 行、100 列；每图 1—8 组。XLSX 多工作表时需用 sheet 指定（报错会列出表名），只读取缓存值、不计算公式；末尾空行/空列忽略；无缓存公式为缺失，先在表格软件重算。脚本不解释百分号、千分位、合并单元格或特殊小数格式。

group_order 恰好包含所有真实组；#RRGGBB 颜色至少覆盖组数。用形状/线型/纹理冗余。长标签若 QA 报错，修改换行、尺寸或布局，不静默截断。标题、单位、分组和专业标识须人工核对。

## 局部修改

```json
{"reason":"只修改标签", "changes":[
  {"target":"node","id":"kinase","set":{"label":"Kinase A (active)"}}
]}
```

机制图 node 可改 label/subtitle/color/x/y/w/h/chain_length；edge 可改 label/color/label_x/label_y/via；panel 可改 label/color/x/y/w/h；figure 可改 title。单次 1—30 项。关系/来源/实体增删需核对科学内容后建立新源版本。

结果图 figure 可改 title/xlabel/ylabel/colors/width_mm/height_mm，须显式提供原 input 表。分组/误差/数据/变换变化是新任务，保留新材料与制作记录。

## 交付与状态

每次新建 v001/v002…；index.html 是离线预览入口，SVG/PNG/PDF 是实际图件；source.json 是制作源。evidence.json（机制）或 caption.json、plot-data.csv（逐格来源）、units.csv（统计单位）、summary.csv（结果）记录来源/计算/限制；caption.json 含 center、spread、n_definition、各组 n、技术重复规则、宽表映射与配对差值，可直接写图注。reproduce.py 使用随附核心/字体，不在线拉代码。依赖在 reproduce/requirements.txt。

qa.json 是筛查，视觉/科学复核默认 PENDING。不能从退出码/状态推导科学正确性、投稿符合性或宿主在线通过。
