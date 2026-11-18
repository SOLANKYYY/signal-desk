const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
async function run(configured){
 const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{innerHTML:'',value:'',querySelector:()=>null});return elements.get(id);};
 let html='';const ctx={window:{},sessionStorage:{getItem:()=>null,setItem:()=>{}},crypto:{randomUUID:()=> '00000000-0000-0000-0000-000000000001'},document:{getElementById:element,querySelectorAll:()=>[]},fetch:async url=>({ok:true,status:200,json:async()=>url.endsWith('/status')?{configured,model:'local-model',chunks:2,note:'Configuration only',reason:'Configure model'}:url.endsWith('/sessions')?{items:[{_id:'abc',title:'<unsafe>'}]}:url.endsWith('/metrics')?{requests_24h:0,errors_24h:0,tokens_24h:0,average_latency_ms:null}:{turns:[]}})};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('frontend/coursework.js','utf8'),ctx);vm.runInContext(fs.readFileSync('frontend/assistant.js','utf8'),ctx);
 await ctx.window.renderAssistant(x=>html=x,()=>true);
 assert.ok(html.includes('How can I help you?'));assert.ok(html.includes('&lt;unsafe&gt;'));assert.ok(element('chat-form').onsubmit);assert.ok(element('chat-thread').innerHTML.includes('Start with a question'));
 assert.ok(html.indexOf('How can I help you?')<html.indexOf('Evidence library'));assert.ok(html.includes('chat-file'));assert.ok(html.includes('chat-feed-next'));
 assert.ok(html.includes('/api/assistant/device-script'));assert.ok(html.includes('device-consent'));assert.ok(html.includes('shared account'));
 await element('device-file').onchange({target:{files:[{name:'program.exe',size:10}]}});
 assert.ok(element('device-file-status').textContent.includes('generated JSON'));
 await element('device-file').onchange({target:{files:[{name:'check.json',size:100,text:async()=>JSON.stringify({schema:'signal-desk-device-check/v1',checks:{},generated_at:'2026-11-18T00:00:00Z'})}]}});
 assert.equal(element('chat-platform').value,'windows');assert.ok(element('device-preview').textContent.includes('signal-desk-device-check/v1'));
 await element('chat-form').onsubmit({preventDefault(){}});
 assert.ok(element('chat-notice').textContent.includes('Confirm permission'));
 element('device-remove').onclick();assert.equal(element('device-preview').textContent,'');assert.equal(element('device-consent').checked,false);
 assert.ok(!html.includes('View setup instructions'));assert.ok(!html.includes('final-assessment checklist'));assert.ok(!html.includes('GEMINI_API_KEY'));
 if(!configured)assert.ok(html.includes('disabled'));
}
(async()=>{await run(true);await run(false);console.log('Assistant UI: configured and unconfigured states passed');})().catch(e=>{console.error(e);process.exit(1);});
