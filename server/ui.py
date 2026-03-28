"""Web UI for the Email Triage Space."""

WEB_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Email Triage OpenEnv</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0a0a;
  --surface:#111111;
  --card:#161616;
  --raised:#1c1c1c;
  --border:#242424;
  --border-subtle:#1a1a1a;
  --text:#e8e8e8;
  --text-secondary:#888888;
  --text-dim:#555555;
  --accent:#d4d4d4;
  --muted:#777777;
}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;}
body{background:var(--bg);color:var(--text);min-height:100vh;padding:32px;-webkit-font-smoothing:antialiased;}
.app-wrapper{background:var(--surface);border:1px solid var(--border);border-radius:16px;max-width:1300px;margin:0 auto;overflow:hidden;min-height:85vh;display:flex;flex-direction:column;}
.hdr{padding:28px 48px;border-bottom:1px solid var(--border-subtle);display:flex;align-items:center;gap:20px;background:var(--surface);}
.hdr h1{font-size:1.4rem;font-weight:700;letter-spacing:-0.3px;color:var(--text);flex:1;}
.hdr h1 span{color:var(--text-secondary);font-size:1.6rem;line-height:0;font-weight:400;}
.badge{background:transparent;color:var(--text-dim);border:1px solid var(--border);padding:5px 12px;border-radius:4px;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;}
.badge.g{color:var(--text-dim);border-color:var(--border);}
.wrap{padding:36px 48px;display:grid;grid-template-columns:1.3fr 1fr;gap:32px;flex:1;}
.card{background:var(--card);border:1px solid var(--border-subtle);border-radius:8px;padding:32px;}
.card h2{font-size:0.7rem;font-weight:600;color:var(--text-dim);margin-bottom:24px;text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px;}
.card h2::before{content:'';display:block;width:2px;height:14px;background:var(--border);border-radius:1px;}
.email-box{background:var(--raised);border:1px solid var(--border-subtle);border-radius:6px;padding:28px;margin-bottom:12px;animation:fadeIn 0.3s ease-out;}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}
.ef{color:var(--text-dim);font-size:0.75rem;margin-bottom:10px;font-weight:600;text-transform:uppercase;letter-spacing:1px;}
.es{font-weight:600;color:var(--text);font-size:1.1rem;margin-bottom:16px;line-height:1.5;}
.eb{color:var(--text-secondary);font-size:0.9rem;line-height:1.75;white-space:pre-wrap;max-height:240px;overflow-y:auto;padding-right:10px;}
.eb::-webkit-scrollbar{width:4px;}
.eb::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
.att{margin-top:14px;color:var(--text-dim);font-size:0.75rem;display:inline-flex;align-items:center;gap:8px;border:1px solid var(--border);padding:6px 12px;border-radius:4px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;}
.ctrls{display:flex;flex-direction:column;gap:18px;}
label{font-size:0.7rem;color:var(--text-dim);margin-bottom:8px;display:block;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;}
select,input,textarea{width:100%;background:var(--raised);border:1px solid var(--border);color:var(--text);padding:12px 16px;border-radius:6px;font-size:0.9rem;transition:border-color 0.15s;outline:none;-webkit-appearance:none;}
select:focus,input:focus,textarea:focus{border-color:#404040;}
textarea{min-height:90px;resize:vertical;}
button{background:var(--raised);color:var(--text);border:1px solid var(--border);padding:14px 24px;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px;transition:all 0.15s;display:inline-block;width:100%;}
button:hover{background:var(--card);border-color:#404040;color:var(--accent);}
button:active{background:var(--surface);}
.sec{background:var(--surface);}
.sec:hover{background:var(--raised);}
.grn{background:var(--raised);border-color:var(--border);color:var(--text);}
.grn:hover{border-color:#404040;color:var(--accent);}
.row{display:flex;gap:12px;align-items:flex-end;}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
.log{background:var(--raised);border:1px solid var(--border-subtle);border-radius:6px;padding:20px;height:360px;overflow-y:auto;font-family:'Consolas',monospace;font-size:0.82rem;}
.log::-webkit-scrollbar{width:4px;}
.log::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
.le{margin-bottom:10px;padding:8px 12px;border-radius:4px;background:var(--card);color:var(--text-secondary);animation:fadeIn 0.2s ease-out;border-left:2px solid var(--border);}
.r{color:#cbd5e1;border-left-color:#6b7280;}
.e{color:#d1d5db;border-left-color:#4b5563;}
.i{color:var(--text-secondary);border-left-color:var(--border);}
.w{color:#d4d4d8;border-left-color:#52525b;}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;}
.st{background:var(--raised);border:1px solid var(--border-subtle);border-radius:6px;padding:20px;text-align:center;}
.sv{font-size:2rem;font-weight:700;color:var(--text);line-height:1;}
.sl{font-size:0.65rem;color:var(--text-dim);margin-top:8px;font-weight:600;text-transform:uppercase;letter-spacing:2px;}
.prog{background:var(--border-subtle);border-radius:1px;height:2px;margin:24px 0;overflow:hidden;}
.pb{background:var(--border);height:100%;transition:width 0.4s ease-out;}
.mb{margin-bottom:28px;}
.placeholder{color:var(--muted);text-align:center;padding:40px;font-size:0.9rem;letter-spacing:0.01em;}
@media (max-width: 980px){
  body{padding:16px;}
  .wrap{grid-template-columns:1fr;padding:20px;}
  .hdr{padding:20px;flex-wrap:wrap;}
  .card{padding:20px;}
  .row{flex-direction:column;align-items:stretch;}
  .g3{grid-template-columns:1fr;}
}
</style>
</head>
<body>
<div class="app-wrapper">
  <div class="hdr">
    <h1 id="app-title">EMAIL TRIAGE<span>.</span></h1>
    <span class="badge" id="env-badge">OpenEnv v1.0</span>
    <span class="badge g" id="type-badge">Rule Baseline Only</span>
    <span class="badge g">v1.0.0</span>
  </div>
  <div class="wrap">
    <div>
      <div class="card mb">
        <h2>Inbox</h2>
        <div id="ed"><p class="placeholder">Select a task and start an episode to begin.</p></div>
      </div>
      <div class="card">
        <h2>Action</h2>
        <div class="ctrls">
          <div>
            <label>Action Type</label>
            <select id="at" onchange="tog()">
              <option value="classify">CLASSIFY</option>
              <option value="respond">RESPOND</option>
              <option value="escalate">ESCALATE</option>
              <option value="archive">ARCHIVE</option>
              <option value="skip">SKIP</option>
              <option value="flag">FLAG</option>
            </select>
          </div>
          <div id="cf" class="g3">
            <div>
              <label>Category</label>
              <select id="cat">
                <option value="spam">spam</option>
                <option value="sales_inquiry">sales_inquiry</option>
                <option value="customer_complaint">customer_complaint</option>
                <option value="technical_support">technical_support</option>
                <option value="billing">billing</option>
                <option value="internal">internal</option>
                <option value="legal">legal</option>
                <option value="press">press</option>
                <option value="partnership">partnership</option>
                <option value="other">other</option>
              </select>
            </div>
            <div>
              <label>Priority</label>
              <select id="pri">
                <option value="urgent">urgent</option>
                <option value="high">high</option>
                <option value="medium">medium</option>
                <option value="low">low</option>
                <option value="ignore">ignore</option>
              </select>
            </div>
            <div>
              <label>Department</label>
              <select id="dep">
                <option value="support">support</option>
                <option value="sales">sales</option>
                <option value="engineering">engineering</option>
                <option value="finance">finance</option>
                <option value="legal">legal</option>
                <option value="executive">executive</option>
                <option value="marketing">marketing</option>
                <option value="ignore">ignore</option>
              </select>
            </div>
          </div>
          <div id="rf" style="display:none">
            <label>Draft Response</label>
            <textarea id="dr" placeholder="Write a professional response..."></textarea>
          </div>
          <div id="xf" style="display:none">
            <label>Context / Reason</label>
            <input id="xr" type="text" placeholder="Why is this being escalated or flagged?">
          </div>
          <div>
            <label>Reasoning</label>
            <input id="rsn" type="text" placeholder="Explain your classification logic...">
          </div>
          <button onclick="act()">Submit Action</button>
        </div>
      </div>
    </div>
    <div>
      <div class="card mb">
        <h2>Control</h2>
        <div class="stats">
          <div class="st"><div class="sv" id="sc">-</div><div class="sl">Score</div></div>
          <div class="st"><div class="sv" id="sp">0</div><div class="sl">Processed</div></div>
          <div class="st"><div class="sv" id="sr">-</div><div class="sl">Remaining</div></div>
        </div>
        <div class="prog mb"><div class="pb" id="pb" style="width:0%"></div></div>
        <div class="row">
          <select id="ts" style="flex:1">
            <option value="task_1_easy">Task 1: Easy (5 emails)</option>
            <option value="task_2_medium">Task 2: Medium (8 emails)</option>
            <option value="task_3_hard">Task 3: Hard Crisis (10 emails)</option>
          </select>
          <button class="grn" onclick="go()">Start</button>
        </div>
        <div style="margin-top:18px;">
          <label>LLM Model</label>
          <input id="lm" type="text" value="gpt-4o-mini" placeholder="gpt-4o-mini">
        </div>
        <div class="row" style="margin-top:18px;">
          <button class="sec" onclick="bl()">Rule Baseline</button>
          <button class="sec" onclick="llmBl()">LLM Baseline</button>
        </div>
      </div>
      <div class="card">
        <h2>Activity Log</h2>
        <div class="log" id="log">
          <div class="le i" style="opacity:0.6;border:none;">[System] Ready for triage operations...</div>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
let active = false;
let total = 0;

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || ('HTTP ' + response.status));
  return data;
}

function lg(msg, tone = 'i') {
  const el = document.getElementById('log');
  const line = document.createElement('div');
  line.className = 'le ' + tone;
  line.textContent = '[' + new Date().toLocaleTimeString() + '] ' + msg;
  el.prepend(line);
}

function toneForScore(score) {
  if (score >= 0.7) return 'r';
  if (score >= 0.4) return 'w';
  return 'e';
}

function reportBaseline(prefix, data) {
  for (const [, result] of Object.entries(data.results)) {
    lg(prefix + ' ' + result.task_name + ': ' + result.score.toFixed(3) + ' [' + (result.passed ? 'pass' : 'fail') + ']', result.passed ? 'r' : 'e');
  }
  lg(prefix + ' mean score: ' + data.summary.mean_score.toFixed(3) + ' | Passed: ' + data.summary.tasks_passed + '/' + data.summary.tasks_run, data.summary.tasks_passed === data.summary.tasks_run ? 'r' : 'w');
  if (data.summary.parse_fallbacks) lg(prefix + ' fallback actions used: ' + data.summary.parse_fallbacks, 'w');
  if (data.runtime_seconds != null) lg(prefix + ' runtime: ' + Number(data.runtime_seconds).toFixed(2) + 's', 'i');
}

(async () => {
  const envBadge = document.getElementById('env-badge');
  const typeBadge = document.getElementById('type-badge');
  try {
    const data = await requestJson('/health');
    envBadge.textContent = data.environment + ' v' + data.version;
    typeBadge.textContent = data.llm_baseline_available ? 'LLM Baseline Ready' : 'Rule Baseline Only';
    if (data.default_llm_model) document.getElementById('lm').value = data.default_llm_model;
  } catch (error) {
    envBadge.textContent = 'Offline';
    typeBadge.textContent = 'Unavailable';
    lg('Health check failed: ' + error, 'e');
  }
})();

function tog() {
  const value = document.getElementById('at').value;
  document.getElementById('cf').style.display = value === 'classify' ? 'grid' : 'none';
  document.getElementById('rf').style.display = value === 'respond' ? 'block' : 'none';
  document.getElementById('xf').style.display = ['escalate', 'flag'].includes(value) ? 'block' : 'none';
}

async function go() {
  const taskId = document.getElementById('ts').value;
  try {
    const data = await requestJson('/reset', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task_id: taskId, seed: 42})
    });
    active = true;
    total = data.observation.total_emails || 0;
    ui(data);
    lg('Mission started: ' + taskId, 'i');
  } catch (error) {
    lg('Error: ' + error, 'e');
  }
}

async function act() {
  if (!active) {
    lg('Start an episode first', 'w');
    return;
  }

  const actionType = document.getElementById('at').value;
  const action = {action_type: actionType};

  if (actionType === 'classify') {
    action.category = document.getElementById('cat').value;
    action.priority = document.getElementById('pri').value;
    action.department = document.getElementById('dep').value;
  }
  if (actionType === 'respond') action.draft_response = document.getElementById('dr').value;
  if (['escalate', 'flag'].includes(actionType)) {
    action.escalation_reason = document.getElementById('xr').value;
    action.flag_reason = document.getElementById('xr').value;
  }

  const reasoning = document.getElementById('rsn').value;
  if (reasoning) action.reasoning = reasoning;

  try {
    const data = await requestJson('/step', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action})
    });
    ui(data);
    const score = data.observation.partial_score;
    lg(actionType.toUpperCase() + ' -> ' + score.toFixed(3) + ' | ' + (data.observation.action_feedback || '').substring(0, 80), toneForScore(score));
    if (data.done) {
      const finalScore = data.observation.cumulative_score;
      lg('Episode complete. Final score: ' + finalScore.toFixed(3), toneForScore(finalScore));
      active = false;
    }
  } catch (error) {
    lg('Error: ' + error, 'e');
  }
}

