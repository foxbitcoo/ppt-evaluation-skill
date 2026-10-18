# PPT评测

按最终页面效果评测PPT，输出**页内细节、单页表达、整稿**三个视角的分数、问题位置、修改建议和HTML/JSON报告。

当前版本 **0.2.3-research**。量表未经人工标定，观察分与覆盖率一起展示，正式总分不默认合并；阅读版提供等权综合观察试算，不用于无人复核的产品排行榜。

## 评测流程

![PPT评测：按页看图、逐项校验、统一复核与报告](assets/evaluation-architecture.png)

N页默认进行N次主要单页视觉请求，另1次整稿检查与问题复核。原生对象只作可选辅助，不逐对象调用模型，也不要求模型复述制作零件的ID。某个判项无效，不会丢掉整页其他有效结果。

| 视角 | 检查重点 |
|---|---|
| 页内细节（8维） | 文字、事实、可读、裁切、图片、图表标注、来源、颜色辨识 |
| 单页表达（8维） | 主旨证据、布局、密度留白、层级、图文、配图、关系、协调 |
| 整稿（8维） | 任务、故事、取舍、口径、视觉系统、节奏、讲稿、收束 |

主报告左侧展示原页，右侧列出该页的维度评分、问题和改法，只展开有修改项的页面。整稿用页序拼图配叙事优缺点。24项评分和权重可展开调整，实时试算综合观察分；工程资料在独立Debug页。

事实没有核实就记未知；同一问题只在主归属维度扣分。最终摘要和建议随复核结果重建，原始模型意见单独保留。

## 安装与使用

将`ppt-evaluation/`目录复制到Agent的skills目录，调用`$ppt-evaluation`。需要Python 3.10+及Pillow：

```bash
python -m pip install Pillow
```

先用可信工具把PPTX/PDF渲染为有序PNG/JPEG；仅检查已有图片也可。记录渲染器和源页映射，实际渲染由调用者完成。

```bash
python scripts/prepare.py --images /path/pages --pptx /path/deck.pptx --page-map /path/page-map.json --output /path/run/manifest.json
# 通过环境变量提供DEEPSEEK_API_KEY，勿写入输入文件或提交仓库。
python scripts/evaluate.py --manifest /path/run/manifest.json --context /path/context.json --out /path/run/evaluation --save-trace
```

默认调用官方DeepSeek `deepseek-flash`；其他兼容服务需显式配置。模型服务会接收指定页面与上下文，运行前取得输入所有者授权。未配置API时，也可以由Agent按同一协议评审，明确标记评审来源。

默认最多12次调用，临时网络错误最多重试1次且占用预算。N页正常需N＋1次；大稿请明确调整`--max-calls`。预算不足时输出部分报告与未知，不伪装完成。不自动安装Office、不自动切换付费服务、不修改原PPT。

完整说明见 [SKILL.md](SKILL.md)、[计分规则](references/scoring.md)、[输入输出协议](references/input-format.md)。

## 验证与限制

v0.2.3修复模型在UNKNOWN/N/A判项中省略null评分字段时的中断；有分状态缺少评分仍单独隔离，不补分。

```bash
# 仓库中的tests用于维护者回归；安装包按SKILL.md执行。
```

测试覆盖错误目标的局部隔离、未知分母、事实同口径核对、去重、复核摘要更新、调用预算及本地模拟服务端到端路径。模拟服务测试不代表真实模型质量。实际样本与私有运行日志不收入公开包。

图像评测无法保证穷尽所有小字与事实；结构化来源是否完整、图片识读、主观美感与语义去重仍需复核。判项覆盖率不等于“全部事实已核验”。原生编辑性、alt text、动画或真实演讲表现不属于默认截图质量分。

v0.2从逐原生对象改为按页评测；旧v0.1数据不可直接混算，须保留旧报告并重新准备输入。旧`ppt-quality-check`可保留为本地兼容入口，不是安装依赖。

## 开源与反馈

原创程序和规则采用[MIT](LICENSE)。[来源索引](references/sources.md)保留参考项目与许可边界，不代表复制其实现或采用其现成总分公式。包中不含客户PPT、公司评测表、WorkBuddy内部文档或凭据。

公开源码与更新来源：[foxbitcoo/ppt-evaluation-skill](https://github.com/foxbitcoo/ppt-evaluation-skill)。首次安装可克隆仓库，再将`ppt-evaluation/`复制到Agent的skills目录；更新时在克隆目录执行`git pull --ff-only`，再替换已安装的Skill目录。不安装全局自动更新钩子。

问题可在[GitHub Issues](https://github.com/foxbitcoo/ppt-evaluation-skill/issues)反馈版本、最小复现和脱敏结果；不要上传私有PPT、完整提示词或密钥。安全问题见[SECURITY.md](SECURITY.md)。
