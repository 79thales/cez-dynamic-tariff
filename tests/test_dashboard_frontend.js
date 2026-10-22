/* Tests the actual generator append logic with the HA websocket protocol. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict"),test=require("node:test");
const context=vm.createContext({HTMLElement:class{},customElements:{get:()=>false,define:()=>{}}});
vm.runInContext(fs.readFileSync("custom_components/cez_dynamic_tariff/frontend/dashboard-generator.js","utf8"),context);
const clone=value=>JSON.parse(JSON.stringify(value));
const bundledCharts=()=>JSON.parse(fs.readFileSync("custom_components/cez_dynamic_tariff/dashboard_template.json","utf8"))
  .views.flatMap(view=>view.sections||[]).flatMap(section=>section.cards||[]).filter(card=>card.type==="custom:apexcharts-card");

// Spouštíme skutečné EVAL funkce šablony. Ověřujeme význam dat, ne jen volbu
// konfigurace: komplementární null není nula, ani hodnota jiného času/období.
test("accounting tooltips omit null while retaining zero, coverage and exact X",()=>{
 for(const card of bundledCharts()){
  const tooltip=vm.runInNewContext("("+card.apex_config.tooltip.custom.slice(5)+")");
  const x=Date.UTC(2026,5,1,12),other=x+86400000;
  const points=[{name:"Úplný měsíc",data:[[x,null],[x,0],[other,78.65]]},
   {name:"Neúplný měsíc",data:[[other,149.56],[x,null]]},
   {name:"Odhad <jiný>",data:[{x,y:undefined},{x:other,y:400}]}];
  const w={config:{series:points},globals:{collapsedSeriesIndices:[]}};
  let html=tooltip({seriesIndex:0,dataPointIndex:1,w});
  assert.ok(html.includes("Úplný měsíc: <strong>0,0 "));
  assert.ok(!html.includes("Neúplný měsíc"));assert.ok(!html.includes("null"));assert.ok(!html.includes("400"));
  assert.ok(html.includes("2026"));assert.ok(html.includes(card.series[0].unit==="kWh"?"kWh":"Kč"));
  html=tooltip({seriesIndex:0,dataPointIndex:2,w});
  assert.ok(html.includes("78,7"));assert.ok(html.includes("149,6"));assert.ok(html.includes("&lt;jiný&gt;"));
  w.globals.collapsedSeriesIndices=[1];
  assert.ok(!tooltip({seriesIndex:0,dataPointIndex:2,w}).includes("Neúplný měsíc"));
  assert.equal(tooltip({seriesIndex:0,dataPointIndex:99,w}),"");
  assert.equal(tooltip({seriesIndex:2,dataPointIndex:0,w:{config:{series:[points[2]]},globals:{}}}),"");
 }
});

test("copied charts receive canonical tooltips without changing local series or layout",()=>{
 const generated=JSON.parse(fs.readFileSync("custom_components/cez_dynamic_tariff/dashboard_template.json","utf8"));
 const existing=clone(generated),before=clone(existing);
 existing.views[0].sections[3].cards[1].apex_config.tooltip={shared:true,intersect:false};
 existing.views[0].sections[3].cards[1].series[0].entity="sensor.my_accounting";
 const local=clone(existing.views[0].sections[3].cards[1]);
 const unrelated={type:"custom:apexcharts-card",header:{title:"Můj jiný graf"},apex_config:{tooltip:{shared:false}}};
 existing.views[1].sections[0].cards.push(unrelated);
 const input=clone(existing),result=context.reuseCurrentCezViews(generated,existing);
 assert.deepEqual(existing,input);
 const repaired=result.views[0].sections[3].cards[1];
 assert.deepEqual(clone(repaired.series),local.series);
 assert.deepEqual(clone(repaired.apex_config.tooltip),before.views[0].sections[3].cards[1].apex_config.tooltip);
 assert.deepEqual(clone(result.views[1].sections[0].cards.at(-1)),unrelated);
 assert.deepEqual(clone(context.cezRepairChartTooltips(result,generated)),clone(result));
});

test("monthly series stay in current billing year and distinguish incomplete, missing and zero",()=>{
 const card=bundledCharts().find(card=>card.header.title==="Měsíční odběr podle měření HA");
 const entity={attributes:{billing_start:"2026-04-01",billing_end:"2027-03-31",today_through:"2026-10-12T19:30:00Z",
  history_months:{"2025-06":{kwh:999,complete:true},"2026-04":{kwh:0,complete:true},
   "2026-06":{kwh:78.65,complete:true},"2026-07":{kwh:13.44,complete:false},
   "2026-09":{kwh:null,complete:false},"2026-10":{kwh:149.56,complete:true}}}};
 const values=card.series.map(s=>new Function("entity","hass",s.data_generator)(entity,{config:{time_zone:"Europe/Prague"}}));
 assert.deepEqual(values[0].map(p=>p[0]),values[1].map(p=>p[0]));
 assert.equal(values[0].length,7);assert.equal(new Date(values[0][0][0]).getUTCFullYear(),2026);
 assert.equal(values[0][0][1],0);assert.equal(values[1][0][1],null);
 assert.equal(values[0][2][1],78.65);assert.equal(values[1][2][1],null);
 assert.equal(values[0][3][1],null);assert.equal(values[1][3][1],13.44);
 assert.equal(values[0][5][1],null);assert.equal(values[1][5][1],null);
 assert.equal(values[0][6][1],null);assert.equal(values[1][6][1],149.56);
 entity.attributes.today_through="not-a-date";
 assert.deepEqual(new Function("entity","hass",card.series[0].data_generator)(entity,{config:{}}),[]);
});

test("financial series clip to billing boundaries without replacing zero or missing values",()=>{
 const card=bundledCharts().find(card=>card.header.title==="Náklady a zálohy za zúčtovací období");
 const left=new Date("2026-04-01T00:00:00").getTime(),right=new Date("2027-04-01T00:00:00").getTime();
 const points=[[left-1,999],[left,0],[left+86400000,null],[right,123],[right+1,999]];
 const entity={attributes:{billing_start:"2026-04-01",billing_end:"2027-03-31",
  cost_actual_series:points,cost_forecast_series:points,advance_paid_series:points,advance_planned_series:points}};
 for(const s of card.series){
  const result=new Function("entity",s.data_generator)(entity);
  assert.deepEqual(result,[[left,null],...points.slice(1,4),[right,null]]);
 }
});

test("comparison keeps current-year X and separates measured energy, prior invoice and forecast",()=>{
 const card=bundledCharts().find(card=>card.header.title==="Skutečná spotřeba a měsíční profil");
 const entity={attributes:{billing_start:"2026-04-01",billing_end:"2027-03-31",today_through:"2026-10-12T19:30:00Z",
  history_months:{"2026-04":{kwh:0,complete:true},"2026-06":{kwh:78.65,complete:true},
   "2026-07":{kwh:13.44,complete:false},"2026-10":{kwh:149.56,complete:false}},
  settled_bills:[{start:"2024-04-01",end:"2025-03-31",months:[{month:"2024-06",nt_kwh:900,vt_kwh:9}]},
   {start:"2025-04-01",end:"2026-03-31",months:[{month:"2025-04",nt_kwh:0,vt_kwh:0},
    {month:"2025-06",nt_kwh:100,vt_kwh:10},{month:"2025-10",nt_kwh:310,vt_kwh:0},
    {month:"2025-11",nt_kwh:300,vt_kwh:0}]}]}};
 const values=card.series.map(s=>new Function("entity","hass",s.data_generator)(entity,{config:{time_zone:"Europe/Prague"}}));
 const month=(series,m)=>series.find(p=>new Date(p[0]).getUTCDate()===1&&new Date(p[0]).getUTCHours()===12&&new Date(p[0]).getUTCMonth()===m-1)?.[1];
 assert.deepEqual(values[0].map(p=>p[0]),values[1].map(p=>p[0]));
 assert.deepEqual(values[0].map(p=>p[0]),values[2].map(p=>p[0]));
 assert.equal(month(values[0],4),0);assert.equal(month(values[1],4),0);
 assert.equal(month(values[0],6),78.65);assert.equal(month(values[1],6),110);assert.equal(month(values[2],6),null);
 assert.equal(month(values[0],7),null); // Starý neúplný měsíc není úplný profil.
 assert.equal(month(values[0],10),149.56);assert.ok(month(values[2],10)>149.56);
 assert.equal(month(values[0],11),null);assert.equal(month(values[1],11),300);assert.equal(month(values[2],11),300);
 assert.equal(month(values[1],12),null);assert.equal(month(values[2],12),null);
 assert.equal(new Date(values[0].at(-1)[0]).getFullYear(),2027);
});
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

test("accounting recovery is added once to copied details using generated registry bindings",()=>{
 const bundled=JSON.parse(fs.readFileSync("custom_components/cez_dynamic_tariff/dashboard_template.json","utf8"));
 const generated=clone(bundled);
 generated.views.forEach((view,index)=>{view.path="cez-new"+["","-detaily","-zalohy"][index];});
 const existing={views:[{path:"cez-dynamic-tariff",cards:[{type:"markdown",content:"místní hlavní karta"}]},
  {path:"cez-dynamic-tariff-detaily",sections:[{cards:[{type:"markdown",content:"místní detail"}]}]},
  {path:"cez-dynamic-tariff-zalohy",cards:[{type:"markdown",content:"místní zálohy"}]}]};
 const before=clone(existing),result=context.reuseCurrentCezViews(generated,existing);
 assert.deepEqual(existing,before);
 const cards=result.views[1].sections[0].cards;
 assert.equal(cards.length,3);assert.equal(cards[0].content,"místní detail");
 assert.ok(cards.some(card=>JSON.stringify(card).includes("button.cez_dynamic_tariff_accounting_backfill")));
 assert.equal(cards.filter(card=>card.name==="Vyúčtování a ceníky – nastavení integrace").length,1);
 context.cezAddAccountingRecovery(result.views[1],generated.views[1]);
 assert.equal(result.views[1].sections[0].cards.length,3);
 assert.equal(result.views[0].cards[0].content,"místní hlavní karta");
 assert.equal(result.views[2].cards[0].content,"místní zálohy");
});

// Převzetí starých pohledů musí opravit stejnou chybu jako přibalená šablona.
// Úprava se týká jen HDO výrazů; místní sestava a vstupní konfigurace se nemění.
test("copied HDO templates are guarded in the main view and detail subviews",()=>{
 const unsafe="{% set hdo = state_attr('sensor.cez_dynamic_tariff_total_price','hdo_entity') %}HDO: {{ 'NT' if is_state(hdo,'on') else 'VT' if is_state( hdo, \"off\" ) else 'neznámé' }}";
 const existing={views:[{path:"cez-dynamic-tariff",cards:[{type:"markdown",content:unsafe}]},
  {path:"cez-dynamic-tariff-detaily",cards:[{type:"markdown",content:unsafe},{type:"markdown",content:"Místní faktura"}]},
  {path:"cez-dynamic-tariff-zalohy",cards:[{type:"markdown",content:unsafe}]}]};
 const before=clone(existing),result=context.reuseCurrentCezViews(config,existing);
 assert.deepEqual(existing,before);
 for(const view of result.views){const content=view.cards[0].content;
  assert.ok(!content.includes("is_state("));assert.ok(content.includes("hdo is string"));
  assert.ok(content.includes("regex_match('^[a-z0-9]+(?:_[a-z0-9]+)*[.][a-z0-9]+(?:_[a-z0-9]+)*\\\\Z')"));
  assert.ok(content.includes("states(hdo) == 'on'"));assert.ok(content.includes("states(hdo) == 'off'"));
  assert.equal(context.cezGuardHdoTemplates(content),content);}
 assert.equal(result.views[1].cards[1].content,"Místní faktura");
});

test("repair preserves guarded bundled templates and unrelated is_state calls",()=>{
 const bundled=JSON.parse(fs.readFileSync("custom_components/cez_dynamic_tariff/dashboard_template.json","utf8"));
 assert.deepEqual(clone(context.cezGuardHdoTemplates(bundled)),bundled);
 const unrelated="{{ is_state('binary_sensor.local_switch','on') }}";
 assert.equal(context.cezGuardHdoTemplates(unrelated),unrelated);
});

test("pricing upgrade preserves custom cards and adds one registry-resolved selector",()=>{
 const generated=JSON.parse(fs.readFileSync("custom_components/cez_dynamic_tariff/dashboard_template.json","utf8"));
 const custom={type:"markdown",title:"Moje poznámka",content:"Místní obsah"};
 const main={path:"cez-dynamic-tariff",sections:[{cards:[
  {type:"markdown",title:"Pásmo obchodní ceny",content:"Starý procentní semafor"},custom]}]};
 const result=clone(context.reuseCurrentCezViews(generated,{views:[main]}));
 const cards=result.views[0].sections[0].cards;
 assert.deepEqual(cards.find(card=>card.title==="Moje poznámka"),custom);
 assert.ok(cards.find(card=>card.title==="Pásmo obchodní ceny").content.includes("active_trade_price"));
 assert.equal(cards.filter(card=>card.title==="Způsob výpočtu dynamického tarifu").length,1);
 assert.deepEqual(clone(context.reuseCurrentCezViews(generated,result)),result);
});

test("accounting document warnings and administration survive generation without duplicating cards",()=>{
 const generated=JSON.parse(fs.readFileSync("custom_components/cez_dynamic_tariff/dashboard_template.json","utf8"));
 const old=clone(generated);
 const walk=(node,cb)=>{if(!node||typeof node!=="object")return;cb(node);Object.values(node).forEach(v=>Array.isArray(v)?v.forEach(x=>walk(x,cb)):walk(v,cb));};
 walk(old,card=>{
  if(card.type==="markdown"&&card.content?.includes("{# cez_accounting_estimate #}"))
   card.content=card.content.split("{# cez_accounting_estimate #}")[0];
 });
 old.views[1].sections.at(-1).cards.pop();
 const source=clone(old),first=context.reuseCurrentCezViews(generated,old);
 assert.deepEqual(old,source);
 const second=context.reuseCurrentCezViews(generated,clone(first));
 assert.deepEqual(clone(first),clone(second));
 let summaries=0,buttons=0;
 walk(first,card=>{
  if(card.type==="markdown"&&card.content?.includes("## Vyúčtování")){
   summaries++;assert.ok(card.content.includes("forecast_approximate"));
   assert.equal(card.content.split("{# cez_accounting_estimate #}").length,2);
  }
  if(card.type==="button"&&card.name==="Vyúčtování a ceníky – nastavení integrace")buttons++;
 });
 assert.equal(summaries,2);assert.equal(buttons,1);
 assert.equal(first.views.length,3);assert.equal(first.views[0].subview,false);
 assert.equal(first.views[1].subview,true);assert.equal(first.views[2].subview,true);
});
