'use strict';
const $ = id => document.getElementById(id);
let mode = 'demo';
let report = null;
function setMode(next) {
  mode = next;
  const live = mode === 'live';
  $('demo-mode').setAttribute('aria-pressed', String(!live));
  $('live-mode').setAttribute('aria-pressed', String(live));
  $('live-fields').hidden = !live;
  $('consent-wrap').hidden = !live;
  $('preflight').hidden = !live;
  updatePreflight();
  $('demo-note').hidden = live;
  $('model').required = live;
  $('endpoint').required = live;
  $('consent').checked = false;
  $('consent').required = live;
  $('run-button').textContent = live ? 'Run my check ↗' : 'Run the demo ↗';
  $('run-hint').textContent = live ? 'Only your chosen endpoint receives the prompt. No retries.' : 'No account. No network calls. Nothing saved.';
  $('prompt-hint').textContent = live ? 'Use a non-sensitive test prompt. Reports exclude prompt and response text.' : 'Demo results are fixed synthetic data; changing settings does not simulate model behavior.';
}
function updatePreflight() {
  $('preflight').textContent = `${$('count').value || '?'} requests to ${$('endpoint').value || 'your endpoint above'}. Cost cannot be known in advance; token usage varies. Review your provider budget before proceeding.`;
}
['count', 'endpoint'].forEach(id => $(id).addEventListener('input', () => { $('consent').checked = false; updatePreflight(); }));
['prompt','model','max_tokens','concurrency','timeout','token_parameter'].forEach(id => $(id).addEventListener('input', () => { $('consent').checked = false; }));
$('demo-mode').onclick = () => setMode('demo');
$('live-mode').onclick = () => setMode('live');
const latency = value => value === null ? 'Unknown' : value >= 1000 ? (value / 1000).toFixed(2) + ' s' : Math.round(value) + ' ms';
const money = value => value === null ? 'Unknown' : '$' + value.toFixed(6);
function render(data) {
  report = data;
  const s = data.summary;
  $('mode-label').textContent = data.synthetic ? 'SYNTHETIC DEMO' : 'LIVE CHECK';
  $('success-label').textContent = `${s.successful} successful · ${s.failed} failed`;
  $('p50').textContent = latency(s.p50_ms);
  $('p95').textContent = latency(s.p95_ms);
  $('cost').textContent = money(s.estimated_total_cost_usd);
  $('cost-note').textContent = s.estimated_total_cost_usd !== null ? 'USD · your rates × reported usage' : s.known_usage_cost_usd !== null ? `Known-usage subtotal: ${money(s.known_usage_cost_usd)}; total unknown` : 'Enter rates; provider must return usage';
  $('coverage').textContent = `${s.usage_known_requests} / ${s.attempted}`;
  $('sample-note').textContent = `${data.synthetic ? 'Illustrative only. ' : ''}Small sample: ${s.successful} successful requests. p95 ${s.successful < 20 ? 'is the slowest success here' : 'uses nearest rank'}. This is a quick check, not a production load test.`;
  $('request-rows').replaceChildren();
  data.requests.forEach(r => {
    const tr = document.createElement('tr');
    [r.request, r.ok ? 'Success' : r.error, latency(r.latency_ms), `${r.input_tokens ?? '?'} / ${r.output_tokens ?? '?'}`].forEach(value => {
      const td = document.createElement('td'); td.textContent = value; tr.append(td);
    });
    $('request-rows').append(tr);
  });
  $('notes').replaceChildren();
  data.notes.forEach(note => { const li = document.createElement('li'); li.textContent = note; $('notes').append(li); });
  $('result').hidden = false;
}
$('check-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('error').hidden = true;
  const body = {mode, confirmed: $('consent').checked};
  ['endpoint','model','prompt','count','concurrency','timeout','max_tokens','input_rate','output_rate','token_parameter'].forEach(id => body[id] = $(id).value);
  if (mode === 'demo') {
    body.model = 'synthetic-model';
    if (body.input_rate === '') body.input_rate = 0.5;
    if (body.output_rate === '') body.output_rate = 2;
  }
  const controls = [...document.querySelectorAll('button,input,textarea,select')];
  controls.forEach(el => el.disabled = true);
  $('empty').hidden = true; $('result').hidden = true; $('busy').hidden = false;
  try {
    const response = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json','X-Inferpico-Token':document.querySelector('meta[name="inferpico-token"]').content}, body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not run this check.');
    render(data);
  } catch (error) {
    $('error').textContent = error.message || 'Connection lost. Check your terminal before trying again.';
    $('error').hidden = false;
    if (report) $('result').hidden = false; else $('empty').hidden = false;
  } finally {
    $('busy').hidden = true;
    controls.forEach(el => el.disabled = false);
  }
});
$('download').onclick = () => {
  if (!report) return;
  const blob = new Blob([JSON.stringify(report, null, 2) + '\n'], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'inferpico-check.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
