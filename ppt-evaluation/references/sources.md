# 公开研究来源与复用边界

核验日期2026-10-18。本包只含独立编写的规则与代码；来源索引不是打包许可，未复制AGPL/专有或许可待核的源码。源审美意见经适用性筛选，未照搬为全场景阈值。所有原生评分方法与本包的0—4量表分别版本化。

| 来源 | 可借鉴内容 | 原有数值/边界 |
|---|---|---|
|[归藏](https://github.com/op7418/guizang-ppt-skill)|布局测量、严重度、讲稿同步|无质量总分；AGPL-3.0，仅出处和独立摘要，不含其代码|
|[宝玉](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-slide-deck)|受众密度、提示词追溯|无质量总分；MIT|
|[花叔](https://github.com/alchaincyf/huashu-design)|概念与执行锚点|6项1—10，概念门槛；缺明确加权公式；MIT|
|[Zara Zhang](https://github.com/zarazhangrui/frontend-slides)|密度、图片适配、溢出与页序|无质量总分；MIT|
|[RW咨询](https://github.com/Pikapika260214/rw-consulting-ppt)|论点—证据—视觉语义、22类拒收|无数字总分；MIT|
|[PPT-Skill](https://github.com/ken861222/PPT-Skill)|金字塔、讲稿转场|无数字质量分；MIT|
|[OpenAI历史Slides Skill](https://github.com/openai/skills/tree/e6afb0d74cc75d220df2faf3dd6c635c2dc6a108/skills/.curated/slides)|结构候选＋实际渲染|历史版本，当前main无该目录；Apache-2.0|
|[PPTAgent/PPTEval](https://github.com/icip-cas/PPTAgent/tree/d53296bc0ddd73e81d51c523d20dd711c7f233f3)|内容/设计/整稿连贯|1—5分；设计偏好与日期/致谢假设需适配；MIT|
|[AutoPresent/SlidesBench](https://github.com/para-lost/AutoPresent)|文字/图片/布局/颜色、参考对齐|0—5；无图片不扣分；解析失败不可移植为零；MIT|
|[SlidesGen-Bench](https://github.com/YunqiaoYang/SlidesGen-Bench)|来源保真、可重复代理指标|源码许可待补证，不含其代码；不采用缺失值默认补分|
|[Microsoft PPT-Eval](https://github.com/microsoft/ppteval)|编辑任务验收及副作用|编辑任务0—1完成分及success布尔，非通用美学分；MIT|
|[Microsoft可访问性](https://support.microsoft.com/en-us/accessibility/powerpoint/make-your-powerpoint-presentations-accessible-to-people-with-disabilities)|标题、替代文本、对象阅读顺序、对比|版权保留；仅出处与一般原则摘要|
|[Anthropic PPTX](https://github.com/anthropics/skills/tree/main/skills/pptx)|仅核查其存在与许可|专有许可，未复制全文或据此衍生规则|

固定commit、文件URL与哈希见[source-index.json](source-index.json)。本包MIT不覆盖第三方代码、图片、论文或数据集；用户输入PPT的许可不由代码许可证代替。

## 原创规则的来源关联

- O01/O03/O04：文字呈现、可读性与边界检查，可参考OpenAI历史交付检查、AutoPresent布局/字体与Microsoft可访问性。
- O02：本项目原创的来源核验合同，可参考宝玉的数据出处、RW的证据边界；上述视觉/布局检查不负责证明外部事实真实。
- O05—O08：宝玉/Zara图像适配、AutoPresent图像/颜色、Microsoft对象语义。
- S01/S04/S05/S07：RW主张—证据与图形语义、PPTAgent内容/设计、AutoPresent布局。
- S02/S03/S06/S08：归藏几何检测思路、宝玉密度、花叔层级/功能、Zara素材适配。只独立写一般定义，不移植特定风格代码与阈值。
- D01—D06/D08：RW全稿契约、PPTAgent连贯性、宝玉受众与全稿系统、PPT-Skill叙事。
- D07：归藏/Zara/PPT-Skill讲稿和页序对应；必须提供实际稿件，不能由静态图想象现场表现。

规则权重均为实验等权，三层不默认相加。N/A/UNKNOWN、唯一根因账本与覆盖率合同属于本包独立设计。工具跳过/执行失败的来源教训不代表其所有版本均存在同样问题。

## 模型配置核验

2026-10-18[DeepSeek官方调用说明](https://api-docs.deepseek.com/quick_start/agent_integrations/)将`deepseek-flash`对应到V4.1-Flash-1017；[视觉文档](https://api-docs.deepseek.com/guides/vision/)支持原生图像。服务端构建会变，API返回别名不能证明精确构建号，运行记录保留这一差异。
