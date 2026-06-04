#!/usr/bin/env node
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const workspace = path.resolve(__dirname, '..', '..', '..');
const serverPath = path.join(__dirname, 'server.cjs');
const sample = path.join(workspace, 'tools', 'solidworks_codex', 'sandbox', 'mcp_sample.SLDPRT');
fs.mkdirSync(path.dirname(sample), { recursive: true });
fs.writeFileSync(sample, 'mcp smoke sample\n');
const mateGroupManifest = path.join(workspace, 'tools', 'solidworks_codex', 'sandbox', 'mcp_mate_group_manifest.json');
const mateSelectionReport = path.join(workspace, 'tools', 'solidworks_codex', 'sandbox', 'mcp_mate_selection_report.json');
const mateGroupValidation = path.join(workspace, 'tools', 'solidworks_codex', 'sandbox', 'mcp_mate_group_validation.json');
fs.writeFileSync(mateGroupManifest, JSON.stringify({
  mode: 'reviewable_mate_group_macros',
  macros: [{
    group_id: 'mcp_fixture_joint',
    mate_type: 'concentric',
    expected_mate_name: 'MG_mcp_fixture_joint_01_concentric',
    macro: 'tools/solidworks_codex/macros/mcp_fixture_joint.swp.vba',
    components: ['shaft-1', 'bearing-1'],
    selection_selectors: [
      { stable_id: 'shaft-1:cylinder:axis', component: 'shaft-1', strategy: 'stable_id_then_feature_dimension_bbox_fallback', fallback: { type: 'cylindrical_axis', origin_m: [0, 0, 0] } },
      { stable_id: 'bearing-1:cylinder:bore', component: 'bearing-1', strategy: 'stable_id_then_feature_dimension_bbox_fallback', fallback: { type: 'cylindrical_axis', origin_m: [0, 0, 0] } }
    ],
    verification: ['rebuild', 'mate_errors']
  }]
}, null, 2));
fs.writeFileSync(mateSelectionReport, JSON.stringify({
  document_title: 'mcp_fixture.SLDASM',
  selection_count: 2,
  selections: [
    { index: 1, type: 'FACES', component: { Name2: 'shaft-1' } },
    { index: 2, type: 'DATUMAXES', component: { Name2: 'bearing-1' } }
  ]
}, null, 2));
fs.writeFileSync(mateGroupValidation, JSON.stringify({
  ok: true,
  counts: { blocking_findings: 0 },
  findings: { blocking: [], warning: [] }
}, null, 2));

const child = spawn(process.execPath, [serverPath], { cwd: workspace, stdio: ['pipe', 'pipe', 'pipe'] });
let id = 1;
let buffer = '';
const pending = new Map();
let stderr = '';

function send(method, params = {}) {
  const msg = { jsonrpc: '2.0', id: id++, method, params };
  child.stdin.write(JSON.stringify(msg) + '\n');
  return new Promise((resolve, reject) => {
    pending.set(msg.id, { resolve, reject, method });
    setTimeout(() => {
      if (pending.has(msg.id)) {
        pending.delete(msg.id);
        reject(new Error(`timeout waiting for ${method}`));
      }
    }, 20000);
  });
}

function notify(method, params = {}) {
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
}

child.stdout.on('data', (d) => {
  buffer += d.toString();
  const lines = buffer.split(/\r?\n/);
  buffer = lines.pop();
  for (const line of lines) {
    if (!line.trim()) continue;
    const msg = JSON.parse(line);
    const p = pending.get(msg.id);
    if (p) {
      pending.delete(msg.id);
      if (msg.error) p.reject(new Error(`${p.method}: ${msg.error.message}`));
      else p.resolve(msg.result);
    }
  }
});
child.stderr.on('data', (d) => { stderr += d.toString(); });

