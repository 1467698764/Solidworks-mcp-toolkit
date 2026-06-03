# SolidWorks Codex MCP

[English](README.en.md)

一个面向通用机械 CAD 工作的 SolidWorks MCP / 控制层，也可以理解为 practical SolidWorks MCP/control layer。项目重点不是把 AI 固定成某个建模模板，而是先把当前 SolidWorks 模型状态整理成足够可靠、足够紧凑的证据，让强模型能够理解装配、尺寸、约束、空间关系和制造风险之后，再做小步、可验证的操作。

## 项目定位

- 本地 MCP 服务器，加上 PowerShell / Python 工具链，用于连接 SolidWorks 自动化能力。
- 面向真实机械装配场景：零件命名不一定规范，约束和设计意图可能不完整，模型状态需要先被理解。
- 先报告、再计划、再修改：备份、单变量修改、重建、复查、对比、验证。
- 支持跨会话交接，让后续 AI 对话基于已有证据继续工作，而不是每次重新猜测项目状态。

## 核心能力

- **37 个保守 MCP 工具**，由本地 CLI 路径和测试覆盖支撑。
- **模型理解，而不只是自动化建模**：`model-understand` 会生成任务相关的 CAD 证据图，覆盖组件、尺寸、mate 证据、transform、空间关系、孔系/制造证据、决策就绪度和缺失信息；复杂 fixture 还可以用语义配合网络证明功能子装配之间确实被约束。
- **不束缚强模型推理**：`report-context`、`report-search`、`worklog`、`handoff-bundle`、`tool-catalog` 提供上下文和检索能力，但不强行规定单一输出格式或固定领域流程。
- **机械通用性**：示例和 fixture 聚焦通用机械结构，例如板件、壳体、定位界面、孔系、紧固件、间隙、坐标变换和可制造性证据，不绑定单一行业案例或个人课题场景。
- **安全修改闭环**：`preflight`、`audit`、`release-tree`、`public-copy-guard`、`repo-health`、`github-readiness` 和 MCP smoke test 用于捕获常见发布与运行问题。

## 快速开始

```powershell
cd <repo>
.\tools\solidworks_codex\install.ps1 -CheckOnly
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

在 SolidWorks 中打开 `.SLDASM` 或 `.SLDPRT` 后，采集当前模型证据：

```powershell
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 model-understand `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -View spatial-assembly `
  -Target "current constraints, transforms, clearance, editable dimensions, hole patterns, and manufacturing evidence" `
  -Out tools\solidworks_codex\reports\understanding.md `
  -JsonOut tools\solidworks_codex\reports\understanding.json
.\tools\solidworks_codex\swctl.ps1 report-context `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -Target "current model evidence and open questions" `
  -Out tools\solidworks_codex\reports\context.md
```

## 典型工作流

1. 用 `inspect` 或 `session-snapshot` 捕获当前状态。
2. 用 `model-understand` 构建紧凑的证据图。
3. 用 `report-search` 查找不确定的尺寸、特征、mate 或组件。
4. 需要修改时，先用 `change-plan` 生成修改计划。
5. 用 `safe-set-dimension` 或其他受控写入工具完成一次窄范围修改。
6. 执行 `rebuild`、`inspect`、`compare`、`change-verify`，必要时再跑 `interference` / `assembly-contract` / `export`。
7. 对装配类目标，把“哪些组件必须存在、关键组件应在什么空间位置、哪些语义 mate 必须存在且连接哪些组件”写成合约，用 `assembly-contract` 防止只看文件生成成功而忽略零件散落、mate 缺失或位置错误。
8. 暂停或切换 AI 会话前，用 `worklog` 和 `handoff-bundle` 记录交接证据。

## MCP 工具分组

### 只读检查

- `solidworks_probe`
- `solidworks_inspect`
- `solidworks_report_summary`
- `solidworks_selection_report`

### 理解与分析

- `solidworks_model_understand`
- `solidworks_design_review`
- `solidworks_change_plan`
- `solidworks_report_search`
- `solidworks_report_context`

### 受控写入

- `solidworks_backup`
- `solidworks_backup_status`
- `solidworks_restore_backup`
- `solidworks_set_dimension`
- `solidworks_safe_set_dimension`
- `solidworks_component_state`
- `solidworks_rebuild`

### 验证与导出

- `solidworks_compare_reports`
- `solidworks_change_verify`
- `assembly-contract`（CLI）：离线校验 inspect 报告是否满足装配合约，包括组件前缀、Transform2/origin 位置、语义 mate 类型、mate 参与组件和 suppressed 状态；用于把任意机械装配的验收条件抽成可复用机制。现有 fixture 只作为回归样例，不能替代通用装配诊断、接口索引和局部修复能力。
- `solidworks_interference_check`
- `solidworks_mass_properties`
- `solidworks_export`

### 交接

- `solidworks_worklog`
- `solidworks_handoff_bundle`
- `solidworks_tool_catalog`
- `solidworks_offline_demo`

### 发布检查

- `solidworks_preflight`
- `solidworks_audit`
- `solidworks_finalize`
- `solidworks_existing_mcp_tools`

生成当前完整工具目录：

```powershell
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

