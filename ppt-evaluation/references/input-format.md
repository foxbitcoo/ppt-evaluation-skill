# 数据协议 v0.2

## 输入

`prepare.py`接收有序页面图，可选原件和页图映射（例如`{"1":"slide-1.png","2":"slide-2.png"}`）。输出`evaluation_unit=rendered_page`、源页、图像哈希、尺寸及可选原生辅助数据。调用模型时不发送原生对象清单作为检查目标；图像哈希改变时阻断依赖它的检查。渲染由调用者完成并记录工具、版本和隐藏页政策。

`context.json`最小例子：

```json
{
  "query": "制作2页经营分析",
  "audience": "管理层",
  "mode": "reading-first",
  "transcript": null,
  "page_mapping_reviewed": true,
  "facts": [
    {"id":"F1","subject":"Example","metric":"revenue","period":"FY2025","unit":"USD million","value":120,"source":{"title":"示例资料","locator":"表1"}}
  ],
  "requirements": [{"id":"R1","description":"第1页需给执行摘要"}]
}
```

事实示例为虚构资料。`facts`必须由可信操作者根据实际来源准备，不能信任成稿自称的数值；source包含可回查的资料/页码/章节。普通参考文本可放入其他上下文字段，但没有结构化反证时不直接支撑自动事实扣分。

## 页面返回

每页对16条O/S规则各给一项；整稿只对8条D规则。页码由调用程序绑定，不用原生对象ID。示例：

```json
{"assessments":[{"rule_id":"O03","status":"BAD","rating":2,"evidence":["左下角图例深字落在深底上"],"reason":"当前渲染可读性受损","issues":[{"kind":"readability","location":"左下角图例","affected_pages":[1],"problem":"图例文字难辨","repair":"改为浅色文字并在实际尺寸复核","severity":"P2","requires_redraw":false}]}]}
```

这里只展示一个判项；实际遗漏项会保留未知，不当作通过。数字错误的issue必须有proof。例如用F1反驳页面的80：

```json
{"type":"source","fact_id":"F1","claim":{"subject":"Example","metric":"revenue","period":"FY2025","unit":"USD million","value":"80","quote":"FY2025 Revenue 80"}}
```

`value`建议用字符串保留显示精度。期间、指标不同不作反证；百万元/亿美元等只在同币种中换算，百分比与百分点不混同。内部矛盾则使用`type=internal`与left/right两条同主体、指标、期间、单位的数值及页面原句。程序只能核对所给结构，原句是否读对仍需视觉与复核。

## 复核与输出

整稿请求接收所有页图及先前有效问题，返回D判项与review_decisions。每个先前问题可keep、drop或merge；不得编造问题ID。额外人工/Agent复核文件为决策数组：

```json
[{"issue_id":"从真实result.json读取的ID","action":"drop","reason":"经查看原图确认是识字误判"}]
```

result.json保存最终规范化判项、三层分数、判项覆盖率、未知、隔离错误、未核验候选、复核与模型历史、真实调用预算/模型/usage。HTML最终结论不使用历史自由摘要，而使用最终结构化缺陷。`--save-trace`另存完整可读请求、图像引用和响应正文，不保存Authorization、Base64或隐藏推理；文件仍含用户输入，默认是私有运行资产。

旧v0.1结果不直接用v0.2评分器重算。新版本必须新建输出目录，保留输入、渲染和规则版本，才能回查改善的是协议还是作品。

`requirement_id`是任务缺项的唯一归属，不是背景标签。只有该缺陷本身违反该项明确要求才填写；同一ID跨单页/整稿或不同kind均只扣一次。普通文字、可读性或配色缺陷留null。单页问题不得关联别页。

可选的`report_metadata`仅控制阅读版标题与展示：title、platform、review_label、storyline（依据实际页序整理，不能来自过时诊断）和debug_url。主报告支持本地权重试算；调权只影响当前页面，真实评分与问题保持原结果版本。
