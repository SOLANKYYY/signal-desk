const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
async function run(configured){
 const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{innerHTML:'',value:'',querySelector:()=>null});return elements.get(id);};
 let html='';const ctx={window:{},sessionStorage:{getItem:()=>null,setItem:()=>{}},crypto:{randomUUID:()=> '00000000-0000-0000-0000-000000000001'},document:{getElementById:element,querySelectorAll:()=>[]},fetch:async url=>({ok:true,status:200,json:async()=>url.endsWith('/status')?{configured,model:'local-model',chunks:2,note:'Configuration only',reason:'Configure model'}:url.endsWith('/sessions')?{items:[{_id:'abc',title:'<unsafe>'}]}:url.endsWith('/metrics')?{requests_24h:0,errors_24h:0,tokens_24h:0,average_latency_ms:null}:{turns:[]}})};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('frontend/coursework.js','utf8'),ctx);vm.runInContext(fs.readFileSync('frontend/assistant.js','utf8'),ctx);
 await ctx.window.renderAssistant(x=>html=x,()=>true);
 assert.ok(html.includes('Evidence first. Answers second.'));assert.ok(html.includes('&lt;unsafe&gt;'));assert.ok(element('chat-form').onsubmit);assert.ok(element('chat-thread').innerHTML.includes('Start with a question'));
 assert.ok(html.indexOf('Evidence library')<html.indexOf('Evidence first. Answers second.'));assert.ok(html.includes('chat-file'));assert.ok(html.includes('chat-feed-next'));
 assert.ok(!html.includes('View setup instructions'));assert.ok(!html.includes('final-assessment checklist'));assert.ok(!html.includes('GEMINI_API_KEY'));
 if(!configured)assert.ok(html.includes('disabled'));
}
(async()=>{await run(true);await run(false);console.log('Assistant UI: configured and unconfigured states passed');})().catch(e=>{console.error(e);process.exit(1);});
