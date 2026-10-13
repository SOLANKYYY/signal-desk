'use strict';
(() => {
  const el = id => document.getElementById(id);
  let activities = [], selected = null, current = null, requestVersion = 0;
  const date = value => value ? new Date(value).toLocaleString() : 'Not recorded';
  const message = (text, failed = false) => {
    el('replica-message').textContent = text;
    el('replica-message').className = failed ? 'health-warning' : 'muted';
  };
  const cell = value => esc(value == null ? 'Not recorded' : value);
  function cards() {
    el('replica-activities').innerHTML = activities.map(a => `<button class="replica-activity ${a.id === selected ? 'selected' : ''}" data-replica-id="${esc(a.id)}" aria-pressed="${a.id === selected}"><strong>${esc(a.title)}</strong><span>${a.run ? 'Result uploaded' : 'Awaiting upload'}</span></button>`).join('');
  }
  function render(run) {
    current = run;
    if (!run) {
      el('replica-result').innerHTML = '<div class="panel empty-state"><h2>No result uploaded yet</h2><p>Run this activity on your laptop, then select its generated JSON file above. No example results are used.</p></div>';
      return;
    }
    const s = run.summary;
    const healthKnown = s.members.every(m => typeof m.health === 'number');
    const healthy = s.members.filter(m => m.health === 1).length;
    const readHosts = [...new Set(s.reads.filter(r => r.servedBy).map(r => r.servedBy))];
    const metric = (label, value, note) => `<article><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></article>`;
    el('replica-result').innerHTML = `
      <div class="replica-result-heading"><div><h2>${esc(s.title)}</h2><p class="muted">Recorded: ${esc(date(s.recordedAt))}<br>Uploaded: ${esc(date(run.uploadedAt))}</p></div><button class="secondary" id="replica-download">Download evidence JSON</button></div>
      <div class="metrics replica-metrics">${metric('Replica set', s.setName || 'Not recorded', 'From the uploaded experiment')}${metric('Members recorded', s.members.length, 'Includes any arbiter')}${metric('Healthy at last snapshot', healthKnown ? `${healthy} / ${s.members.length}` : 'Not recorded', 'Historical health, not live status')}${metric('Evidence steps', s.stepCount, 'Commands and recorded replies')}</div>
      <div class="replica-members">${s.members.map(m => `<article class="panel replica-member ${m.state === 'PRIMARY' ? 'replica-primary' : ''}"><span class="chip">${esc(m.state)}</span><h3>${esc(m.name)}</h3><p>Priority: <strong>${cell(m.priority)}</strong><br>Recorded health: <strong>${m.health === 1 ? 'Healthy' : m.health === 0 ? 'Unavailable' : 'Not recorded'}</strong></p><p class="muted">${m.state === 'ARBITER' ? 'Votes in elections. Stores no records and cannot become primary.' : m.state === 'PRIMARY' ? 'Primary at this snapshot; accepts writes.' : m.state === 'SECONDARY' ? 'Secondary at this snapshot; replicates the primary’s data.' : 'See the command evidence for this member’s state.'}</p></article>`).join('')}</div>
      ${s.replication.length ? `<section class="panel replica-section"><h3>Did the document reach each member?</h3>${s.replication.map(r => `<p><strong>${esc(r.member)}</strong> — ${r.found ? 'Document found' : 'Document not found'}</p>`).join('')}<p class="muted">Based on the script’s direct reads of the inserted document.</p></section>` : ''}
      ${s.prediction ? `<section class="panel replica-section"><h3>Election prediction: ${s.prediction.correct ? 'correct' : 'did not match'}</h3><p>Predicted: <strong>${esc(s.prediction.predicted)}</strong><br>Elected: <strong>${esc(s.prediction.elected)}</strong></p><p class="muted">Comparison calculated from the recorded predicted and elected members.</p></section>` : ''}
      ${s.reads.length ? `<section class="panel replica-section"><h3>Client reconnection</h3><p><strong>${s.readSuccess} successful reads · ${s.readFailure} failed reads</strong></p><p>Members serving reads: ${readHosts.map(esc).join(' → ')}</p><div class="replica-read-strip" aria-label="Read results in chronological order">${s.reads.map(r => `<span class="${r.error || !r.servedBy ? 'read-failed' : 'read-ok'}" title="${esc(date(r.at))}: ${esc(r.error || r.servedBy || 'Failed read')}"></span>`).join('')}</div><p class="muted">Each mark is one recorded read. Details are available below.</p><details><summary>Read-by-read evidence</summary><div class="table-wrap"><table><thead><tr><th>Time</th><th>Served by</th><th>Result</th></tr></thead><tbody>${s.reads.map(r => `<tr><td>${esc(date(r.at))}</td><td>${cell(r.servedBy)}</td><td>${esc(r.error || (r.servedBy ? 'Success' : 'Failed read'))}</td></tr>`).join('')}</tbody></table></div></details></section>` : ''}
      <section class="panel replica-section"><h3>Recorded member changes</h3><p class="muted">Consecutive identical states are combined. This timeline includes only snapshots captured by the script.</p><ol class="replica-timeline">${s.timeline.map(t => `<li><time>${esc(date(t.at))}</time><strong>${t.primary ? `${esc(t.primary)} is primary` : 'No primary recorded'}</strong><p>${Object.entries(t.states).map(([name, state]) => `${esc(name)}: ${esc(state)}`).join(' · ')}</p><small>${esc(t.step)}</small></li>`).join('')}</ol></section>
      ${s.issues.length ? `<section class="panel replica-section"><h3>Recorded command errors</h3><p class="muted">Some errors may have been handled by later steps, such as setting an explicit write concern before adding an arbiter.</p>${s.issues.map(i => `<p><strong>${esc(i.step)}</strong><br>${esc(i.message)}</p>`).join('')}</section>` : ''}
      <section class="panel replica-section"><h3>Command evidence</h3><p class="muted">Uploaded evidence is user supplied. It is not independently verified against a running cluster.</p>${run.document.steps.map(step => `<details class="replica-step"><summary>${esc(step.step)} · ${esc(date(typeof step.executedAt === 'object' ? step.executedAt.$date : step.executedAt))}</summary><pre>${esc(JSON.stringify({command: step.command, result: step.result}, null, 2))}</pre></details>`).join('')}<details class="replica-step"><summary>Technical details</summary><p>Script: <code>${esc(s.script)}</code><br>Collection: <code>replica_lab_runs</code><br>Evidence SHA-256: <code>${esc(run.sha256)}</code></p></details></section>`;
    el('replica-download').onclick = () => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(current.document, null, 2)], {type: 'application/json'}));
      const a = document.createElement('a'); a.href = url; a.download = current.summary.script.replace(/\.py$/, '.json'); a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
  }
  async function select(id) {
    selected = id; cards();
    const version = ++requestVersion;
    current = null;
    if (!activities.find(a => a.id === id)?.run) { render(null); return; }
    el('replica-result').innerHTML = '<p class="empty-state">Loading recorded evidence…</p>';
    try {
      const run = await api('/api/replica-lab/' + encodeURIComponent(id));
      if (version === requestVersion) render(run);
    } catch (e) {
      if (version === requestVersion) { el('replica-result').textContent = 'Unable to load this result. Use Reload saved results to retry.'; message(e.message, true); }
    }
  }
  window.replicaLabLoad = async () => {
    try {
      const data = await api('/api/replica-lab');
      activities = data.activities;
      await select(selected || activities.find(a => a.run)?.id || activities[0].id);
    } catch (e) { message(e.message, true); el('replica-result').textContent = 'Saved results are unavailable. Check your Signal Desk database connection and try Reload saved results.'; }
  };
  el('replica-refresh').onclick = () => window.replicaLabLoad();
  el('replica-activities').onclick = e => { const b = e.target.closest('[data-replica-id]'); if (b) select(b.dataset.replicaId); };
  el('replica-upload-form').onsubmit = async e => {
    e.preventDefault();
    const files = [...el('replica-files').files];
    if (!files.length || files.length > 4) { message('Choose between one and four Chapter 8 JSON files.', true); return; }
    const button = el('replica-upload-button'); button.disabled = true;
    const saved = [], failed = [];
    try {
      for (const file of files) {
        try {
          if (file.size > 1024 * 1024) throw Error('File exceeds 1 MiB.');
          message('Uploading ' + file.name + '…');
          const doc = JSON.parse(await file.text());
          const result = await api('/api/replica-lab/import', doc);
          selected = result.id; saved.push(file.name);
        } catch (err) { failed.push(file.name + ': ' + err.message); }
      }
      await window.replicaLabLoad();
      message(`${saved.length} result file(s) saved.${failed.length ? ' Could not save: ' + failed.join('; ') : ' Select an activity to explore its evidence.'}`, failed.length > 0);
      if (!failed.length) el('replica-files').value = '';
    } finally { button.disabled = false; }
  };
})();