async function bl() {
  const taskId = document.getElementById('ts').value;
  lg('Executing rule baseline on ' + taskId + '...', 'i');
  try {
    const data = await requestJson('/baseline', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task_id: taskId})
    });
    reportBaseline('Rule baseline', data);
  } catch (error) {
    lg('Baseline error: ' + error, 'e');
  }
}

async function llmBl() {
  const taskId = document.getElementById('ts').value;
  const model = 'gpt-4o-mini';
  lg('Executing LLM baseline on ' + taskId + ' with ' + model + '...', 'i');
  try {
    const data = await requestJson('/baseline/llm', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task_id: taskId, model})
    });
    reportBaseline('LLM baseline', data);
  } catch (error) {
    lg('LLM baseline error: ' + error, 'e');
  }
}

function ui(data) {
  const observation = data.observation;
  document.getElementById('sc').textContent = observation.cumulative_score != null ? observation.cumulative_score.toFixed(3) : '-';
  document.getElementById('sp').textContent = observation.emails_processed ?? 0;
  document.getElementById('sr').textContent = observation.emails_remaining ?? '-';

  if (total > 0) document.getElementById('pb').style.width = ((observation.emails_processed || 0) / total * 100) + '%';

  const email = observation.current_email;
  const el = document.getElementById('ed');
  if (email) {
    el.innerHTML = `<div class="email-box">
      <div class="ef">From: ${email.sender} <span style="color:var(--muted);font-weight:400;margin-left:8px;">${(email.timestamp || '').slice(0, 16).replace('T', ' ')}</span> <span class="badge" style="float:right;background:rgba(255,255,255,0.1);box-shadow:none;">Thread: ${email.thread_length || 1}</span></div>
      <div class="es">${email.subject}</div>
      <div class="eb">${email.body}</div>
      ${email.has_attachments ? '<div class="att">Attachments</div>' : ''}
    </div><div style="font-size:0.8rem;color:var(--muted);text-align:right;margin-top:8px;">Email ${(observation.email_index || 0) + 1} of ${total || '?'}</div>`;
  } else if (data.done) {
    el.innerHTML = '<div class="email-box" style="text-align:center;padding:60px 40px;"><div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:var(--text);margin-bottom:12px;">Complete</div><div style="font-size:1.5rem;font-weight:800;color:var(--text);">Inbox Zero</div><div style="color:var(--muted);font-size:0.9rem;margin-top:8px;">All emails successfully triaged.</div></div>';
  }
}
</script>
</body>
</html>"""
