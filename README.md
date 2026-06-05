# SolidWorks Codex MCP

[English](README.en.md)

一个面向真实机械 CAD 工作的 practical SolidWorks MCP/control layer。它不是单个夹具生成器，也不是把 AI 固定进某个建模模板；它的主线是先把当前 SolidWorks 状态整理成可靠证据，再让强模型基于证据完成理解、计划、执行和验证。

## 当前定位

- **53 MCP tools** 通过 `tools/solidworks_codex/mcp/server.cjs` 暴露，并落到 `swctl.ps1` 与 Python 控制层。
- 面向通用 SolidWorks MCP：零件、装配、尺寸、特征、mate、Transform2/origin、干涉、质量属性、原生 `.SLDASM/.SLDPRT` 文件读回。
- 执行层已覆盖受控组件插入、零件特征执行、元数据写入、组件状态、尺寸修改、mate 组选面/校验/宏生成/执行检查等链路。
- 证据优先：`inspect` / `model-understand` / `assembly-diagnose` / `interface-index` / `report-context` / `worklog` / `handoff-bundle` 让后续 AI 回合从事实继续，而不是从猜测重启。
- 验证优先但不倒置顺序：先实现执行能力，再配套 `compare`、`change-verify`、`assembly-contract`、`interference`、`live-gate` 与发布门禁。

## 快速开始

```powershell
cd <repo>
.\tools\solidworks_codex\install.ps1 -CheckOnly
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

打开一个 `.SLDASM` 或 `.SLDPRT` 后采集当前证据：

```powershell
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 model-understand `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -View spatial-assembly `
  -Target "constraints, transforms, clearance, editable dimensions, hole patterns, manufacturing evidence" `
  -Out tools\solidworks_codex\reports\understanding.md `
  -JsonOut tools\solidworks_codex\reports\understanding.json
```

## 推荐工作流

1. 用 `inspect` 或 `session-snapshot` 固化当前模型事实。
2. 用 `model-understand` / `assembly-diagnose` / `interface-index` 找对象、接口、风险和证据缺口。
3. 用 `workflow-plan` 选择 validation profiles：`draft_part`、`single_part`、`assembly`、`mechanism_assembly`、`engineering_release`，并按任务设置 `runtime_budget` 与 `extra_checks`。
4. 需要写入时先准备 backup，再执行明确的动作：`safe-set-dimension`、`component-insert`、`part-feature-execute`、`metadata-execute`、`mate-group-execute` 等。
5. 执行后立即 `rebuild`、`inspect`、`compare`、`change-verify`；装配类任务加 `assembly-contract`、`interference`，真实能力验收走 `live-gate`。
6. 暂停、提交或切换会话前，用 `worklog` 和 `handoff-bundle` 记录证据、决策、失败、未解问题和下一步。

## 工具分组

- **只读检查**：`probe`、`start-probe`、`inspect`、`start-inspect`、`selection-report`、`report-summary`、`issue-report`、`mass-properties`。
- **理解与诊断**：`model-understand`、`design-review`、`change-plan`、`report-search`、`report-context`、`assembly-diagnose`、`assembly-repair-plan`、`interface-index`。
- **受控执行**：`backup`、`restore-backup`、`set-dimension`、`safe-set-dimension`、`component-state`、`component-insert`、`feature-state`、`part-feature-execute`、`metadata-execute`、`rebuild`。
- **Mate 与装配**：`mate-macro`、`mate-group-plan`、`mate-group-validate`、`mate-selection-check`、`mate-group-macro`、`mate-group-execute`、`mate-group-execution-check`、`mate-group-live-protocol`、`assembly-review-pipeline`。
- **验证与导出**：`compare`、`change-verify`、`interference`、`assembly-contract`、`export`、`live-gate`。
- **交接与发布**：`worklog`、`handoff-bundle`、`tool-catalog`、`offline-demo`、`preflight`、`audit`、`finalize`、`repo-health`、`github-readiness`。

完整当前目录以生成结果为准：

```powershell
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

## 重要边界

- `shaper_machine_v5` 是 simple-mechanism regression，用来压测 native file readback、semantic mate participation、`0 interference`、cleanup 和装配诊断；它 is not a showcase，也 is not proof，不能把项目边界定义成一个 named fixture。
- 验收主产物是原生 `.SLDASM/.SLDPRT`；STEP optional smoke 只做补充。
- `mate_error: 1` 在 SolidWorks AddMate 路径中按 no-error 处理，但必须再由 mate 读回、参与组件、suppressed 状态、placement 和干涉证据确认。
- 两个固定组件之间的 required mate 默认会被 `assembly-contract` 拦截；只有 manifest 明确 `allow_fixed_fixed: true` 才作为参考/文档约束接受。

## 文档

- 使用指南：`docs/solidworks-codex-usage.md`
- 架构说明：`docs/architecture.md`
- 项目原则：`docs/project-principles.md`
- 故障排查：`docs/troubleshooting.md`
- 工作流：`docs/workflows/README.md`
- 离线 demo：`docs/demo/README.md`
- 能力矩阵：`docs/capability-matrix.md`
- Prompt library / Prompt 库：`docs/prompts.md`
- 路线图：`ROADMAP.md`
- 执行清单：`docs/solidworks-codex-capability-gap-checklist.md`

## 验证与发布

提交或发布前运行：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
.\scripts\verify-all.ps1
```

真实 SolidWorks 能力验收使用：

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
python tools\solidworks_codex\scripts\sw_live_validation_gate.py --cleanup-stale --out tools\solidworks_codex\reports\live_validation_gate.json
```

`CleanupStale` 只清理已知旧生成目录，不触碰 `shaper_machine_v5`、`live_capability_suite` 或普通仓库目录。生成的 reports、backups、exports、宏、缓存和日志通常不提交，除非明确晋升为 fixture 或 demo 资产。

## 许可

本项目使用自定义非商业许可。允许个人学习、研究、评估和非商业修改；转售、付费托管、商业打包或商业 CAD automation / MCP / AI-agent 服务需要权利人书面许可。详见 `LICENSE`。
