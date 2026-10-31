const $ = id => document.getElementById(id);
let selectedRun = null;
let selectedEvent = null;
const pretty = value => JSON.stringify(value, null, 2);
function node(tag, text, className) { const element = document.createElement(tag); if(text !== undefined) element.textContent = text; if(className) element.className = className; return element; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const payload = await response.json(); if(!response.ok) throw new Error(payload.error); return payload;
}
async function action(operation) {
  $('notice').textContent = 'Working...'; document.querySelectorAll('button').forEach(button => button.disabled = true);
  try { await operation(); $('notice').textContent = ''; } catch(error) { $('notice').textContent = error.message; }
  finally { document.querySelectorAll('button').forEach(button => button.disabled = false); }
}
async function library() {
  const runs = await api('/api/runs'); $('runs').replaceChildren();
  for(const run of runs) { const button = node('button',run.name,run.id === selectedRun?.id ? 'active' : ''); button.append(node('small',`${run.policy.toUpperCase()} / ${run.status} / ${run.id.slice(0,8)}`)); button.onclick = () => action(() => openRun(run.id)); $('runs').append(button); }
  if(!runs.length) $('runs').append(node('p','No recordings yet.','muted'));
}
function selectEvent(event) { selectedEvent = event.seq; $('event-title').textContent = `${event.seq}. ${event.name}`; $('detail').textContent = pretty(event); drawEvents(); }
function drawEvents() {
  $('events').replaceChildren(); const query = $('search').value.toLowerCase();
  const start = Math.min(...selectedRun.events.map(event => event.start_ns));
  const extent = Math.max(1,...selectedRun.events.map(event => event.start_ns-start+event.duration_ns));
  for(const event of selectedRun.events.filter(event => pretty(event).toLowerCase().includes(query))) {
    const row = node('button',undefined,`event ${selectedEvent === event.seq ? 'selected' : ''}`);
    row.append(node('span',String(event.seq).padStart(2,'0'),'muted'));
    const label = node('span',event.name); label.append(node('small',`${event.kind} / ${event.origin} / ${event.status}`,event.origin)); row.append(label);
    const track = node('div',undefined,'track'); const bar = node('div',undefined,'bar');
    // Width represents elapsed duration on the shared wall-clock axis.
    bar.style.width = `${Math.max(.6,event.duration_ns/extent*100)}%`; bar.style.marginLeft = `${(event.start_ns-start)/extent*100}%`; track.append(bar); row.append(track,node('span',`${(event.duration_ns/1e6).toFixed(2)} ms`));
    row.onclick = () => selectEvent(event); $('events').append(row);
  }
  if(!$('events').children.length) $('events').append(node('p','No matching events.','muted'));
}
function targets() {
  $('target').replaceChildren(); const checkpoint = Number($('checkpoint').value);
  const nextCheckpoint = selectedRun.events.find(event => event.kind === 'checkpoint' && event.seq > checkpoint)?.seq ?? Infinity;
  for(const event of selectedRun.events.filter(event => ['tool','model'].includes(event.kind) && event.seq > checkpoint && event.seq < nextCheckpoint)) { const option = node('option',`${event.seq}. ${event.name}`); option.value=event.seq; $('target').append(option); }
  $('fork').disabled = !$('target').children.length;
}
async function openRun(id, keepComparison=false) {
  selectedRun = await api(`/api/runs/${encodeURIComponent(id)}`); selectedEvent=null;
  $('empty').hidden=true; $('trace').hidden=false; if(!keepComparison) $('comparison').hidden=true;
  $('title').textContent=selectedRun.name; $('metadata').textContent=`${selectedRun.id} / ${selectedRun.policy} / ${selectedRun.status}`;
  $('metrics').replaceChildren();
  const failed=selectedRun.events.filter(event=>['error','cancelled'].includes(event.status)).length;
  for(const [value,label] of [[selectedRun.events.length,'EVENTS'],[failed,'ERRORS / CANCELLATIONS'],[selectedRun.policy.toUpperCase(),'EXECUTION POLICY']]) { const card=node('div',undefined,'metric');card.append(node('b',String(value)),node('span',label));$('metrics').append(card); }
  $('checkpoint').replaceChildren();
  for(const event of selectedRun.events.filter(event=>event.kind==='checkpoint')) { const option=node('option',`${event.seq}. ${event.name}`);option.value=event.seq;$('checkpoint').append(option); }
  targets(); drawEvents(); if(selectedRun.events.length) selectEvent(selectedRun.events.find(event=>event.kind==='tool')||selectedRun.events[0]);
  await library();
}
function showComparison(comparison) {
  $('comparison').hidden=false; $('diff').replaceChildren();
  $('diff-title').textContent=comparison.first_divergence ? `First divergence: original event ${comparison.first_divergence.original_event}` : 'Replay matches every recorded outcome';
  for(const change of comparison.changes) { const row=node('div',undefined,'diffrow');for(const [label,event] of [['ORIGINAL',change.before],['REVISED',change.after]]) {const panel=node('article');panel.append(node('div',label,'eyebrow'),node('pre',pretty(event)));row.append(panel);} $('diff').append(row); }
}
$('demo').onclick=()=>action(async()=>{const run=await api('/api/demo',{});await openRun(run.id);});
$('refresh').onclick=()=>action(library);
$('search').oninput=()=>{if(selectedRun)drawEvents();};
$('checkpoint').onchange=targets;
$('fork').onclick=()=>action(async()=>{const original=selectedRun.id;const response=JSON.parse($('response').value);const run=await api('/api/fork',{run_id:original,event:Number($('target').value),response});await openRun(run.id,true);showComparison(await api(`/api/compare?left=${original}&right=${run.id}`));$('comparison').scrollIntoView({block:'start'});});
$('replay').onclick=()=>action(async()=>{const original=selectedRun.id;const run=await api('/api/replay',{run_id:original});await openRun(run.id,true);showComparison(await api(`/api/compare?left=${original}&right=${run.id}`));});
action(async()=>{await library();const runs=await api('/api/runs');if(runs.length)await openRun(runs[0].id);});
