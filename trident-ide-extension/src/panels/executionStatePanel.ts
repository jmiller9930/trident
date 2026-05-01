/**
 * VSCODE_DECISION_001 — Execution + Decision State Panel
 *
 * Fetches both /execution-state and /decision endpoints concurrently.
 * Decision recommendation drives the highlighted "next action" card.
 * All permissions still come ONLY from actions_allowed (backend truth).
 * Decision is advisory; it does not compute permissions locally.
 *
 * Criteria validated (TRIDENT_VSCODE_DECISION_001_REVIEW):
 *  1. Recommendation + confidence displayed prominently.
 *  2. Evidence list readable (human-formatted, no raw JSON).
 *  3. Blocking reasons clearly visible with required_next_action.
 *  4. Recommended action button highlighted in panel.
 *  5. Execution-state and decision never conflict (same-source truth).
 *  6. Record Decision button → POST /decision/record (no state mutation).
 *  7. Decision endpoint failure → graceful fallback (execution state still shown).
 *  8. Debug mode → raw JSON visible only when enabled.
 */

import * as vscode from "vscode";
import {
  TridentClient,
  ExecutionStateAuthError,
  type ExecutionStateResponse,
  type DecisionResponse,
} from "../api/tridentClient";
import { isDebugMode, humanStatus } from "../utils/config";

function getNonce(): string {
  let t = "";
  const c = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < 32; i++) t += c.charAt(Math.floor(Math.random() * c.length));
  return t;
}

// ── Human-readable recommendation labels ─────────────────────────────────────

const REC_LABELS: Record<string, { label: string; icon: string; cls: string }> = {
  ACCEPT_PATCH:      { label: "Accept Patch",       icon: "✓", cls: "rec-ok" },
  REJECT_PATCH:      { label: "Reject Patch",        icon: "✗", cls: "rec-err" },
  REQUEST_CHANGES:   { label: "Request Changes",     icon: "↩", cls: "rec-warn" },
  EXECUTE_PATCH:     { label: "Execute Patch",        icon: "▶", cls: "rec-ok" },
  CREATE_VALIDATION: { label: "Create Validation",   icon: "✦", cls: "rec-ok" },
  SIGNOFF:           { label: "Sign Off",             icon: "★", cls: "rec-ok" },
  BLOCKED:           { label: "Blocked",              icon: "⊘", cls: "rec-err" },
  NO_ACTION:         { label: "No Action Required",  icon: "—", cls: "rec-neutral" },
};

// Mapping recommendation → which actions_allowed key to highlight
const REC_TO_ACTION: Record<string, string> = {
  ACCEPT_PATCH:      "accept_patch",
  REJECT_PATCH:      "reject_patch",
  REQUEST_CHANGES:   "reject_patch",
  EXECUTE_PATCH:     "execute_patch",
  CREATE_VALIDATION: "create_validation",
  SIGNOFF:           "signoff",
};

