/* Tests the actual generator append logic with the HA websocket protocol. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict"),test=require("node:test");
const context=vm.createContext({HTMLElement:class{},customElements:{get:()=>false,define:()=>{}}});
vm.runInContext(fs.readFileSync("custom_components/cez_dynamic_tariff/frontend/dashboard-generator.js","utf8"),context);
const clone=value=>JSON.parse(JSON.stringify(value));
const config={views:[{path:"cez",title:"ČEZ",subview:false},{path:"cez-detaily",subview:true},{path:"cez-zalohy",subview:true}]};
function server(options={}){
 let value={title:"House",theme:"user-theme",custom:{preserve:true},views:[{path:"home",cards:[{type:"markdown",content:"untouched"}]}]};
 const calls=[];let reads=0;
 return {get value(){return clone(value)},calls,async call(message){
  calls.push(clone(message));
  if(message.type==="get_panels")return {lovelace:{config:{mode:options.yaml?"yaml":"storage"}}};
  if(message.type==="lovelace/config"){
   if(options.automatic)throw new Error("config_not_found");
   reads++;if(options.concurrent&&reads===2)value.views.push({path:"someone-else"});
   return clone(value);
  }
  if(message.type==="lovelace/config/save"){
   if(options.failBeforeSave)throw new Error("network");
   value=clone(message.config);if(options.failAfterSave)throw new Error("lost-response");return null;
  }
  throw new Error("Unexpected command: "+message.type);
 }};
}
test("append three views to the top tab bar, retaining all root settings and views",async()=>{
 const s=server(),before=s.value;
 const result=await context.appendCezViews(m=>s.call(m),config);
 assert.equal(result.view_path,"cez");assert.equal(s.value.views.length,4);
 assert.deepEqual(s.value.views[0],before.views[0]);assert.equal(s.value.theme,before.theme);assert.deepEqual(s.value.custom,before.custom);
 assert.equal(s.value.views[1].subview,false);assert.equal(s.value.views[2].subview,true);
 assert.ok(!s.calls.some(m=>m.url_path||m.type==="lovelace/dashboards/create"));
});
test("repeated generation never overwrites or duplicates an existing view",async()=>{
 const s=server();await context.appendCezViews(m=>s.call(m),config);const before=s.value;
 await assert.rejects(context.appendCezViews(m=>s.call(m),config),/view_exists/);assert.deepEqual(s.value,before);
 assert.equal(s.calls.filter(m=>m.type==="lovelace/config/save").length,1);
});
test("collision of a detail path rejects the entire append",async()=>{
 const s=server();const changed=clone(config);changed.views[1].path="home";
 await assert.rejects(context.appendCezViews(m=>s.call(m),changed),/view_exists/);assert.equal(s.value.views.length,1);
});
test("YAML and auto-generated Overview are not written",async()=>{
 for(const options of [{yaml:true},{automatic:true}]){const s=server(options);
  await assert.rejects(context.appendCezViews(m=>s.call(m),config),/yaml_dashboard|overview_not_editable/);
  assert.equal(s.calls.filter(m=>m.type==="lovelace/config/save").length,0);}
});
test("concurrent user edits are retained and cause a retry instead of stale save",async()=>{
 const s=server({concurrent:true});await assert.rejects(context.appendCezViews(m=>s.call(m),config),/overview_changed/);
 assert.equal(s.value.views[1].path,"someone-else");assert.equal(s.calls.filter(m=>m.type==="lovelace/config/save").length,0);
});
test("a lost success response is reconciled by reading the stored configuration",async()=>{
 const s=server({failAfterSave:true});const result=await context.appendCezViews(m=>s.call(m),config);
 assert.equal(result.view_path,"cez");assert.equal(s.value.views.length,4);
});
test("failed save neither deletes nor retries writes",async()=>{
 const s=server({failBeforeSave:true});await assert.rejects(context.appendCezViews(m=>s.call(m),config),/save_unconfirmed/);
 assert.equal(s.value.views.length,1);assert.equal(s.calls.filter(m=>m.type==="lovelace/config/save").length,1);
 assert.ok(!s.calls.some(m=>m.type.includes("delete")));
});
test("unsafe paths, duplicate paths or a hidden main view are rejected before calls",async()=>{
 for(const modify of [v=>v[0].path="../home",v=>v[0].subview=true,v=>v[2].path=v[1].path]){
  const s=server(),bad=clone(config);modify(bad.views);
  await assert.rejects(context.appendCezViews(m=>s.call(m),bad),/invalid_views/);assert.equal(s.calls.length,0);}
});

test("reuse keeps the user's exact card layout and local invoice values",()=>{
 const generated={views:[{path:"cez-new",title:"New title"},{path:"cez-new-detaily",subview:true},{path:"cez-new-zalohy",subview:true}]};
 const existing={views:[{path:"cez-dynamic-tariff",title:"Old title",sections:[{cards:[{type:"markdown",content:"Local invoice example · custom layout"},{type:"button",tap_action:{navigation_path:"/lovelace/cez-dynamic-tariff-detaily"}}]}]},
  {path:"cez-dynamic-tariff-detaily",subview:true,back_path:"/lovelace/cez-dynamic-tariff",cards:[{type:"markdown",content:"user details"}]},
  {path:"cez-dynamic-tariff-zalohy",subview:true,back_path:"/lovelace/cez-dynamic-tariff-detaily"}]};
 const before=clone(existing),result=context.reuseCurrentCezViews(generated,existing);
 assert.deepEqual(existing,before);assert.equal(result.views[0].title,"New title");
 assert.equal(result.views[0].sections[0].cards[0].content,existing.views[0].sections[0].cards[0].content);
 assert.equal(result.views[0].sections[0].cards[1].tap_action.navigation_path,"/lovelace/cez-new-detaily");
 assert.equal(result.views[1].back_path,"/lovelace/cez-new");assert.equal(result.views[2].back_path,"/lovelace/cez-new-detaily");
 assert.equal(result.views[0].subview,false);assert.equal(result.views[1].subview,true);
});
test("fresh installations retain the bundled current template",()=>{
 assert.equal(context.reuseCurrentCezViews(config,{views:[{path:"home"}]}),config);
});
