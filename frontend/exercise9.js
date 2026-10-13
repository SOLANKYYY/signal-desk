'use strict';
(() => {
  const el = id => document.getElementById(id);
  let runs = {}, view = 'latency', loading = false;
  const num = n => Number(n).toLocaleString(undefined, {maximumFractionDigits: 3});
  const mode = w => w === 3 ? 'All 3 (w:3)' : `w:${w}`;
  const when = value => new Date(value).toLocaleString();
  const names = {baseline:'Healthy baseline','one-secondary-offline':'One secondary disconnected','first-recovery':'First reconnect & catch-up','two-secondaries-offline':'Both secondaries disconnected','final-recovery':'Final reconnect & catch-up'};
  function message(text, failed=false) { el('ex9-message').textContent=text; el('ex9-message').className=failed?'health-warning':'muted'; }
  function empty(title) { return `<div class="panel replica-section"><h2>${title}</h2><p class="empty-state">Awaiting your measured results. Run the Docker kit and upload the generated JSON. No sample measurements are shown.</p></div>`; }
  function heading(run, title) {return `<div class="replica-result-heading"><div><h2>${title}</h2><p class="muted">Recorded ${esc(when(run.summary.finishedAt))} · Uploaded ${esc(when(run.uploadedAt))}</p></div><button class="secondary ex9-no-print" data-ex9-download="${esc(run._id)}">Download evidence JSON</button></div>`;}
  function render() {
    const count=Object.keys(runs).length;
    el('ex9-progress').textContent=`${count} of 2 experiment results uploaded${count===2?' · Ready to prepare your submission':''}`;
    const latency=runs.latency;
    if(!latency) el('ex9-latency').innerHTML=empty('9.1 · Write concern latency');
    else {
      const rows=latency.summary.rows;
      const fastest=[...rows].sort((a,b)=>a.averageMs-b.averageMs)[0];
      const comparisons=[1,'majority',3].map(w=>{
        const off=rows.find(r=>r.w===w&&!r.j), on=rows.find(r=>r.w===w&&r.j);
        return `${mode(w)}: ${num(on.averageMs-off.averageMs)} ms per write ${on.averageMs>=off.averageMs?'added':'difference'} with j:true${off.averageMs>0?` (${num(on.averageMs/off.averageMs)}× the j:false average)`:''}`;
      });
      el('ex9-latency').innerHTML=`<div class="panel replica-section">${heading(latency,'9.1 · Write concern latency')}<p><strong>Fastest in this recording:</strong> ${esc(mode(fastest.w))}, j:${fastest.j} — ${num(fastest.averageMs)} ms average.</p><div class="table-wrap"><table><caption>1,000 individual inserts per configuration · milliseconds</caption><thead><tr><th>Write concern</th><th>Journal wait</th><th>Writes</th><th>Total ms</th><th>Average ms</th><th>P50 ms</th><th>P99 ms</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(mode(r.w))}</td><td>j:${r.j}</td><td>${r.count}</td><td>${num(r.elapsedMs)}</td><td>${num(r.averageMs)}</td><td>${num(r.p50Ms)}</td><td>${num(r.p99Ms)}</td></tr>`).join('')}</tbody></table></div><h3>Try it yourself · What did journaling change?</h3><ul>${comparisons.map(t=>`<li>${esc(t)}</li>`).join('')}</ul><p class="muted">Recorded writeConcernMajorityJournalDefault: ${esc(latency.summary.majorityJournalDefault??'not recorded')}. Total includes loop overhead; average and percentiles use the individual write timings. P99 uses nearest rank. These are local measurements, not production performance guarantees.</p></div>`;
    }
    const partition=runs.partition;
    if(!partition) el('ex9-partition').innerHTML=empty('9.2 · Network partition');
    else {
      const s=partition.summary;
      const writeRows=s.events.filter(e=>e.kind==='write');
      // Collapse repeated state snapshots for readability; full samples stay in JSON.
      let previous='';const transitions=s.events.filter(e=>{
        if(e.kind==='write')return false;
        const signature=JSON.stringify([e.phase,e.members,e.error,e.kind]);
        const changed=signature!==previous;previous=signature;return changed;
      });
      el('ex9-partition').innerHTML=`<div class="panel replica-section">${heading(partition,'9.2 · Network partition')}<p><strong>${s.acknowledged}</strong> acknowledged probes · <strong>${s.failed}</strong> probes returned errors · Both recoveries recorded.</p><p class="muted">Inspect probe errors alongside the recorded member states. A timeout may leave a write applied without the requested acknowledgment.</p><div class="table-wrap"><table><caption>Observed write attempts · retries disabled</caption><thead><tr><th>Recorded time</th><th>Phase</th><th>Concern</th><th>Outcome</th><th>Latency ms</th></tr></thead><tbody>${writeRows.map(e=>`<tr><td>${esc(when(e.at))}</td><td>${esc(names[e.phase])}</td><td>${esc(mode(e.w))}</td><td>${esc(e.outcome)}${e.error?`<details><summary>Error details</summary><p>${esc(e.error)}</p></details>`:''}</td><td>${num(e.latencyMs)}</td></tr>`).join('')}</tbody></table></div><h3>Election &amp; recovery timeline</h3><ol class="replica-timeline">${transitions.map(e=>`<li><time>${esc(when(e.at))} · ${num(e.elapsedSeconds)}s within phase</time><strong>${esc(names[e.phase])}</strong><p>${e.members?.map(m=>`${esc(m.name)}: ${esc(m.state)} (health ${m.health})`).join(' · ')||esc(e.error||'Status unavailable')}</p>${e.caughtUp?'<span class="chip">Catch-up sentinel read on all 3 members</span>':''}</li>`).join('')}</ol></div>`;
    }
    el('ex9-latency').hidden=view!=='latency';el('ex9-partition').hidden=view!=='partition';
    document.querySelectorAll('[data-ex9-download]').forEach(button=>button.onclick=async()=>{
      try { const r=await api('/api/exercise9/'+button.dataset.ex9Download); const blob=new Blob([JSON.stringify(r.document,null,2)],{type:'application/json'}); const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=button.dataset.ex9Download==='latency'?'lab_9_1_latency.json':'lab_9_2_partition.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); } catch(e){message(e.message,true);}
    });
  }
  async function load() {
    if(loading)return;loading=true;
    try { const data=await api('/api/exercise9'); runs=Object.fromEntries(data.runs.map(r=>[r._id,r]));render(); }
    catch(e){message('Could not load Exercise 9 results: '+e.message,true);}
    finally{loading=false;}
  }
  window.exercise9Load=load;
  el('ex9-reload').onclick=load;
  document.querySelectorAll('[data-ex9-view]').forEach(b=>b.onclick=()=>{view=b.dataset.ex9View;document.querySelectorAll('[data-ex9-view]').forEach(other=>other.setAttribute('aria-pressed',String(other===b)));render();});
  el('ex9-upload-form').onsubmit=async event=>{
    event.preventDefault();const files=[...el('ex9-files').files];
    if(!files.length||files.length>2){message('Select one or two Exercise 9 JSON files.',true);return;}
    el('ex9-upload-button').disabled=true;
    let uploaded=0;
    try{
      for(const file of files){
        if(file.size>1024*1024)throw new Error(`${file.name} exceeds 1 MiB.`);
        let doc;try{doc=JSON.parse(await file.text());}catch{throw new Error(`${file.name} is not valid JSON.`);}
        message(`Uploading ${file.name}…`);
        await api('/api/exercise9/import',doc);uploaded++;
      }
      message(`${uploaded} result file${uploaded===1?'':'s'} saved.`);el('ex9-files').value='';
    }catch(e){message(`${uploaded?`${uploaded} file saved. `:''}${e.message}`,true);}
    finally{el('ex9-upload-button').disabled=false;await load();}
  };
  for(const id of ['ex9-hub','ex9-notes']){
    try{el(id).value=localStorage.getItem(id)||'';}catch{}
    el(id).oninput=()=>{try{localStorage.setItem(id,el(id).value);}catch{}};
  }
  el('ex9-print').onclick=()=>{
    let url;try{url=new URL(el('ex9-hub').value);}catch{}
    if(!runs.latency||!runs.partition){el('ex9-print-message').textContent='Upload both completed experiments before printing the submission report.';return;}
    if(!url||url.protocol!=='https:'||url.hostname!=='hub.docker.com'||!/^\/r\/[^/]+\/[^/]+\/?$/.test(url.pathname)){el('ex9-print-message').textContent='Enter your Docker Hub repository URL, such as https://hub.docker.com/r/your-name/signal-desk-exercise9.';return;}
    el('ex9-print-message').textContent='Choose Save as PDF in the print dialog.';
    el('ex9-print-meta').textContent=`Docker Hub URL (provided by student): ${url.href}\n\nStudent explanation:\n${el('ex9-notes').value||'Not provided.'}`;
    window.print();
  };
  render();
})();