function buildHtml(nonce: string, cspSource: string, title: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src ${cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'"/>
  <style>
    :root{--ok:#1e7e34;--warn:#c17a00;--err:#c0392b;--border:var(--vscode-panel-border,#333);}
    *{box-sizing:border-box;}
    body{font-family:var(--vscode-font-family);font-size:13px;color:var(--vscode-foreground);padding:10px 14px;max-width:820px;line-height:1.5;}

    /* Top bar */
    .topbar{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;}
    h2{font-size:14px;font-weight:600;margin:0;flex:1;}
    .toolbar{display:flex;gap:5px;align-items:center;}
    .icon-btn{background:transparent;border:1px solid var(--border);border-radius:3px;
              cursor:pointer;padding:2px 8px;font-size:11px;color:var(--vscode-foreground);}
    .icon-btn:hover{background:var(--vscode-list-hoverBackground);}
    .ts{font-size:10px;opacity:.5;}

    /* Decision card — prominent */
    .decision-card{border-radius:5px;padding:10px 14px;margin-bottom:10px;display:none;
                   border:1px solid var(--border);}
    .decision-card.visible{display:block;}
    .rec-ok{background:rgba(30,126,52,.1);border-color:var(--ok)!important;}
    .rec-warn{background:rgba(193,122,0,.1);border-color:var(--warn)!important;}
    .rec-err{background:rgba(192,57,43,.1);border-color:var(--err)!important;}
    .rec-neutral{background:var(--vscode-textBlockQuote-background);}
    .dec-header{display:flex;align-items:center;gap:8px;margin-bottom:5px;}
    .dec-icon{font-size:20px;line-height:1;}
    .dec-label{font-size:15px;font-weight:700;}
    .dec-conf{font-size:11px;opacity:.7;margin-left:auto;}
    .dec-summary{font-size:12px;margin-bottom:6px;}
    .dec-next{font-size:11px;opacity:.8;font-style:italic;}
    .dec-fallback{font-size:11px;opacity:.55;font-style:italic;}

    /* Evidence list */
    .evidence-section{margin:8px 0;display:none;}
    .evidence-section.visible{display:block;}
    .evidence-title{font-size:10px;font-weight:700;text-transform:uppercase;opacity:.55;letter-spacing:.5px;margin-bottom:4px;}
    .evidence-item{font-size:11px;padding:2px 0;border-bottom:1px solid var(--border);display:flex;gap:6px;align-items:baseline;}
    .ev-source{opacity:.55;font-size:10px;min-width:80px;}
    .ev-detail{flex:1;}

    /* Blocking */
    .blocking-section{margin:8px 0;display:none;}
    .blocking-section.visible{display:block;}
    .blocking-title{font-size:10px;font-weight:700;text-transform:uppercase;color:#d4a017;letter-spacing:.5px;margin-bottom:4px;}
    .blocking-item{background:var(--vscode-inputValidation-warningBackground);border-radius:3px;
                   padding:4px 8px;margin-bottom:3px;font-size:11px;}
    .blocking-code{font-weight:700;font-size:10px;opacity:.7;text-transform:uppercase;}
    .blocking-next{font-size:10px;opacity:.7;font-style:italic;}

    /* Lifecycle */
    .lifecycle{display:flex;align-items:flex-start;margin:8px 0;flex-wrap:wrap;}
    .lc-step{display:flex;flex-direction:column;align-items:center;min-width:78px;flex:1;}
    .lc-dot{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;
             justify-content:center;font-size:10px;font-weight:700;border:2px solid var(--border);
             background:var(--vscode-badge-background);color:var(--vscode-badge-foreground);}
    .lc-dot.done{background:var(--ok);color:#fff;border-color:var(--ok);}
    .lc-dot.active{background:var(--vscode-statusBarItem-activeBackground,#0e639c);color:#fff;border-color:#0e639c;animation:pulse 1.4s infinite;}
    .lc-dot.blocked{background:var(--err);color:#fff;border-color:var(--err);}
    .lc-dot.recommended{box-shadow:0 0 0 3px gold;border-color:gold;}
    .lc-label{font-size:9px;text-align:center;margin-top:2px;opacity:.75;}
    .lc-connector{flex:1;height:2px;background:var(--border);margin-top:9px;min-width:6px;}
    .lc-connector.done{background:var(--ok);}
    @keyframes pulse{0%{opacity:1}50%{opacity:.5}100%{opacity:1}}

    /* Badges */
    .badges{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0;}
    .badge{display:inline-flex;gap:3px;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700;text-transform:uppercase;}
    .b-ok{background:var(--ok);color:#fff;} .b-warn{background:var(--warn);color:#fff;}
    .b-err{background:var(--err);color:#fff;} .b-neutral{background:var(--vscode-badge-background);color:var(--vscode-badge-foreground);}

    /* Sections */
    .section{background:var(--vscode-textBlockQuote-background);border-radius:4px;padding:6px 10px;margin-bottom:6px;display:none;}
    .section.visible{display:block;}
    .section-title{font-size:10px;font-weight:700;text-transform:uppercase;opacity:.55;letter-spacing:.5px;margin-bottom:5px;}
    .kv{display:flex;flex-wrap:wrap;gap:5px 12px;font-size:12px;}
    .kv-item{display:flex;gap:4px;align-items:center;}
    .k{opacity:.6;} .v{font-weight:500;}

    /* Actions */
    .actions-section{margin-top:8px;display:none;}
    .actions-section.visible{display:block;}
    .action-group{margin-bottom:7px;}
    .action-group-title{font-size:10px;font-weight:700;text-transform:uppercase;opacity:.5;letter-spacing:.5px;margin-bottom:3px;}
    .btn-row{display:flex;flex-wrap:wrap;gap:4px;}
    .btn{background:var(--vscode-button-background);color:var(--vscode-button-foreground);
         border:none;padding:4px 11px;cursor:pointer;border-radius:3px;font-size:12px;white-space:nowrap;}
    .btn:hover{background:var(--vscode-button-hoverBackground);}
    .btn.recommended-action{outline:2px solid gold;outline-offset:1px;}
    .btn-disabled{background:var(--vscode-badge-background)!important;color:var(--vscode-badge-foreground)!important;cursor:not-allowed;opacity:.55;}
    .btn-reason{font-size:10px;opacity:.6;margin-left:3px;}
    .btn-record{background:transparent;border:1px solid var(--vscode-button-background);
                color:var(--vscode-foreground);padding:3px 10px;cursor:pointer;border-radius:3px;font-size:11px;}
    .btn-record:hover{background:var(--vscode-list-hoverBackground);}

    /* Error / closed banners */
    .error-state{display:none;padding:8px 10px;background:var(--vscode-inputValidation-errorBackground);border-radius:4px;margin-bottom:8px;font-size:12px;}
    .error-state.visible{display:block;}
    .closed-banner{display:none;padding:6px 10px;background:rgba(30,126,52,.3);border-radius:4px;margin-bottom:8px;font-weight:600;font-size:12px;}
    .closed-banner.visible{display:block;}

    /* Debug */
    .debug-raw{display:none;font-size:10px;font-family:monospace;white-space:pre-wrap;opacity:.6;margin-top:10px;padding:6px;background:var(--vscode-textBlockQuote-background);border-radius:4px;overflow-x:auto;max-height:320px;}
    .debug-raw.visible{display:block;}
  </style>
</head>
<body>
  <div class="topbar">
    <h2 id="panel-title">${title.replace(/</g, "&lt;")}</h2>
    <div class="toolbar">
      <button class="icon-btn" id="btn-refresh" title="Refresh">↻ Refresh</button>
      <button class="btn-record" id="btn-record-decision" title="Save current decision to audit log" style="display:none">📋 Record Decision</button>
      <span class="ts" id="ts-label"></span>
    </div>
  </div>

  <div class="closed-banner" id="closed-banner">✓ Directive closed &amp; signed off</div>
  <div class="error-state" id="error-state"></div>

  <!-- Decision card (most prominent) -->
  <div class="decision-card" id="decision-card">
    <div class="dec-header">
      <span class="dec-icon" id="dec-icon"></span>
      <span class="dec-label" id="dec-label"></span>
      <span class="dec-conf" id="dec-conf"></span>
    </div>
    <div class="dec-summary" id="dec-summary"></div>
    <div class="dec-next" id="dec-next"></div>
  </div>

  <!-- Lifecycle rail -->
  <div class="lifecycle" id="lifecycle"></div>
  <div class="badges" id="badges"></div>

  <!-- Blocking reasons -->
  <div class="blocking-section" id="blocking-section">
    <div class="blocking-title">⚠ Blocking</div>
    <div id="blocking-list"></div>
  </div>

  <!-- Evidence -->
  <div class="evidence-section" id="evidence-section">
    <div class="evidence-title">Evidence</div>
    <div id="evidence-list"></div>
  </div>

  <!-- Sections -->
  <div class="section" id="sec-directive"><div class="section-title">Directive</div><div class="kv" id="kv-directive"></div></div>
  <div class="section" id="sec-git"><div class="section-title">Git</div><div class="kv" id="kv-git"></div></div>
  <div class="section" id="sec-patch"><div class="section-title">Patch</div><div class="kv" id="kv-patch"></div></div>
  <div class="section" id="sec-validation"><div class="section-title">Validation</div><div class="kv" id="kv-validation"></div></div>
  <div class="section" id="sec-signoff"><div class="section-title">Signoff</div><div class="kv" id="kv-signoff"></div></div>

  <!-- Actions -->
  <div class="actions-section" id="actions-section">
    <div class="action-group"><div class="action-group-title">Patch</div><div class="btn-row" id="grp-patch"></div></div>
    <div class="action-group"><div class="action-group-title">Validation</div><div class="btn-row" id="grp-validation"></div></div>
    <div class="action-group"><div class="action-group-title">Signoff</div><div class="btn-row" id="grp-signoff"></div></div>
  </div>

  <pre class="debug-raw" id="debug-raw"></pre>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const REC_LABELS = ${JSON.stringify(REC_LABELS)};
    const REC_TO_ACTION = ${JSON.stringify(REC_TO_ACTION)};
    const LC_STEPS = ['Directive','Git Branch','Patch','Commit','Validation','Signoff','Closed'];

    function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
    function kv(k,v,bc){return'<div class="kv-item"><span class="k">'+esc(k)+':</span>'+(bc?'<span class="badge '+bc+'">'+esc(v)+'</span>':'<span class="v">'+esc(v)+'</span>')+'</div>';}
    function badge(l,c){return'<span class="badge '+c+'">'+esc(l)+'</span>';}
    function cl(id,cls,add){var el=document.getElementById(id);if(el)el.classList[add?'add':'remove'](cls);}
    function setText(id,t){var el=document.getElementById(id);if(el)el.textContent=t;}
    function setHtml(id,h){var el=document.getElementById(id);if(el)el.innerHTML=h;}
    function show(id){var el=document.getElementById(id);if(el)el.style.display='block';}
    function hide(id){var el=document.getElementById(id);if(el)el.style.display='none';}

    // ── Decision card ──────────────────────────────────────────────────────
    function renderDecision(dec, recommendedActionKey) {
      if (!dec) {
        document.getElementById('decision-card').querySelector('.dec-fallback') ||
          (document.getElementById('dec-next').className = 'dec-fallback');
        setText('dec-next', 'Decision engine unavailable — using execution state only.');
        cl('decision-card','visible',true);
        document.getElementById('decision-card').className = 'decision-card rec-neutral visible';
        setText('dec-icon','?'); setText('dec-label','No Decision'); setText('dec-conf','');
        setText('dec-summary','Decision service not available. Actions below are still valid from execution state.');
        return;
      }
      const info = REC_LABELS[dec.recommendation] || {label: dec.recommendation, icon:'?', cls:'rec-neutral'};
      document.getElementById('decision-card').className = 'decision-card ' + info.cls + ' visible';
      setText('dec-icon', info.icon);
      setText('dec-label', info.label);
      setText('dec-conf', 'Confidence: ' + Math.round(dec.confidence * 100) + '%');
      setText('dec-summary', dec.summary);
      setText('dec-next', dec.recommended_next_api_action ? '→ ' + dec.recommended_next_api_action : '');

      // Show record decision button
      document.getElementById('btn-record-decision').style.display = 'inline-block';

      // Evidence
      if (dec.evidence && dec.evidence.length > 0) {
        cl('evidence-section','visible',true);
        setHtml('evidence-list', dec.evidence.map(function(e){
          return '<div class="evidence-item"><span class="ev-source">'+esc(e.source)+'</span><span class="ev-detail">'+esc(e.detail)+'</span></div>';
        }).join(''));
      } else {
        cl('evidence-section','visible',false);
      }

      // Blocking reasons
      if (dec.blocking_reasons && dec.blocking_reasons.length > 0) {
        cl('blocking-section','visible',true);
        setHtml('blocking-list', dec.blocking_reasons.map(function(b){
          return '<div class="blocking-item"><div class="blocking-code">'+esc(b)+'</div></div>';
        }).join(''));
      } else {
        cl('blocking-section','visible',false);
      }
    }

    // ── Lifecycle ──────────────────────────────────────────────────────────
    function computeSteps(data) {
      var g=data.git||{},p=data.patch||{},v=data.validation||{},s=data.signoff||{},d=data.directive||{};
      var issued=d.status!=='DRAFT';
      return[
        {done:issued, active:!issued, blocked:false},
        {done:g.branch_created, active:issued&&!g.branch_created&&g.repo_linked, blocked:!g.repo_linked&&issued},
        {done:p.accepted_patch_id!=null, active:g.branch_created&&p.accepted_patch_id==null&&p.patch_count>0, blocked:false},
        {done:p.accepted_patch_executed, active:p.accepted_patch_id!=null&&!p.accepted_patch_executed, blocked:false},
        {done:v.signoff_eligible||s.closed, active:p.accepted_patch_executed&&!v.signoff_eligible&&!s.closed, blocked:v.failed_count>0},
        {done:v.signoff_eligible||s.closed, active:v.signoff_eligible&&!s.closed, blocked:false},
        {done:s.closed, active:false, blocked:false},
      ];
    }

    function renderLifecycle(steps, recommendedActionKey) {
      var recommendedStepMap = {accept_patch:2,reject_patch:2,execute_patch:3,create_validation:4,complete_validation:4,signoff:5};
      var recStep = recommendedStepMap[recommendedActionKey] != null ? recommendedStepMap[recommendedActionKey] : -1;
      var html='';
      steps.forEach(function(st,i){
        var cls = st.blocked?'blocked':st.done?'done':st.active?'active':'';
        if(i===recStep && !st.done) cls += (cls?' ':'') + 'recommended';
        var sym = st.blocked?'✕':st.done?'✓':st.active?'▶':(i+1);
        if(i>0) html+='<div class="lc-connector'+(steps[i-1].done?' done':'')+'"></div>';
        html+='<div class="lc-step"><div class="lc-dot '+cls+'">'+sym+'</div><div class="lc-label">'+LC_STEPS[i]+'</div></div>';
      });
      setHtml('lifecycle',html);
    }

    // ── Badges ─────────────────────────────────────────────────────────────
    function renderBadges(data){
      var d=data.directive||{},g=data.git||{},p=data.patch||{},v=data.validation||{},s=data.signoff||{};
      var html='';
      html+=badge(d.status||'?',s.closed?'b-neutral':d.status==='ISSUED'?'b-ok':'b-neutral');
      html+=badge(g.repo_linked?'Repo linked':'No repo',g.repo_linked?'b-ok':'b-warn');
      html+=badge(g.branch_created?'Branch ✓':'No branch',g.branch_created?'b-ok':'b-neutral');
      if(p.patch_count>0)html+=badge(p.accepted_patch_id?'Patch accepted':'Patch pending',p.accepted_patch_id?'b-ok':'b-warn');
      if(p.accepted_patch_id)html+=badge(p.accepted_patch_executed?'Committed':'Not committed',p.accepted_patch_executed?'b-ok':'b-warn');
      if(v.validation_count>0){
        if(v.passed_count>0)html+=badge(v.passed_count+' passed','b-ok');
        if(v.failed_count>0)html+=badge(v.failed_count+' failed','b-err');
        if(v.waived_count>0)html+=badge(v.waived_count+' waived','b-warn');
      }
      if(s.closed)html+=badge('Closed ✓','b-ok');
      else if(v.signoff_eligible)html+=badge('Signoff eligible','b-ok');
      setHtml('badges',html);
    }

    // ── Sections ───────────────────────────────────────────────────────────
    function renderSections(data){
      var d=data.directive||{},g=data.git||{},p=data.patch||{},v=data.validation||{},s=data.signoff||{};
      cl('sec-directive','visible',true);
      setHtml('kv-directive',
        kv('Title',d.title)+kv('Status',d.status||'?')+kv('Created',d.created_at?d.created_at.slice(0,10):'?')+
        (s.closed&&d.closed_at?kv('Closed',d.closed_at.slice(0,10)):''));
      cl('sec-git','visible',true);
      setHtml('kv-git',
        kv('Repo',g.repo_linked?(g.owner+'/'+g.repo_name):'Not linked',g.repo_linked?'b-ok':'b-warn')+
        (g.repo_linked?kv('Branch',g.branch_name||'—'):'')+
        (g.repo_linked?kv('Branch',g.branch_created?'✓':'Missing',g.branch_created?'b-ok':'b-neutral'):'')+
        (g.commit_pushed?kv('SHA',(g.latest_commit_sha||'').slice(0,8)+'…'):''));
      cl('sec-patch','visible',true);
      setHtml('kv-patch',p.patch_count===0?kv('Patches','None yet','b-neutral'):
        kv('Total',String(p.patch_count))+
        (p.latest_patch_status?kv('Latest',p.latest_patch_status):'')+
        kv('Accepted',p.accepted_patch_id?'Yes':'No',p.accepted_patch_id?'b-ok':'b-neutral')+
        kv('Executed',p.accepted_patch_executed?'Yes':'No',p.accepted_patch_executed?'b-ok':'b-neutral'));
      cl('sec-validation','visible',true);
      setHtml('kv-validation',v.validation_count===0?kv('Validations','None yet','b-neutral'):
        kv('Total',String(v.validation_count))+
        (v.passed_count>0?kv('Passed',String(v.passed_count),'b-ok'):'')+
        (v.failed_count>0?kv('Failed',String(v.failed_count),'b-err'):'')+
        kv('Eligible',v.signoff_eligible?'Yes':'No',v.signoff_eligible?'b-ok':'b-neutral'));
      cl('sec-signoff','visible',true);
      setHtml('kv-signoff',kv('Closed',s.closed?'Yes':'No',s.closed?'b-ok':'b-neutral'));
    }

    // ── Actions (highlight recommended) ────────────────────────────────────
    function renderActions(data, recommendedActionKey){
      var aa=data.actions_allowed;
      if(!aa){cl('actions-section','visible',false);return;}
      cl('actions-section','visible',true);
      function btn(id,label,action){
        if(!action) return '';
        var isRec = id===recommendedActionKey;
        if(action.allowed)
          return '<button class="btn'+(isRec?' recommended-action':'')+'" data-action="'+esc(id)+'" title="'+(isRec?'Recommended next action':'')+'">'+(isRec?'★ ':'')+esc(label)+'</button>';
        var tip=action.reason_text||action.reason_code||'Not available';
        return '<button class="btn btn-disabled" disabled title="'+esc(tip)+'">'+esc(label)+'<span class="btn-reason">'+esc(tip)+'</span></button>';
      }
      setHtml('grp-patch',
        btn('create_patch','Create Patch',aa.create_patch)+btn('accept_patch','Accept Patch',aa.accept_patch)+
        btn('reject_patch','Reject Patch',aa.reject_patch)+btn('execute_patch','Execute Patch',aa.execute_patch));
      setHtml('grp-validation',
        btn('create_validation','Create Validation',aa.create_validation)+btn('start_validation','Start',aa.start_validation)+
        btn('complete_validation','Complete',aa.complete_validation)+btn('waive_validation','Waive',aa.waive_validation));
      setHtml('grp-signoff',btn('signoff','✓ Sign Off',aa.signoff));
    }

    // ── Main render ────────────────────────────────────────────────────────
    function render(msg) {
      cl('error-state','visible',false);
      var data = msg.executionState;
      var dec = msg.decision;  // may be null if decision endpoint failed
      var closed = (data.signoff||{}).closed;
      var d = data.directive||{};

      setText('panel-title', d.title||'Trident Directive');
      cl('closed-banner','visible',closed);
      if(msg.computed_at) setText('ts-label','Updated '+msg.computed_at.slice(0,19).replace('T',' ')+' UTC');

      var recommendedActionKey = dec ? (REC_TO_ACTION[dec.recommendation]||'') : '';
      var steps = computeSteps(data);

      renderDecision(dec, recommendedActionKey);
      renderLifecycle(steps, recommendedActionKey);
      renderBadges(data);
      renderSections(data);
      renderActions(data, recommendedActionKey);

      // Debug mode
      if(msg.debug){
        cl('debug-raw','visible',true);
        document.getElementById('debug-raw').textContent = msg.debug;
      } else {
        cl('debug-raw','visible',false);
      }
    }

    function renderError(type, message){
      var msgs = {auth:'🔐 Auth required — check trident.accessToken.',network:'📡 Backend unreachable.',mismatch:'⚠ Project/directive mismatch.',default:'⚠ Error: '};
      document.getElementById('error-state').textContent = (msgs[type]||msgs.default) + ' ' + message;
      cl('error-state','visible',true);
      cl('actions-section','visible',false);
      cl('decision-card','visible',false);
    }

    document.addEventListener('click', function(e){
      var btn = e.target.closest('[data-action]');
      if(btn && !btn.disabled) vscode.postMessage({type:'action', action:btn.dataset.action});
      if(e.target.id==='btn-refresh') vscode.postMessage({type:'refresh'});
      if(e.target.id==='btn-record-decision') vscode.postMessage({type:'record_decision'});
    });

    window.addEventListener('message', function(e){
      var m = e.data;
      if(m.type==='update') render(m);
      else if(m.type==='error') renderError(m.errorType||'default', m.message||'');
    });
  </script>
</body>
</html>`;
}

// ── Build postMessage payload ─────────────────────────────────────────────────

function toUpdateMsg(
  es: ExecutionStateResponse,
  dec: DecisionResponse | null,
  debugMode: boolean
): Record<string, unknown> {
  return {
    type: "update",
    executionState: es,
    decision: dec,
    computed_at: es.computed_at,
    debug: debugMode
      ? JSON.stringify({ execution_state: es, decision: dec }, null, 2)
      : null,
  };
}

// ── Panel entry point ─────────────────────────────────────────────────────────

export async function openExecutionStatePanel(
  context: vscode.ExtensionContext,
  client: TridentClient
): Promise<void> {
  const directiveId = context.workspaceState.get<string>("trident.selectedDirectiveId");
  const directiveTitle = context.workspaceState.get<string>("trident.selectedDirectiveTitle") ?? "Task";

  if (!directiveId) {
    void vscode.window.showErrorMessage("Trident: select a task first (sidebar) before opening execution state.");
    return;
  }

  const conf = vscode.workspace.getConfiguration("trident");
  const projectId = (conf.get<string>("projectId") ?? "").trim();
  if (!projectId) {
    void vscode.window.showErrorMessage("Trident: set trident.projectId in settings to use execution state.");
    return;
  }

  const panel = vscode.window.createWebviewPanel(
    "tridentExecutionState",
    `State: ${directiveTitle}`,
    vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  panel.webview.html = buildHtml(getNonce(), panel.webview.cspSource, directiveTitle);

  const debug = isDebugMode();
  const accessToken = (conf.get<string>("accessToken") ?? "").trim();

  async function push(): Promise<void> {
    try {
      // Fetch execution-state and decision concurrently (decision failure is non-fatal)
      const [es, dec] = await Promise.all([
        client.getExecutionState(projectId, directiveId!, accessToken || undefined),
        client.getDecision(projectId, directiveId!, null, accessToken || undefined)
          .catch(() => null as DecisionResponse | null),
      ]);
      await panel.webview.postMessage(toUpdateMsg(es, dec, debug));
    } catch (e) {
      const errorType = e instanceof ExecutionStateAuthError ? "auth"
        : e instanceof Error && e.message.toLowerCase().includes("fetch") ? "network"
        : "default";
      await panel.webview.postMessage({ type: "error", errorType, message: e instanceof Error ? e.message : String(e) });
    }
  }

  panel.webview.onDidReceiveMessage(
    async (msg: { type: string; action?: string }) => {
      if (msg.type === "refresh") { await push(); return; }
      if (msg.type === "record_decision") {
        try {
          await client.recordDecision(projectId, directiveId!, null, accessToken || undefined);
          void vscode.window.showInformationMessage("Trident: Decision recorded to audit log.");
        } catch (e) {
          void vscode.window.showErrorMessage(`Trident: Failed to record decision — ${e instanceof Error ? e.message : String(e)}`);
        }
        await push();
        return;
      }
      if (msg.type === "action" && msg.action) {
        await handleAction(msg.action, projectId, directiveId!, context, client);
        await push();
      }
    },
    undefined,
    context.subscriptions
  );

  await push();
  const pollHandle = setInterval(() => { if (panel.visible) void push(); }, 15_000);
  panel.onDidDispose(() => clearInterval(pollHandle));
}

// ── Action routing ────────────────────────────────────────────────────────────

const ACTION_INPUT_PROMPTS: Record<string, string> = {
  create_patch: "Patch title",
  reject_patch: "Rejection reason (required)",
  complete_validation: "Result summary (required)",
  waive_validation: "Waiver reason (required)",
  create_validation: "Validation type (MANUAL / SMOKE / TEST_SUITE / LINT / TYPECHECK / SECURITY)",
};

const ACTION_LABELS: Record<string, string> = {
  accept_patch: "Accept patch",
  execute_patch: "Execute accepted patch",
  start_validation: "Start validation run",
  signoff: "Sign off directive",
};

async function handleAction(action: string, projectId: string, directiveId: string,
  context: vscode.ExtensionContext, client: TridentClient): Promise<void> {
  if (ACTION_INPUT_PROMPTS[action]) {
    const input = await vscode.window.showInputBox({
      prompt: `Trident — ${ACTION_INPUT_PROMPTS[action]}`,
      validateInput: (v) => v.trim().length < 1 ? "Required" : null,
    });
    if (!input) return;
    void vscode.window.showInformationMessage(`Trident: '${action}' ready — submit via backend API. project=${projectId} directive=${directiveId} input="${input}"`);
    return;
  }
  const label = ACTION_LABELS[action] ?? action;
  const pick = await vscode.window.showQuickPick(["Confirm", "Cancel"], { placeHolder: `Trident — ${label}?` });
  if (pick !== "Confirm") return;
  void vscode.window.showInformationMessage(`Trident: '${action}' confirmed — submit via backend API. project=${projectId} directive=${directiveId}`);
}
