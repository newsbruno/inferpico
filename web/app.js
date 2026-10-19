'use strict';
const $ = id => document.getElementById(id);
let mode = 'demo';
let report = null;
let running = false;
const fields = ['endpoint', 'model', 'prompt', 'count', 'concurrency', 'timeout', 'max_tokens', 'input_rate', 'output_rate', 'token_parameter'];

function markStale(message = 'Settings have changed. These results belong to the previous completed check.') {
  if (!report) return;
  $('result-state').textContent = message;
  $('result-state').hidden = false;
}
function setMode(next) {
  if (running) return;
  const changed = mode !== next;
  mode = next;
  const live = mode === 'live';
  $('demo-mode').setAttribute('aria-pressed', String(!live));
  $('live-mode').setAttribute('aria-pressed', String(live));
  $('live-fields').hidden = !live;
  $('consent-wrap').hidden = !live;
  $('preflight').hidden = !live;
  $('demo-note').hidden = live;
  ['model', 'endpoint'].forEach(id => {
    $(id).required = live;
    $(id).disabled = !live;
  });
  $('consent').checked = false;
  $('consent').required = live;
  $('run-label').textContent = live ? 'Run my check' : 'Run the demo';
  $('run-hint').textContent = live ? 'Only your chosen endpoint receives the prompt. No retries.' : 'No account. No provider calls. Nothing saved.';
  $('prompt-hint').textContent = live ? 'Use a non-sensitive test prompt. Reports exclude prompt and response text.' : 'Demo results are fixed synthetic data; changing settings does not simulate model behavior.';
  updatePreflight();
  if (changed) {
    markStale();
    $('error').hidden = true;
    $('status').textContent = live ? 'Real request mode selected. Review your endpoint, limits and consent before each run.' : 'Synthetic demo mode selected. No provider requests will be made.';
  }
}
function updatePreflight() {
  $('preflight').textContent = `${$('count').value || '?'} requests, at most ${$('max_tokens').value || '?'} output tokens each, to ${$('endpoint').value || 'your endpoint above'}. Cost cannot be known in advance; providers may bill other token categories or failed requests. Review your provider budget before proceeding.`;
}
fields.forEach(id => $(id).addEventListener('input', () => {
  $('consent').checked = false;
  $('prompt').setCustomValidity('');
  $('model').setCustomValidity('');
  updatePreflight();
  markStale();
}));
// Expand advanced fields before the browser tries to focus an invalid input.
$('check-form').addEventListener('invalid', event => {
  const details = event.target.closest('details');
  if (details) details.open = true;
}, true);
$('demo-mode').onclick = () => setMode('demo');
$('live-mode').onclick = () => setMode('live');
const latency = value => value === null ? 'Unknown' : value >= 1000 ? (value / 1000).toFixed(2) + ' s' : Math.round(value) + ' ms';
const money = value => value === null ? 'Unknown' : value > 0 && value < 0.000001 ? '<$0.000001' : '$' + value.toFixed(6);
function failureHint(error) {
  if (error === 'http_401' || error === 'http_403') return 'Authorization failed. Check the key set in your terminal and provider permissions.';
  if (error === 'http_404') return 'Endpoint or model not found. Check the full chat completions URL and exact model ID.';
  if (error === 'http_429') return 'Provider limit reached. Check rate limits, quota and account balance before another run.';
  if (error === 'http_400' || error === 'http_422') return 'Provider rejected the request. Check the model ID and output limit parameter in Rates & request limits.';
  if (error === 'timeout') return 'A network operation timed out. The provider may still finish or bill the request.';
  if (error === 'connection_or_tls_error') return 'Connection failed. Check the endpoint, local model server and TLS setup.';
  if (error === 'invalid_json' || error === 'invalid_response') return 'The endpoint did not return a supported chat completions response.';
  if (error === 'response_too_large') return 'The response exceeded the local size limit. Try a smaller output token limit.';
  if (error && error.startsWith('http_5')) return 'Provider server error. Check provider status before another run.';
  return 'A request failed. Check endpoint compatibility and the local terminal before another run.';
}
function render(data) {
  const s = data.summary;
  $('result-state').hidden = true;
  $('mode-label').textContent = data.synthetic ? 'SYNTHETIC DEMO' : 'LIVE CHECK';
  $('success-label').textContent = `${s.successful} successful · ${s.failed} failed`;
  $('p50').textContent = latency(s.p50_ms);
  $('p95').textContent = latency(s.p95_ms);
  $('cost').textContent = money(s.estimated_total_cost_usd);
  $('cost-note').textContent = s.estimated_total_cost_usd !== null ? `USD · ${data.synthetic ? 'illustrative' : 'your'} rates × reported usage` : s.known_usage_cost_usd !== null ? `Known-usage subtotal: ${money(s.known_usage_cost_usd)}; total unknown` : 'Enter rates; provider must return usage';
  $('coverage').textContent = `${s.usage_known_requests} / ${s.attempted}`;
  $('sample-note').textContent = s.successful === 0 ? 'No successful responses. Latency percentiles are unknown. Failed requests may still be billed; inspect each result below.' : `${data.synthetic ? 'Illustrative only. ' : ''}Small sample: ${s.successful} successful requests. p95 ${s.successful < 20 ? 'is the slowest success here' : 'uses nearest rank'}. This is a quick check, not a production load test.`;
  $('request-rows').replaceChildren();
  data.requests.forEach(r => {
    const tr = document.createElement('tr');
    [r.request, r.ok ? 'Success' : r.error || 'request_failed', latency(r.latency_ms), `${r.input_tokens ?? '?'} / ${r.output_tokens ?? '?'}`].forEach(value => {
      const td = document.createElement('td'); td.textContent = value; tr.append(td);
    });
    $('request-rows').append(tr);
  });
  const errors = [...new Set(data.requests.filter(r => !r.ok).map(r => r.error))];
  $('failure-note').textContent = errors.map(failureHint).filter((value, index, hints) => hints.indexOf(value) === index).join(' ');
  $('failure-note').hidden = errors.length === 0;
  $('notes').replaceChildren();
  data.notes.forEach(note => { const li = document.createElement('li'); li.textContent = note; $('notes').append(li); });
  report = data;
  $('result').hidden = false;
  $('status').textContent = `${data.synthetic ? 'Synthetic demo' : 'Check'} complete: ${s.successful} successful, ${s.failed} failed. ${s.estimated_total_cost_usd === null ? 'Total cost unknown.' : `Estimated cost ${money(s.estimated_total_cost_usd)}.`}`;
}
$('check-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (running) return;
  $('prompt').setCustomValidity($('prompt').value.trim() ? '' : 'Enter a non-empty prompt.');
  $('model').setCustomValidity(mode !== 'live' || $('model').value.trim() ? '' : 'Enter a model ID.');
  if (!$('check-form').reportValidity()) return;
  $('error').hidden = true;
  const body = {mode, confirmed: $('consent').checked};
  fields.forEach(id => body[id] = $(id).value);
  if (mode === 'demo') {
    body.model = 'synthetic-model';
    if (body.input_rate === '') body.input_rate = 0.5;
    if (body.output_rate === '') body.output_rate = 2;
  }
  // Consent authorizes exactly this submission, including a failed submission.
  $('consent').checked = false;
  running = true;
  const controls = [...document.querySelectorAll('button,input,textarea,select')].map(el => [el, el.disabled]);
  controls.forEach(([el]) => el.disabled = true);
  $('empty').hidden = true; $('result').hidden = true; $('busy').hidden = false;
  $('busy-title').textContent = mode === 'demo' ? 'Preparing the demo report.' : 'Measuring the full response.';
  $('busy-copy').textContent = mode === 'demo' ? 'These synthetic values illustrate the report. No provider requests are made.' : "Keep this tab open. Closing it doesn't cancel requests already sent. No automatic retries.";
  $('results-panel').setAttribute('aria-busy', 'true');
  $('status').textContent = mode === 'demo' ? 'Preparing the synthetic demo report.' : 'Check running. Provider requests may be billed. Keep this tab open.';
  let completed = false;
  try {
    const response = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json','X-Inferpico-Token':document.querySelector('meta[name="inferpico-token"]').content}, body:JSON.stringify(body)});
    let data;
    try { data = await response.json(); } catch {
      throw new Error('The local app returned an unreadable response. Check your terminal. Requests already sent may still be billed.');
    }
    if (!response.ok) throw new Error(data.error || 'Could not run this check. Check your terminal before another run.');
    render(data);
    completed = true;
  } catch (error) {
    $('error').textContent = error instanceof TypeError ? 'Connection to the local app was lost. Check your terminal before another run. Requests already sent may still finish or be billed.' : error.message || 'Could not run this check. Check your terminal before another run.';
    $('error').hidden = false;
    $('status').textContent = 'Check failed. Review the error before trying again.';
    if (report) {
      markStale('The latest check failed. These results belong to the previous completed check.');
      $('result').hidden = false;
    } else $('empty').hidden = false;
  } finally {
    $('busy').hidden = true;
    $('results-panel').setAttribute('aria-busy', 'false');
    controls.forEach(([el, disabled]) => el.disabled = disabled);
    running = false;
    (completed ? $('result-title') : $('error')).focus();
  }
});
$('download').onclick = () => {
  if (!report) return;
  const blob = new Blob([JSON.stringify(report, null, 2) + '\n'], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'inferpico-check.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
setMode('demo');
