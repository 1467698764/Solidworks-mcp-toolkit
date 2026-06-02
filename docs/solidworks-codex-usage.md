# SolidWorks Codex 使用说明

当前 MCP wrapper 暴露 35 MCP tools，覆盖 read-only、analysis、handoff、write_guarded、export_verify 和 release gates。

这是一套面向通用机械 CAD 项目的 SolidWorks 证据采集、上下文整理、安全修改和验证工具链。目标不是替代工程师做最终强度、热、寿命或公差判断，而是让 Codex/AI 先充分理解当前模型状态，再基于证据选择下一步。

## 核心原则

- 先读模型证据，再计划修改。
- 真实模型修改前先 `backup`。
- 一次只改一个关键变量，保留 before/after 报告。
- 不强制固定输出模板；让强模型结合目标、证据缺口和验证结果自由分析。
- 对尺寸、装配约束、空间关系、干涉、孔系和制造可行性，只在证据足够时给结论；证据不足时明确缺口。

## 常用只读流程

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_before.json
.\tools\solidworks_codex\swctl.ps1 summary -Report tools\solidworks_codex\reports\assembly_before.json -Out tools\solidworks_codex\reports\assembly_before.md
.\tools\solidworks_codex\swctl.ps1 model-understand -Report tools\solidworks_codex\reports\assembly_before.json -View spatial-assembly -Target "locating interfaces, editable dimensions, floating components, clearance, and manufacturing evidence" -Out tools\solidworks_codex\reports\understanding.md -JsonOut tools\solidworks_codex\reports\understanding.json
```

如果需要允许 COM 启动 SolidWorks：

```powershell
.\tools\solidworks_codex\swctl.ps1 start-inspect -Out tools\solidworks_codex\reports\assembly_before.json
```

## 修改前备份

```powershell
.\tools\solidworks_codex\swctl.ps1 backup -Files 'C:\path\to\your\sample_machine.SLDASM','C:\path\to\changed_part.SLDPRT' -Out tools\solidworks_codex\reports\backup_before_change.json
```

## 安全尺寸修改

先从 inspect/model-understand 报告里确认完整尺寸名，例如：

```text
D1@Sketch1@plate.SLDPRT
```

再执行默认不保存的修改：

```powershell
.\tools\solidworks_codex\swctl.ps1 safe-set-dimension -Model 'C:\path\to\changed_part.SLDPRT' -Dimension 'D1@Sketch1@plate.SLDPRT' -ValueM 0.012 -Out tools\solidworks_codex\reports\safe_set_dimension.json
```

确认无误后再决定是否保存。每次修改后建议执行：

```powershell
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_after.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\assembly_before.json -After tools\solidworks_codex\reports\assembly_after.json -Out tools\solidworks_codex\reports\assembly_delta.md -JsonOut tools\solidworks_codex\reports\assembly_delta.json
.\tools\solidworks_codex\swctl.ps1 change-verify -Report tools\solidworks_codex\reports\assembly_delta.json -AllowDimension 'D1@Sketch1@plate.SLDPRT'
```

## 装配、空间关系和制造证据

```powershell
.\tools\solidworks_codex\swctl.ps1 report-context -Report tools\solidworks_codex\reports\assembly_before.json -Target "mounting interface, hole pattern, datum alignment, clearance, and manufacturing evidence" -Out tools\solidworks_codex\reports\context.md -JsonOut tools\solidworks_codex\reports\context.json
.\tools\solidworks_codex\swctl.ps1 report-search -Report tools\solidworks_codex\reports\assembly_before.json -Target "mounting hole D1 Fillet" -Out tools\solidworks_codex\reports\search.md
.\tools\solidworks_codex\swctl.ps1 design-review -Report tools\solidworks_codex\reports\assembly_before.json -Target "assembly constraints, clearance risks, hole pattern evidence, and manufacturing gaps" -Out tools\solidworks_codex\reports\design_review.md
.\tools\solidworks_codex\swctl.ps1 change-plan -Report tools\solidworks_codex\reports\assembly_before.json -Target "adjust a mounting interface while preserving constraints, clearance, and manufacturability" -SessionName mechanical-interface-update -Out tools\solidworks_codex\reports\change_plan.md
```

## 组件状态和检查工具

```powershell
.\tools\solidworks_codex\swctl.ps1 component-state -Component 'drive_unit-1' -Action hide -Out tools\solidworks_codex\reports\component_hide.json
.\tools\solidworks_codex\swctl.ps1 component-state -Component 'drive_unit-1' -Action show -Out tools\solidworks_codex\reports\component_show.json
.\tools\solidworks_codex\swctl.ps1 component-state -Component 'support_bushing-1' -Action suppress
.\tools\solidworks_codex\swctl.ps1 component-state -Component 'support_bushing-1' -Action unsuppress
.\tools\solidworks_codex\swctl.ps1 interference -Out tools\solidworks_codex\reports\interference.json
.\tools\solidworks_codex\swctl.ps1 mass -Out tools\solidworks_codex\reports\mass.json
.\tools\solidworks_codex\swctl.ps1 export -Target tools\solidworks_codex\exports\sample_machine.step -Out tools\solidworks_codex\reports\export_step.json
```

## 交接和多轮工作

```powershell
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 worklog -SessionName mechanical-interface-update -Action decision -Message "Use report-context and report-search before any write operation" -Artifact tools\solidworks_codex\reports\context.md -Next "backup target files before safe-set-dimension"
.\tools\solidworks_codex\swctl.ps1 handoff-bundle -Report tools\solidworks_codex\reports\assembly_before.json -FromReport tools\solidworks_codex\reports\worklog.jsonl -Target "current model evidence, constraints, clearance, and manufacturing gaps" -OutDir tools\solidworks_codex\reports\handoff\assembly-baseline
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