## MCP 配置

复制并按需修改：

```text
examples/codex-mcp-config.example.toml
```

MCP server 入口：

```text
tools/solidworks_codex/mcp/server.cjs
```

本仓库不会自动修改你的全局 Codex 配置。

## 许可证

本项目使用自定义非商业许可证：允许个人学习、研究、评估和非商业修改；未经作者书面许可，不允许转售、付费托管、打包进商业产品，或用于提供商业 CAD 自动化 / MCP / AI-agent 服务。详见 `LICENSE`。

## 文档

- 使用指南：`docs/solidworks-codex-usage.md`
- 架构说明：`docs/architecture.md`
- 项目原则 / 给未来 AI 会话的偏好：`docs/project-principles.md`
- 故障排查：`docs/troubleshooting.md`
- 离线 demo：`docs/demo/README.md`
- 可复制工作流：`docs/workflows/README.md`
- 能力矩阵：`docs/capability-matrix.md`
- Prompt library / Prompt 库：`docs/prompts.md`
- 发布检查清单：`docs/github-release-checklist.md`
- 更新日志：`CHANGELOG.md`
- 路线图：`ROADMAP.md`

## 提交或发布前验证

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
```

也可以运行：

```powershell
.\scripts\verify-all.ps1
```

生成的 reports、backups、exports、宏、缓存和日志属于运行产物，通常不应提交，除非明确提升为 fixture 或 demo 资产。

## 设计立场

这个项目的目标不是把 AI 限制在狭窄的 CAD 宏模板里，而是给强模型足够准确的 SolidWorks 证据，让它能够自主理解当前机械项目，在证据不足时主动提出缺口，并在合适时执行小步、可验证的修改。

工程审查仍然必要。本工具链提升的是证据采集、空间/约束理解、可重复修改和交接质量；它不能替代最终机械校核、仿真、尺寸链/公差分析或制造评审。

## Live SolidWorks gate（可选但用于真实能力验收）

离线单测、MCP smoke 和 `verify-all.ps1` 只证明仓库语法、工具映射与报告逻辑。要验证真实 SolidWorks 建模/装配能力，请在装有 SolidWorks + pywin32 的本机串行运行 live gate：

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
```

该 gate 会隐藏 SolidWorks 窗口并串行执行几个层级的 live 验证，避免多开窗口和并行 COM 会话：

- `live_session_smoke`：最小实机链路，生成两个小零件和一个装配，创建距离配合，直接 inspect 当前 ModelDoc2，不启动第二个 SolidWorks 会话；要求 mate 回读到参与组件、干涉为 0、退出后无锁文件。
- `live_capability_suite`：验证拉伸、拉伸切除、旋转拉伸、旋转切除、草图尺寸读取/修改/rebuild/save、装配插入、同心配合、距离配合、干涉回调、质量回调、关闭文档和文件锁探测。每个会生成特征的操作还会记录选择隔离证据：创建特征前已清空选择、只选中目标草图、当前活动文档标题、重开后特征实际消耗的草图名和几何计数。每个 live mate 还必须记录清空选择后的计数、创建配合前 2 个选中实体、组件对、保存后 mate feature，以及 inspect 回读到的 mate 类型、参与组件和未 suppressed 状态；inspect 回读组件必须匹配声明的语义合约组件对，而不能只匹配创建时碰巧选中的组件。干涉回调必须可用且 count 为 0，非零干涉会让 gate 失败。
- `complete_shaper_v5`：保留的简单机构装配回归样例，路径为 `tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM`，报告为 `tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json`。它用于暴露装配诊断、接口选择、mate 网络、干涉和 cleanup 问题；不应被当作项目能力上限、展示性成果或通用装配能力已经成熟的证明。

验收主产物始终是原生 `.SLDASM/.SLDPRT`；STEP 只作为 optional smoke，不作为交付判定。`-CleanupStale` 只会删除已知旧失败生成目录 `shaper_machine`/`shaper_machine_v2`/`shaper_machine_v3`/`shaper_machine_v4`，不会触碰 `shaper_machine_v5`、`live_capability_suite` 或仓库其它目录。gate 运行前和每个 live check 之间都会检查 `tools/solidworks_codex/live_fixture/**/~$*`；如果重型 check 超时，会记录 timeout cleanup 结果并只清理无响应或超过内存阈值的 `SLDWORKS.exe`。

Direct Python form (same cleanup flag behind swctl): `python tools/solidworks_codex/scripts/sw_live_validation_gate.py --cleanup-stale --out tools/solidworks_codex/reports/live_validation_gate.json`.
