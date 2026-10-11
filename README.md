# Bench2Result · Free Scientific Visualization Skill

中文描述科研需求，B2R 帮你规划图件，调用当前 AI 宿主的工具完成绘图，并接续自然语言修改。默认英文标注、Classic / Refined 两种二维方案；可说“只画一张”。定量图使用真实表格与代码。

## 安装

**Codex**：将以下内容发给支持 Skills 的 Codex 客户端：

```text
$skill-installer 请从以下官方目录安装 Bench2Result（B2R）免费科研可视化 Skill：
https://github.com/Calpath-Duke/b2r-skill/tree/main/skills/b2r-research-visualization
请先检查来源与文件完整性。如果已有旧版，先确认并备份再升级，不直接覆盖。完成后告诉我安装位置、版本和调用方式。如果当前平台不能自动安装，请指导我本地导入。
```

无需访问私有仓库，也无需提供私人 GitHub Token。安装器若报告目录已存在，请让 AI 先将旧目录备份到技能扫描目录以外，再安装；失败时恢复备份。不同 Codex 版本的默认目录可能不同，以安装器实际报告为准。当前官方文档列出用户 `~/.agents/skills/` 和项目 `.agents/skills/`；安装脚本也支持显式 `--dest`。不要重复安装到多个扫描位置。

**本地 ZIP 导入**：从 [Releases](https://github.com/Calpath-Duke/b2r-skill/releases) 下载 `B2R-Skill-0.3.8.zip`，不要把 GitHub 自动生成的整个仓库 ZIP 当作单个 Skill 包。

| 客户端 | 最短路径 | 安装验证状态 |
|---|---|---|
| Codex | 上述完整 GitHub 目录交给 Skill Installer；或将 ZIP 内完整 `b2r-research-visualization` 目录安装至客户端识别的位置 | 以本次 Release 验证记录为准 |
| WorkBuddy | 技能管理 → 添加/上传技能 → 导入 ZIP 并启用。若客户端要求根级 SKILL.md，使用同版 `B2R-WorkBuddy-0.3.8-format-only.zip` | 格式包来自同一核心；桌面实际导入待验证 |
| 豆包工作 | 在支持自定义技能的工作入口打开“技能・连接器・伙伴”，选择本地导入；优先尝试标准 ZIP | 官方确认本地技能导入；具体 ZIP 层级及实机导入待验证。普通豆包聊天不等同于豆包工作 |

如果客户端不接受包，不要只上传 SKILL.md：需要一起保留 scripts、references、assets 和许可文件。记录客户端版本和导入报错，在 [Issues](https://github.com/Calpath-Duke/b2r-skill/issues) 反馈，不附 Token、患者资料或未授权研究文件。

## 确认安装与首次调用

在技能列表中寻找 `b2r-research-visualization` / Bench2Result。若未出现，重新加载或重启客户端。在 Codex CLI/IDE 用 `$b2r-research-visualization`，在支持技能选择的界面显式选中 B2R。

```text
请使用 B2R，先报告你读取的 Skill 版本和所在目录，并确认 references、scripts、assets 均完整；本次不生图。
```

首次绘图可说：“用 B2R 画抗体结合细胞表面受体的概念示意图，只画一张。未指定具体抗体或受体，不添加具体分子名称。”随后可说“只改标题”或“使用方案 B，颜色淡一些”。

安装成功与生图能力是两件事：图片生成取决于当前会话工具和权限；无生图工具时 B2R 会说明限制。AI 图片路径不要求预先安装 Python；数据绘图或本地组合脚本按需由 AI 在隔离环境安装 Skill 内 requirements 文件。

## 费用、科学核验与授权

B2R Skill 免费。宿主订阅、图像生成及额度受平台规则约束；双图通常需要两次渲染，可随时选择单图模式。无新增第三方收费 API。用户需核验科学关系和数据；B2R 不保证图件直接符合任何期刊要求。QA 的 PASS 仅代表具体检查项，不是专家认证。

公开分发仅包含可独立使用的免费运行核心。私有知识积累、内部验证作品及研发历史不在本仓库，也不是运行前提。不会自动下载或执行远程更新。升级从已验收 Release 获取。

沿用既有公开软件的 MIT 授权，不扩大未分发内容的许可。字体遵守 SIL OFL，第三方代码保留各自版权；具体见 [LICENSE](LICENSE)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。宿主生成图片和按需外部素材不因代码 MIT 自动获得同样授权。

官方依据（核对 2026-10-11）：[Codex Skills](https://learn.chatgpt.com/docs/build-skills)、[OpenAI Skill Installer](https://github.com/openai/skills/tree/main/skills/.system/skill-installer)、[WorkBuddy 技能](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)、[豆包工作官方说明](https://www.feishu.cn/content/article/7677519271848610746)。
