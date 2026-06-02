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

`swctl.ps1` 的默认报告输出会写回仓库 `tools/solidworks_codex/reports/...`；用户显式传入的相对模型、报告或备份文件路径仍按调用命令时的当前目录解释。跨目录调用时，外部模型路径建议使用绝对路径，仓库产物路径建议使用 `tools\solidworks_codex\...`。

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


## 装配合约验证

`assembly-contract` 是离线、只读的装配验收工具：输入一份 `inspect` JSON 和一份合约 JSON，验证当前装配是否满足可复用的机械证据条件，而不是只相信文件已生成。它重点检查：

- 文档类型和最小组件数；
- 必要组件前缀是否存在；
- 关键组件 Transform/origin 是否在容差内；
- 语义 mate 是否存在、类型是否正确、是否未 suppressed；
- mate inspect 回读的参与组件是否匹配预期语义组件对。

示例合约：

```json
{
  "document_type": "assembly",
  "minimum_component_count": 4,
  "components": {
    "base_plate": {"required": true, "origin_m": [0.0, 0.0, 0.0], "tolerance_m": 0.002},
    "cover_plate": {"required": true, "origin_m": [0.0, 0.0, 0.05], "tolerance_m": 0.002},
    "drive_shaft": {"required": true},
    "bearing_block": {"required": true}
  },
  "mates": {
    "Base_Cover_Distance": {"type": "MateDistanceDim", "semantic_pair": ["base_plate", "cover_plate"]},
    "Shaft_Bearing_Concentric": {"type": "MateConcentric", "semantic_pair": ["drive_shaft", "bearing_block"]}
  }
}
```

运行：

```powershell
.\tools\solidworks_codex\swctl.ps1 assembly-contract `
  -Report tools\solidworks_codex\reports\assembly_before.json `
  -Manifest tools\solidworks_codex\reports\assembly_contract_manifest.json `
  -Out tools\solidworks_codex\reports\assembly_contract.json
```

这个工具会继续用于牛头刨床 live fixture 的通用化验收，但它不是绕开实机建模的替代品：复杂装配仍必须通过 SolidWorks 原生 `.SLDASM/.SLDPRT`、真实 mate 回读、干涉和质量检查。`complete_shaper_v5` 的 spec/live 入口会同步导出 `tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_assembly_contract.json`，因此同一份 inspect 报告既要通过 shaper 专用 gate，也能用通用 `assembly-contract` 复验组件位置和语义 mate 网络。

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

live gate 是 opt-in，不默认放进普通 CI；它需要本机 SolidWorks、可导入 `pythoncom/win32com.client` 的 Python，并会尽量设置 `sw.Visible = False` 以减少窗口和内存干扰。它串行运行，不并行启动多个 SolidWorks 会话。控制台默认只打印 compact summary，完整 JSON 始终写入 `-Out`；如确实需要把完整报告树打印到终端，可加 `-FullConsoleJson`。它验证的交付物是原生 `.SLDASM/.SLDPRT`：

- 会话 smoke：两个小零件 + 一个装配 + 距离配合；inspect 必须读到 mate 参与组件，干涉为 0，退出后无锁。
- 功能套件：拉伸/切除/旋转拉伸/旋转切除/草图尺寸修改/读取修改重建/装配插入/配合/干涉/质量/cleanup。每个特征操作必须带选择隔离证据：当前活动文档、清空选择后的选择数、创建特征前唯一选中的草图、以及重开文件后特征实际消耗的草图名和几何计数。每个配合也必须带选择隔离证据：清空选择后为 0、创建配合前恰好 2 个选中实体、组件对与 mate 结果一致，并通过装配 inspect 回读 mate 类型、参与组件和未 suppressed 状态；回读组件必须匹配声明的语义合约组件对。干涉回调必须可用且 count 为 0，非零干涉会让 gate 失败。
- 牛头刨床：`tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM` 是复杂机械试刀石，不是项目边界；它严格检查零件数、组件数、主要功能组件 Transform2/origin 位置回读、覆盖结构、导轨、刀头、工作台和快回传动的语义配合网络、参与组件、配合创建时的 2 实体选择证据、质量、0 干涉、inspect/model-understanding 证据、文件锁。

STEP 导出只保留为 optional smoke，不能替代 `.SLDASM/.SLDPRT` 验收。旧失败生成物可用 `-CleanupStale` 清理；清理范围只包括 `shaper_machine`、`shaper_machine_v2`、`shaper_machine_v3`、`shaper_machine_v4`，不会触碰 `shaper_machine_v5`、`live_capability_suite` 或其它仓库目录。live gate 会在启动前和每个 check 之间扫描生成目录下的 `~$` 锁文件；重型 check 超时时会记录 cleanup 结果，并只终止无响应或超过内存阈值的 `SLDWORKS.exe`。