## 更好的请求方式

推荐：

```text
请根据当前证据审查这个装配体的安装接口是否能从 8mm 调整到 10mm。
重点检查：相关尺寸 full name、装配约束、孔系/定位基准、最小间隙、干涉风险、加工和装配可达性。
验证标准：rebuild 无错误，before/after compare 只出现预期变化，必要时运行 interference/export。
权限：先备份，不保存最终文件，给我确认后再继续。
```

不推荐：

```text
请优化整个装配体。
```

因为它缺少目标尺寸、约束、验证标准和允许修改范围。

## 发布和自检

```powershell
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
.\tools\solidworks_codex\swctl.ps1 github-readiness -Out tools\solidworks_codex\reports\github_readiness.json
.\tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
.\tools\solidworks_codex\swctl.ps1 offline-demo -OutDir docs\demo\offline
```

## Live gate：真实 SolidWorks 能力验收

当需要确认不是“离线字符串测试”而是真实 SolidWorks COM 能力可用时，运行：

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
```

live gate 是 opt-in，不默认放进普通 CI；它需要本机 SolidWorks、可导入 `pythoncom/win32com.client` 的 Python，并会尽量设置 `sw.Visible = False` 以减少窗口和内存干扰。它验证的交付物是原生 `.SLDASM/.SLDPRT`：

- 功能套件：拉伸/切除/旋转拉伸/旋转切除/草图尺寸修改/读取修改重建/装配插入/配合/干涉/质量/cleanup。
- 牛头刨床：`tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM`，严格检查零件数、组件数、mate 语义、质量、0 干涉、文件锁。

STEP 导出只保留为 optional smoke，不能替代 `.SLDASM/.SLDPRT` 验收。旧失败生成物可用 `-CleanupStale` 清理；清理范围只包括 `shaper_machine`、`shaper_machine_v2`、`shaper_machine_v3`、`shaper_machine_v4`，不会触碰 `shaper_machine_v5`、`live_capability_suite` 或其它仓库目录。