(async () => {
  const init = await send('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'solidworks-codex-smoke', version: '0.1' } });
  notify('notifications/initialized');
  const listed = await send('tools/list');
  const backup = await send('tools/call', { name: 'solidworks_backup', arguments: { files: [sample], out: 'tools/solidworks_codex/reports/mcp_backup_sample.json' } });
  const backupStatus = await send('tools/call', { name: 'solidworks_backup_status', arguments: { report: 'tools/solidworks_codex/reports/mcp_backup_sample.json', out: 'tools/solidworks_codex/reports/mcp_backup_status.json' } });
  const restoreBackup = await send('tools/call', { name: 'solidworks_restore_backup', arguments: { report: 'tools/solidworks_codex/reports/mcp_backup_sample.json', out: 'tools/solidworks_codex/reports/mcp_restore_backup_dryrun.json' } });
  const existing = await send('tools/call', { name: 'solidworks_existing_mcp_tools', arguments: {} });
  const compare = await send('tools/call', { name: 'solidworks_compare_reports', arguments: { before: 'tools/solidworks_codex/sandbox/report_before.json', after: 'tools/solidworks_codex/sandbox/report_after.json', out: 'tools/solidworks_codex/reports/mcp_compare_fixture.md', json_out: 'tools/solidworks_codex/reports/mcp_compare_fixture.json' } });
  const changeVerify = await send('tools/call', { name: 'solidworks_change_verify', arguments: { delta: 'tools/solidworks_codex/reports/mcp_compare_fixture.json', allow_dimension: ['D1@Sketch1@plate.SLDPRT'], allow_component: ['support_bushing-1:suppressed','drive_unit-1:fixed'], allow_component_added: ['reference_sensor-1'], allow_feature_type: ['Fillet'], out: 'tools/solidworks_codex/reports/mcp_change_verify.json' } });
  const template = await send('tools/call', { name: 'solidworks_template_macro', arguments: { template: 'flange', outer_diameter_mm: 50, thickness_mm: 6, center_bore_mm: 16, hole_count: 4, hole_pcd_mm: 38, hole_diameter_mm: 4.5, out: 'tools/solidworks_codex/macros/mcp_flange.swp.vba', manifest: 'tools/solidworks_codex/reports/mcp_flange_manifest.json' } });
  const issue = await send('tools/call', { name: 'solidworks_issue_report', arguments: { report: 'tools/solidworks_codex/sandbox/report_after.json', out: 'tools/solidworks_codex/reports/mcp_issue_fixture.md', json_out: 'tools/solidworks_codex/reports/mcp_issue_fixture.json' } });
  const mate = await send('tools/call', { name: 'solidworks_mate_macro', arguments: { mate: 'concentric', out: 'tools/solidworks_codex/macros/mcp_mate_concentric.swp.vba', manifest: 'tools/solidworks_codex/reports/mcp_mate_concentric_manifest.json' } });
  const mateSelectionCheck = await send('tools/call', { name: 'solidworks_mate_selection_check', arguments: { macro_manifest: 'tools/solidworks_codex/sandbox/mcp_mate_group_manifest.json', selection_report: 'tools/solidworks_codex/sandbox/mcp_mate_selection_report.json', expected_mate_name: 'MG_mcp_fixture_joint_01_concentric', out: 'tools/solidworks_codex/reports/mcp_mate_selection_check.json' } });
  const mateGroupExecute = await send('tools/call', { name: 'solidworks_mate_group_execute', arguments: { macro_manifest: 'tools/solidworks_codex/sandbox/mcp_mate_group_manifest.json', dry_run: true, out: 'tools/solidworks_codex/reports/mcp_mate_group_execute.json' } });
  const mateGroupLiveProtocol = await send('tools/call', { name: 'solidworks_mate_group_live_protocol', arguments: { macro_manifest: 'tools/solidworks_codex/sandbox/mcp_mate_group_manifest.json', validation_report: 'tools/solidworks_codex/sandbox/mcp_mate_group_validation.json', model: 'C:/models/mcp_fixture.SLDASM', out: 'tools/solidworks_codex/reports/mcp_mate_group_live_protocol.json', markdown_out: 'tools/solidworks_codex/reports/mcp_mate_group_live_protocol.md' } });
  const designReview = await send('tools/call', { name: 'solidworks_design_review', arguments: { report: 'tools/solidworks_codex/sandbox/report_after.json', intent: 'locating interfaces, floating components, editable dimensions, and manufacturability evidence', out: 'tools/solidworks_codex/reports/mcp_design_review.md', json_out: 'tools/solidworks_codex/reports/mcp_design_review.json' } });
  const changePlan = await send('tools/call', { name: 'solidworks_change_plan', arguments: { report: 'tools/solidworks_codex/sandbox/report_after.json', goal: 'adjust a critical mounting dimension and verify assembly, clearance, and manufacturing evidence', session_name: 'mcp-change', out: 'tools/solidworks_codex/reports/mcp_change_plan.md', json_out: 'tools/solidworks_codex/reports/mcp_change_plan.json' } });
  const reportSearch = await send('tools/call', { name: 'solidworks_report_search', arguments: { report: 'tools/solidworks_codex/sandbox/report_after.json', query: 'bearing D1 Fillet', out: 'tools/solidworks_codex/reports/mcp_report_search.md', json_out: 'tools/solidworks_codex/reports/mcp_report_search.json' } });
  const reportContext = await send('tools/call', { name: 'solidworks_report_context', arguments: { report: 'tools/solidworks_codex/sandbox/report_after.json', focus: 'current model evidence, constraints, clearance, and manufacturing gaps', out: 'tools/solidworks_codex/reports/mcp_report_context.md', json_out: 'tools/solidworks_codex/reports/mcp_report_context.json' } });
  const modelUnderstand = await send('tools/call', { name: 'solidworks_model_understand', arguments: { report: 'tools/solidworks_codex/sandbox/report_after.json', task: 'understand component constraints, spatial relationships, editable dimensions, and manufacturing evidence', view: 'assembly-constraints', out: 'tools/solidworks_codex/reports/mcp_model_understanding.md', json_out: 'tools/solidworks_codex/reports/mcp_model_understanding.json' } });
  const worklog = await send('tools/call', { name: 'solidworks_worklog', arguments: { session_name: 'mcp-smoke', event: 'verification', message: 'MCP smoke exercised report context and worklog tools', artifact: ['tools/solidworks_codex/sandbox/report_after.json'], next: 'Run audit before handoff', log: 'tools/solidworks_codex/reports/mcp_worklog.jsonl', summary_out: 'tools/solidworks_codex/reports/mcp_worklog.md' } });
  const handoff = await send('tools/call', { name: 'solidworks_handoff_bundle', arguments: { report: 'tools/solidworks_codex/sandbox/report_after.json', worklog: 'tools/solidworks_codex/reports/mcp_worklog.jsonl', focus: 'current model evidence, constraints, clearance, and manufacturing gaps', out_dir: 'tools/solidworks_codex/reports/mcp_handoff' } });
  const toolCatalog = await send('tools/call', { name: 'solidworks_tool_catalog', arguments: { out: 'tools/solidworks_codex/reports/mcp_tool_catalog.md', json_out: 'tools/solidworks_codex/reports/mcp_tool_catalog.json' } });
  const offlineDemo = await send('tools/call', { name: 'solidworks_offline_demo', arguments: { out_dir: 'tools/solidworks_codex/reports/mcp_offline_demo' } });
  const preflight = await send('tools/call', { name: 'solidworks_preflight', arguments: { out: 'tools/solidworks_codex/reports/mcp_preflight.json' } });
  const summary = {
    init: init.serverInfo,
    tool_count: listed.tools.length,
    tool_names: listed.tools.map(t => t.name),
    backup_is_error: backup.isError === true,
    backupStatus_is_error: backupStatus.isError === true,
    restoreBackup_is_error: restoreBackup.isError === true,
    backup_text_head: backup.content?.[0]?.text?.slice(0, 500),
    existing_mcp_is_error: existing.isError === true,
    compare_is_error: compare.isError === true,
    changeVerify_is_error: changeVerify.isError === true,
    has_safe_set_dimension: listed.tools.some(t => t.name === 'solidworks_safe_set_dimension'),
    template_is_error: template.isError === true,
    issue_is_error: issue.isError === true,
    mate_is_error: mate.isError === true,
    mateSelectionCheck_is_error: mateSelectionCheck.isError === true,
    mateGroupExecute_is_error: mateGroupExecute.isError === true,
    mateGroupLiveProtocol_is_error: mateGroupLiveProtocol.isError === true,
    designReview_is_error: designReview.isError === true,
    changePlan_is_error: changePlan.isError === true,
    reportSearch_is_error: reportSearch.isError === true,
    reportContext_is_error: reportContext.isError === true,
    modelUnderstand_is_error: modelUnderstand.isError === true,
    worklog_is_error: worklog.isError === true,
    handoff_is_error: handoff.isError === true,
    toolCatalog_is_error: toolCatalog.isError === true,
    offlineDemo_is_error: offlineDemo.isError === true,
    preflight_is_error: preflight.isError === true,
    backupStatus_text_head: backupStatus.content?.[0]?.text?.slice(0, 500),
    restoreBackup_text_head: restoreBackup.content?.[0]?.text?.slice(0, 500),
    existing_mcp_text_head: existing.content?.[0]?.text?.slice(0, 500),
    compare_text_head: compare.content?.[0]?.text?.slice(0, 500),
    changeVerify_text_head: changeVerify.content?.[0]?.text?.slice(0, 500),
    template_text_head: template.content?.[0]?.text?.slice(0, 500),
    issue_text_head: issue.content?.[0]?.text?.slice(0, 500),
    mate_text_head: mate.content?.[0]?.text?.slice(0, 500),
    mateSelectionCheck_text_head: mateSelectionCheck.content?.[0]?.text?.slice(0, 500),
    mateGroupExecute_text_head: mateGroupExecute.content?.[0]?.text?.slice(0, 500),
    mateGroupLiveProtocol_text_head: mateGroupLiveProtocol.content?.[0]?.text?.slice(0, 500),
    designReview_text_head: designReview.content?.[0]?.text?.slice(0, 500),
    changePlan_text_head: changePlan.content?.[0]?.text?.slice(0, 500),
    reportSearch_text_head: reportSearch.content?.[0]?.text?.slice(0, 500),
    reportContext_text_head: reportContext.content?.[0]?.text?.slice(0, 500),
    modelUnderstand_text_head: modelUnderstand.content?.[0]?.text?.slice(0, 500),
    worklog_text_head: worklog.content?.[0]?.text?.slice(0, 500),
    handoff_text_head: handoff.content?.[0]?.text?.slice(0, 500),
    toolCatalog_text_head: toolCatalog.content?.[0]?.text?.slice(0, 500),
    offlineDemo_text_head: offlineDemo.content?.[0]?.text?.slice(0, 500),
    preflight_text_head: preflight.content?.[0]?.text?.slice(0, 500),
    stderr
  };
  console.log(JSON.stringify(summary, null, 2));
  try { await send('shutdown'); } catch {}
  notify('exit');
  child.kill();
})().catch((err) => {
  console.error(err.stack || err.message);
  console.error(stderr);
  child.kill();
  process.exit(1);
});





