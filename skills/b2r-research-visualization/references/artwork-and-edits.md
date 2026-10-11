# 分层组合与自然语言修改

这是宿主制作选项，不是科研插画的能力上限。宿主也可写任务专属 SVG/绘图脚本。

## Artwork

`kind:artwork`，title,purpose,language,canvas,objects 必需；sources,notes,materials,calls 可选。
canvas 为 width,height（布局坐标）、width_mm,height_mm（物理尺寸）。对象中心为 x,y，w,h 为范围；z 控制前后关系。

对象稳定 id、type、role、可选 aliases 帮助把自然语言映射到实际层。类型包括 region,ellipse,text,membrane,receptor,protein,chain,image,arrow,line；支持 fill/stroke、line_width、opacity。text 使用 text,font_size,align。image 使用任务内相对 asset 路径，保留透明度。chain_length 只控制示意链，不表示真实化学结构。

arrow 的 from/to 引用形状对象，端点随对象位置计算；relation/evidence/sources 与结构图一致。via 可指定折点。不能用装饰型线条伪装未支持的科学关系。

允许图形包含/叠放。attachment:{target:膜ID,mode:on_membrane} 校验受体与膜相交；inside 校验对象位于指定区域的矩形边界。它们不是精确生物几何验证。无语义约束的重叠仍需视觉检查。

```sh
python "<SKILL_DIR>/scripts/b2r.py" artwork --spec "任务/scene.json" --assets "任务" --out "交付/机制图"
python "<SKILL_DIR>/scripts/b2r.py" inspect --source "交付/机制图/v001/source.json"
```

## 自然语言 → 对象 → 实际修改

宿主读取对象地图和当前图，选择正确角色：受体图形 receptor 与 receptor-label 是不同对象。不要把用户模糊反馈简单作字符串替换。

若已有 Classic/Refined 两方案，先按交付映射识别“第一张/第二张/B”，读取选中版本的源文件或图片，并沿用共享科学内容；只在其分支保存新版本，未选方案保持。版本指代不明时才问一句，不重新要求用户提交原始需求。

例如用户说“R1 改成 R1 receptor；细胞核改为紫色”：修改 text 对象；若细胞核是 bitmap，实际调用宿主编辑该素材，保存新 PNG，再修改 image 对象的 asset。下面补丁由宿主生成，不要求用户填写：

```json
{"reason":"用户自然语言反馈原文", "changes":[
 {"target":"object","id":"receptor-label","set":{"text":"R1 receptor"}},
 {"target":"object","id":"nucleus","set":{"asset":"assets/nucleus-v2.png"}}
]}
```

```sh
python "<SKILL_DIR>/scripts/b2r.py" edit --source "交付/机制图/v001/source.json" --patch "任务/edit.json" --assets "任务" --record "任务/真实编辑调用.json" --out "交付/机制图"
```

只有图片编辑时需要 --record。没有换素材时 --assets 可省略，默认源版本目录。
支持视觉属性 x,y,w,h,z,fill,stroke,line_width,text,font_size,align,asset,points,via,chain_length,opacity；不允许用视觉补丁改科学关系。对结果图/旧结构图继续使用原 input-contracts 契约。

检查 changes 与源差异，实际打开两版。对未改对象检查 SVG，或比较允许区域外的像素；移动对象时预期包含跟随它的箭头。保证“其他层未变”必须有证据，不能仅凭 ID。

## 组合图版

安装可选 requirements-compose.txt。`kind:assembly`，title,canvas,panels；可选 footer。每个 panel 包含 id,title,source（已有交付目录相对路径）,x,y,w,h。面板提供 figure.svg 与 figure-outlined.svg，组合后仍是嵌套矢量对象；其中 bitmap 仍是 bitmap。

```sh
python "<SKILL_DIR>/scripts/b2r.py" assemble --spec "任务/assembly.json" --assets "任务" --out "交付/图形摘要"
```

数据面板先用真实表格绘制，再组合。面板制作源和数据随目录复制。组合预览从 outlined SVG 生成，避免系统字体替换；可编辑 SVG 保留文字，需安装随附字体。
