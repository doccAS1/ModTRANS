PAGE = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>skyrimtrans</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e3e1da;--accent:#2f6f4f;--accent-ink:#fff;--bad:#a6362c;--warn:#8a6100;--ok-bg:#e8f2ec}
@media (prefers-color-scheme:dark){:root{--bg:#161715;--card:#1f201e;--ink:#ecebe6;--mute:#9a9992;--line:#34352f;--accent:#5fb287;--accent-ink:#0e1a13;--bad:#ef7d72;--warn:#e0b24a;--ok-bg:#1f2d25}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0}
header p{color:var(--mute);margin:4px 0 24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px}
.card h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin:0 0 12px;font-weight:600}
#drop{border-style:dashed;text-align:center;padding:34px 18px;cursor:pointer}
#drop.over{border-color:var(--accent);background:var(--ok-bg)}
#drop b{display:block;font-size:16px}
#drop span{color:var(--mute);font-size:13px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:560px){.row{grid-template-columns:1fr}}
label{display:block;font-size:13px;color:var(--mute);margin-bottom:4px}
select,input[type=text],input[type=password],input[type=number],textarea{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
textarea{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;min-height:70px}
.field{margin-bottom:12px}
.hide{display:none!important}
.check{display:flex;gap:8px;align-items:flex-start;font-size:14px;color:var(--ink)}
.check input{margin-top:4px}
.check small{display:block;color:var(--mute)}
button{font:inherit;border:0;border-radius:8px;padding:10px 18px;cursor:pointer;background:var(--accent);color:var(--accent-ink);font-weight:600}
button.sec{background:transparent;color:var(--ink);border:1px solid var(--line)}
button:disabled{opacity:.45;cursor:not-allowed}
.actions{display:flex;gap:10px;align-items:center;margin-top:6px}
.bar{height:8px;background:var(--line);border-radius:99px;overflow:hidden;margin:10px 0}
.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .3s}
pre{margin:0;max-height:160px;overflow:auto;font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;color:var(--mute);white-space:pre-wrap}
.stats{display:flex;gap:22px;flex-wrap:wrap;margin:6px 0 12px}
.stats div{font-size:13px;color:var(--mute)}
.stats b{display:block;font-size:24px;color:var(--ink)}
.err{color:var(--bad);font-weight:600}
details{margin-top:10px;font-size:13px}
details summary{cursor:pointer;color:var(--mute)}
details ul{margin:8px 0 0;padding-left:18px;max-height:200px;overflow:auto}
a.dl{display:inline-block;text-decoration:none;background:var(--accent);color:var(--accent-ink);padding:10px 18px;border-radius:8px;font-weight:600}
.note{font-size:13px;color:var(--mute);margin-top:10px}
.q{list-style:none;margin:0;padding:0}
.q li{display:flex;align-items:center;gap:10px;padding:9px 10px;border:1px solid var(--line);border-radius:8px;margin-bottom:6px;cursor:pointer}
.q li.sel{border-color:var(--accent);background:var(--ok-bg)}
.q .nm{flex:1;min-width:0}.q .nm b{display:block;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.q .bd{font-size:12px;color:var(--mute);white-space:nowrap}.q .bd.ok{color:var(--accent)}.q .bd.bad{color:var(--bad)}
.q .bar{height:4px;margin:4px 0 0}
.q .acts{display:flex;gap:6px;align-items:center}
button.sm,a.sm{padding:4px 10px;font-size:13px;border-radius:6px}
a.sm{display:inline-block;text-decoration:none;background:var(--accent);color:var(--accent-ink);font-weight:600}
.banner{background:var(--ok-bg);border:1px solid var(--warn);border-radius:8px;padding:10px 12px;margin-bottom:10px;font-size:14px}
.lane{border:1px solid var(--line);border-radius:10px;padding:10px;margin-bottom:12px}
.lane.paused{border-color:var(--warn)}
.lane .lh{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.lane .lh b{font-size:14px}.lane .lh .sum{font-size:12px;color:var(--mute);flex:1;min-width:120px}
.lane .pm{font-size:13px;color:var(--warn);margin:0 0 8px}
.lane .empty{font-size:13px;color:var(--mute);margin:0 0 4px}
.stage h3{font-size:12px;margin:0 0 6px;color:var(--mute);font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.hist .meta{font-size:12px;color:var(--mute)}
.hist details{margin:4px 0 0}
</style>
</head>
<body>
<main>
<header><h1>skyrimtrans</h1><p>Traduce le mod di Skyrim senza toccare la struttura: cambia solo il testo.</p></header>

<section class="card" id="drop" tabindex="0">
  <b id="dropTitle">Trascina qui le mod</b>
  <span id="dropSub">.zip, .7z, .esp, .esm, .esl &middot; anche pi&ugrave; di una: vengono tradotte una dopo l'altra</span>
  <input type="file" id="file" class="hide" accept=".zip,.7z,.esp,.esm,.esl" multiple>
</section>

<section class="card hide" id="queueCard">
  <h2>Code</h2>
  <div id="stage" class="stage hide"><h3>Da avviare</h3><ul class="q" id="stageList"></ul></div>
  <div id="lanes"></div>
  <div class="actions"><button class="sec sm" id="qHide" type="button">Nascondi le finite</button></div>
</section>

<section class="card" id="ctxCard">
  <h2>Contesto della mod<span id="ctxFor"></span></h2>
  <p class="note" style="margin:0 0 10px">Aiuta il modello a capire di che mod si tratta (tono, ambientazione, nomi da non tradurre). Viene letto dal plugin; puoi aggiungere i dati della pagina Nexus Mods e correggere il testo qui sotto.</p>
  <div class="row">
    <div class="field"><label for="nexus_ref">Link o ID Nexus Mods (facoltativo)</label><input type="text" id="nexus_ref" autocomplete="off" placeholder="es. 168874"></div>
    <div class="field"><label for="nexus_key">Chiave API Nexus <span>(gratuita: Nexus &rarr; Account &rarr; API)</span></label><input type="password" id="nexus_key" autocomplete="off" placeholder="non viene salvata su disco"></div>
  </div>
  <div class="row">
    <div class="field"><label for="nexus_game">Gioco su Nexus</label><select id="nexus_game"><option value="skyrimspecialedition">Skyrim Special Edition</option><option value="skyrim">Skyrim (Legendary Edition)</option></select></div>
    <div class="field" style="align-self:end"><button class="sec" id="ctxBtn" disabled>Aggiungi dati da Nexus Mods</button></div>
  </div>
  <div class="field"><label for="brief">Contesto dato al modello (modificabile)</label><textarea id="brief" style="min-height:110px;font-family:inherit;font-size:14px" placeholder="Carica una mod: il contesto letto dal plugin apparirà qui."></textarea></div>
  <span id="ctxMsg" class="note"></span> <span id="ctxErr" class="err"></span>
</section>

<section class="card">
  <h2>Traduzione</h2>
  <div class="row">
    <div class="field"><label for="lang">Traduci in</label><select id="lang"></select></div>
    <div class="field"><label for="source">Lingua originale della mod</label><select id="source"></select></div>
  </div>
  <div class="field"><label for="preset">Servizio AI</label>
    <select id="preset">
      <option value="claude">Claude (Anthropic)</option>
      <option value="openai">OpenAI</option>
      <option value="ollama">Locale &ndash; Ollama</option>
      <option value="lmstudio">Locale &ndash; LM Studio</option>
      <option value="custom">Altro (compatibile OpenAI)</option>
    </select></div>
  <div class="row">
    <div class="field"><label for="model">Modello</label><input type="text" id="model" autocomplete="off"></div>
    <div class="field" id="urlBox"><label for="base_url">Indirizzo API</label><input type="text" id="base_url" autocomplete="off"></div>
  </div>
  <div class="field" id="keyBox"><label for="api_key">Chiave API <span id="keyHint"></span></label><input type="password" id="api_key" autocomplete="off" placeholder="non viene salvata su disco"></div>
  <details><summary>Opzioni avanzate</summary>
    <div class="row" style="margin-top:10px">
      <div class="field"><label for="batch">Stringhe per richiesta</label><input type="number" id="batch" min="1" max="200"></div>
    </div>
    <div class="field"><label class="check"><input type="checkbox" id="shorten" checked><span>Accorcia i testi troppo lunghi<small>Nomi, pulsanti e scelte di dialogo che superano molto la lunghezza originale vengono riscritti pi&ugrave; brevi (una richiesta in pi&ugrave; solo se serve).</small></span></label></div>
    <div class="field"><label class="check"><input type="checkbox" id="review"><span>Revisione finale con l&rsquo;AI<small>Un secondo passaggio rilegge le traduzioni e corregge errori evidenti. Costa circa una richiesta in pi&ugrave; ogni 30 stringhe.</small></span></label></div>
    <div class="field"><label class="check"><input type="checkbox" id="use_memory" checked><span>Usa la memoria delle traduzioni<small>Riprende da dove si era interrotto e riusa le traduzioni gi&agrave; fatte (stessa lingua e modello). <span id="memInfo"></span> <a href="#" id="memClear">Svuota la memoria</a></small></span></label></div>
    <div class="field"><label for="game_data">Nomi ufficiali del gioco (facoltativo)</label><input id="game_data" type="text" placeholder="C:\\Program Files (x86)\\Steam\\steamapps\\common\\Skyrim Special Edition\\Data" spellcheck="false"><small class="hint">Cartella Data di Skyrim in italiano: il programma accoppia i testi inglesi e italiani del gioco e li usa come glossario ufficiale. Viene ricordato solo il percorso.</small></div>
    <div class="field"><label for="glossary">Glossario (JSON, facoltativo)</label><textarea id="glossary" placeholder='{"Dragonborn": "Sangue di Drago"}' spellcheck="false"></textarea></div>
  </details>
  <div class="field" style="margin-top:14px"><label for="out_where">Dove salvare il risultato</label>
    <select id="out_where"><option value="download">Scarica dal browser</option><option value="folder">Salva in una cartella del PC</option></select></div>
  <div id="outBox" class="hide">
    <div class="row">
      <div class="field"><label for="out_dir">Cartella</label>
        <div style="display:flex;gap:8px"><input type="text" id="out_dir" autocomplete="off" placeholder="es. C:\Mods\Traduzioni"><button class="sec" id="browseBtn" type="button">Sfoglia...</button></div></div>
      <div class="field"><label for="out_mode">Formato</label>
        <select id="out_mode"><option value="folder">Cartella pronta (da copiare nel gioco o nel mod manager)</option><option value="zip">File ZIP</option></select></div>
    </div>
    <p class="note" style="margin:-4px 0 10px">Non sovrascrive mai nulla: se il nome esiste gi&agrave; aggiunge (2), (3)...</p>
  </div>
  <div class="field" style="margin-top:14px"><label class="check"><input type="checkbox" id="dry"><span>Solo analisi<small>Non chiama nessuna AI: mostra quante stringhe verrebbero tradotte.</small></span></label></div>
  <div class="field" id="laneBox" style="margin-top:14px"><label for="laneSel">Metti le mod in</label><select id="laneSel"><option value="new">Una nuova coda (con le impostazioni qui sopra)</option></select>
    <p class="note" id="laneNote" style="margin:6px 0 0"></p></div>
  <div class="actions"><button id="go" disabled>Traduci</button><button id="stop" class="sec hide">Annulla</button><span id="msg" class="err"></span></div>
</section>

<section class="card hide" id="progress">
  <h2 id="phase">Avvio</h2>
  <div class="bar"><i id="barFill"></i></div>
  <pre id="log"></pre>
</section>

<section class="card hide" id="result">
  <h2 id="resTitle">Risultato</h2>
  <div class="stats" id="stats"></div>
  <div id="resAction"></div>
  <details id="warnBox" class="hide"><summary id="warnSum"></summary><ul id="warnList"></ul></details>
  <details id="failBox" class="hide"><summary id="failSum"></summary><ul id="failList"></ul></details>
  <p class="note" id="resNote"></p>
</section>

<section class="card hide hist" id="histCard">
  <h2>Cronologia</h2>
  <ul class="q" id="histList"></ul>
  <div class="actions"><span class="note" id="histInfo" style="margin:0;flex:1"></span><button class="sec sm" id="histClear" type="button">Svuota la cronologia</button></div>
</section>
</main>
<div id="modal" class="hide" style="position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:16px;z-index:10">
  <div class="card" style="width:100%;max-width:560px;margin:0;max-height:85vh;display:flex;flex-direction:column">
    <h2>Scegli la cartella</h2>
    <div style="display:flex;gap:8px;margin-bottom:8px"><button class="sec" id="bUp" type="button">&uarr; Su</button><input type="text" id="bPath" readonly style="flex:1"></div>
    <div id="bQuick" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px"></div>
    <ul id="bList" style="list-style:none;margin:0 0 10px;padding:0;overflow:auto;flex:1;border:1px solid var(--line);border-radius:8px;min-height:160px"></ul>
    <div style="display:flex;gap:8px;align-items:center"><button class="sec" id="bNew" type="button">Nuova cartella</button><span id="bErr" class="err" style="flex:1;font-size:13px"></span><button class="sec" id="bCancel" type="button">Annulla</button><button id="bOk" type="button">Usa questa cartella</button></div>
  </div>
</div>
<script>
const T="__TOKEN__", D=__DEFAULTS__;
const $=s=>document.querySelector(s);
let laneSel="new", items=[], sel=-1, viewJob=null, autoFollow=true, uploadId=null, briefTouched=false, lastQ=null, shownKey=null;
const seenDone=new Set(), hiddenJobs=new Set();
const STATE_TXT={queued:"In attesa",running:"In corso",done:"Completata",error:"Errore",cancelled:"Annullata"};

const PRESETS={
  claude:{provider:"anthropic",url:"",model:D.default_model,batch:40,key:"(o variabile ANTHROPIC_API_KEY)"},
  openai:{provider:"openai",url:"https://api.openai.com/v1",model:"gpt-4o-mini",batch:40,key:"(o variabile OPENAI_API_KEY)"},
  ollama:{provider:"openai",url:"http://localhost:11434/v1",model:"qwen2.5:14b",batch:8,key:"(non serve in locale)"},
  lmstudio:{provider:"openai",url:"http://localhost:1234/v1",model:"",batch:8,key:"(non serve in locale)"},
  custom:{provider:"openai",url:"",model:"",batch:20,key:"(se richiesta)"}
};
for(const [k,l] of D.langs){for(const id of ["lang","source"]){const o=document.createElement("option");o.value=k;o.textContent=l;$("#"+id).appendChild(o)}}
$("#lang").value=D.saved.lang||"italian"; $("#source").value=D.saved.source||"english";
$("#preset").value=D.saved.preset||"claude";
function applyPreset(keep){
  const p=PRESETS[$("#preset").value];
  $("#urlBox").classList.toggle("hide",p.provider==="anthropic");
  $("#keyHint").textContent=p.key;
  if(!keep){$("#base_url").value=p.url;$("#model").value=p.model;$("#batch").value=p.batch}
}
$("#preset").onchange=()=>applyPreset(false);
applyPreset(false);
if(D.saved.preset){ if(D.saved.model!==undefined)$("#model").value=D.saved.model; if(D.saved.base_url!==undefined)$("#base_url").value=D.saved.base_url; if(D.saved.batch_items)$("#batch").value=D.saved.batch_items; }

async function api(path,opt={}){
  const r=await fetch(path,{...opt,headers:{"X-Token":T,"Content-Type":"application/json"}});
  let j={}; try{j=await r.json()}catch(e){}
  if(!r.ok) throw new Error(j.error||("Errore "+r.status));
  return j;
}
function fmt(n){return n>1048576?(n/1048576).toFixed(1)+" MB":Math.max(1,Math.round(n/1024))+" KB"}

function upload(file,it){
  return new Promise((res,rej)=>{
    const x=new XMLHttpRequest();
    x.open("POST","/api/upload?name="+encodeURIComponent(file.name));
    x.setRequestHeader("X-Token",T);
    x.upload.onprogress=e=>{if(e.lengthComputable){it.pct=Math.round(100*e.loaded/e.total);renderQueue()}};
    x.onload=()=>{let j={};try{j=JSON.parse(x.responseText)}catch(e){} x.status===200?res(j):rej(new Error(j.error||"Caricamento fallito"))};
    x.onerror=()=>rej(new Error("Caricamento fallito"));
    x.send(file);
  });
}
function saveFields(){ const it=items[sel]; if(it){ it.brief=$("#brief").value; it.briefTouched=briefTouched; it.nexus_ref=$("#nexus_ref").value } }
function selectItem(i){
  saveFields(); sel=i; const it=items[i];
  $("#brief").value=it?it.brief:""; $("#nexus_ref").value=it?it.nexus_ref:""; briefTouched=it?it.briefTouched:false;
  uploadId=it&&it.upload_id; $("#ctxBtn").disabled=!uploadId; $("#ctxFor").textContent=it?" — "+it.name:"";
  $("#ctxMsg").textContent=it&&it.job?"Questa mod è già in coda: cambiare il contesto non ha più effetto su di lei.":""; $("#ctxErr").textContent=""; renderQueue();
}
function syncGo(){
  const n=items.filter(it=>it.status==="ready"&&!it.job).length;
  $("#go").disabled=!n; $("#go").textContent=n>1?"Traduci "+n+" mod":"Traduci";
}
async function addFiles(list){
  const files=[...list]; if(!files.length)return;
  $("#msg").textContent="";
  for(const f of files){
    const it={name:f.name,size:f.size,upload_id:null,job:null,brief:"",briefTouched:false,nexus_ref:"",status:"upload",err:"",pct:0};
    items.push(it); if(sel<0||!items[sel]||items[sel].job)selectItem(items.length-1); else renderQueue();
    try{ const j=await upload(f,it); it.upload_id=j.upload_id; it.nexus_ref=j.nexus_id?String(j.nexus_id):""; it.status="ready";
         if(items[sel]===it){ $("#nexus_ref").value=it.nexus_ref; uploadId=it.upload_id; $("#ctxBtn").disabled=false }
         loadContext(false,it) }
    catch(e){ it.status="fail"; it.err=e.message }
    renderQueue(); syncGo();
  }
}
const drop=$("#drop");
drop.onclick=()=>$("#file").click();
drop.onkeydown=e=>{if(e.key==="Enter"||e.key===" ")$("#file").click()};
$("#file").onchange=e=>{ addFiles(e.target.files); e.target.value="" };
for(const ev of ["dragenter","dragover"])drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add("over")});
for(const ev of ["dragleave","drop"])drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove("over")});
drop.addEventListener("drop",e=>addFiles(e.dataTransfer.files));
addEventListener("dragover",e=>e.preventDefault()); addEventListener("drop",e=>e.preventDefault());

$("#brief").oninput=()=>{briefTouched=true};
$("#nexus_game").value=D.saved.nexus_game||"skyrimspecialedition";
async function loadContext(withNexus,it=items[sel]){
  if(!it||!it.upload_id)return;
  const here=()=>items[sel]===it;
  if(here()){ $("#ctxErr").textContent=""; $("#ctxMsg").textContent=withNexus?"Leggo la pagina Nexus e preparo il riassunto...":"Leggo il plugin..." }
  const p=PRESETS[$("#preset").value];
  const body={upload_id:it.upload_id,provider:p.provider,model:$("#model").value.trim(),base_url:$("#base_url").value.trim(),api_key:$("#api_key").value.trim()};
  if(withNexus){body.nexus_ref=$("#nexus_ref").value.trim();body.nexus_key=$("#nexus_key").value.trim();body.nexus_game=$("#nexus_game").value}
  try{
    const j=await api("/api/context",{method:"POST",body:JSON.stringify(body)});
    if(here()){ if(withNexus||!briefTouched){$("#brief").value=j.brief;briefTouched=false;it.brief=j.brief;it.briefTouched=false} }
    else if(withNexus||!it.briefTouched){ it.brief=j.brief; it.briefTouched=false }
    if(here())$("#ctxMsg").textContent="Fonti: "+j.sources.join(", ")+(j.nexus_name?" · Nexus: "+j.nexus_name:"")+(j.warning?" · "+j.warning:"");
  }catch(e){ if(here()){ $("#ctxMsg").textContent=""; $("#ctxErr").textContent=e.message } }
}
$("#ctxBtn").onclick=()=>{ if(!$("#nexus_ref").value.trim()){$("#ctxErr").textContent="Inserisci il link o l'ID della mod su Nexus";return} loadContext(true) };

/* ---- dove salvare ---- */
$("#out_where").value=D.saved.out_where||"download"; $("#out_dir").value=D.saved.out_dir||""; $("#out_mode").value=D.saved.out_mode||"folder";
function syncOut(){ $("#outBox").classList.toggle("hide",$("#out_where").value!=="folder") }
$("#out_where").onchange=syncOut; syncOut();
let bCur="";
async function loadDir(path){
  $("#bErr").textContent="";
  try{
    const j=await api("/api/browse?path="+encodeURIComponent(path||""));
    bCur=j.path; $("#bPath").value=j.path; $("#bUp").disabled=!j.parent&&!j.drives.length; $("#bUp").dataset.parent=j.parent||"";
    const q=$("#bQuick"); q.innerHTML="";
    for(const p of [...j.quick,...(j.drives||[])]){const b=document.createElement("button");b.type="button";b.className="sec";b.style.padding="4px 10px";b.textContent=p.split(/[\\/]/).filter(Boolean).pop()||p;b.title=p;b.onclick=()=>loadDir(p);q.appendChild(b)}
    const l=$("#bList"); l.innerHTML="";
    if(!j.dirs.length){const e=document.createElement("li");e.style.cssText="padding:10px;color:var(--mute)";e.textContent="(nessuna sottocartella)";l.appendChild(e)}
    for(const d of j.dirs){const e=document.createElement("li");e.style.cssText="padding:8px 10px;cursor:pointer;border-bottom:1px solid var(--line)";e.textContent="\uD83D\uDCC1 "+d;e.onclick=()=>loadDir(j.path.replace(/[\\/]+$/,"")+j.sep+d);l.appendChild(e)}
  }catch(e){ $("#bErr").textContent=e.message }
}
$("#browseBtn").onclick=()=>{ $("#modal").classList.remove("hide"); loadDir($("#out_dir").value.trim()) };
$("#bUp").onclick=()=>loadDir($("#bUp").dataset.parent||"");
$("#bCancel").onclick=()=>$("#modal").classList.add("hide");
$("#bOk").onclick=()=>{ $("#out_dir").value=bCur; $("#modal").classList.add("hide") };
$("#bNew").onclick=async()=>{
  const n=prompt("Nome della nuova cartella:"); if(!n)return;
  try{ const j=await api("/api/mkdir",{method:"POST",body:JSON.stringify({path:bCur,name:n})}); loadDir(j.path) }catch(e){ $("#bErr").textContent=e.message }
};

/* ---- memoria ---- */
$("#use_memory").checked=D.saved.use_memory!==false; $("#shorten").checked=D.saved.shorten!==false; $("#game_data").value=D.saved.game_data||""; $("#review").checked=!!D.saved.review;
async function memRefresh(){ try{ const m=await api("/api/memory"); $("#memInfo").textContent=m.entries?("Salvate "+m.entries+" traduzioni ("+(m.bytes/1048576).toFixed(1)+" MB)."):"Ancora vuota." }catch(e){} }
memRefresh();
$("#memClear").onclick=async e=>{ e.preventDefault(); if(!confirm("Cancellare tutte le traduzioni salvate? Dovranno essere rifatte (e ripagate) la prossima volta."))return; await api("/api/memory/clear",{method:"POST",body:"{}"}); memRefresh() };

function currentSettings(){
  const p=PRESETS[$("#preset").value];
  return {lang:$("#lang").value,source:$("#source").value,provider:p.provider,preset:$("#preset").value,
    model:$("#model").value.trim(),base_url:$("#base_url").value.trim(),api_key:$("#api_key").value.trim(),
    batch_items:parseInt($("#batch").value)||40,nexus_game:$("#nexus_game").value,out_where:$("#out_where").value,out_dir:$("#out_dir").value.trim(),out_mode:$("#out_mode").value,use_memory:$("#use_memory").checked,shorten:$("#shorten").checked,review:$("#review").checked,glossary:$("#glossary").value.trim(),game_data:$("#game_data").value.trim()};
}
$("#go").onclick=async()=>{
  saveFields(); $("#msg").textContent="";
  const ready=items.filter(it=>it.status==="ready"&&!it.job);
  if(!ready.length)return;
  const base=currentSettings();
  let first=null, target=$("#laneSel").value;
  for(const it of ready){
    const own={upload_id:it.upload_id,brief:it.brief.trim(),dry_run:$("#dry").checked};
    try{ const j=await api("/api/start",{method:"POST",body:JSON.stringify(target==="new"?{...base,...own,lane_id:"new"}:{...own,lane_id:target})});
         it.job=j.job_id; if(!first)first=j.job_id; if(target==="new"){ target=j.lane_id; $("#laneSel").dataset.want=target } }
    catch(e){ $("#msg").textContent=(ready.length>1?it.name+": ":"")+e.message; break }
  }
  if(first){ viewJob=first; autoFollow=true; shownKey=null; $("#result").classList.add("hide") }
  if(items[sel]&&items[sel].job)$("#ctxMsg").textContent="Questa mod è già in coda: cambiare il contesto non ha più effetto su di lei.";
  syncGo(); pollQueue();
};
$("#stop").onclick=()=>viewJob&&api("/api/cancel/"+viewJob,{method:"POST",body:"{}"}).then(pollQueue).catch(()=>{});
$("#qHide").onclick=()=>{ for(const j of (lastQ?lastQ.jobs:[])) if(!["queued","running"].includes(j.state))hiddenJobs.add(j.id); renderQueue() };

function el(tag,cls,text){ const e=document.createElement(tag); if(cls)e.className=cls; if(text!==undefined)e.textContent=text; return e }
function qrow(name,badge,badgeCls,pct,selected,onclick){
  const li=el("li",selected?"sel":""); li.onclick=onclick;
  const nm=el("div","nm"); nm.appendChild(el("b","",name));
  if(pct!==null){ const bar=el("div","bar"); const i=el("i"); i.style.width=pct+"%"; bar.appendChild(i); nm.appendChild(bar) }
  li.appendChild(nm); li.appendChild(el("span","bd "+badgeCls,badge));
  const acts=el("div","acts"); li.appendChild(acts); return {li,acts}
}
function btn(label,fn,cls){ const b=el("button",cls||"sec sm",label); b.type="button"; b.onclick=e=>{e.stopPropagation();fn()}; return b }
function jobRow(j){
  const run=j.state==="running";
  const pct=run?(j.total?Math.round(100*j.done/j.total):3):null;
  const badge=run?(j.phase+(j.total?" "+j.done+"/"+j.total:"")):STATE_TXT[j.state]+(j.dry&&j.state==="done"?" (analisi)":"");
  const r=qrow(j.name,badge,j.state==="done"?"ok":(j.state==="error"?"bad":""),pct,viewJob===j.id,()=>{ viewJob=j.id; autoFollow=false; shownKey=null; refreshView() });
  if(j.state==="queued"||run) r.acts.appendChild(btn("Annulla",()=>api("/api/cancel/"+j.id,{method:"POST",body:"{}"}).then(pollQueue).catch(()=>{})));
  if(j.state==="done"&&j.downloadable){ const a=el("a","sm","Scarica"); a.href="/api/download/"+j.id+"?t="+encodeURIComponent(T); a.onclick=e=>e.stopPropagation(); r.acts.appendChild(a) }
  if(j.state==="done"&&j.saved_to) r.acts.appendChild(btn("Apri cartella",()=>api("/api/open",{method:"POST",body:JSON.stringify({path:j.saved_to})}).catch(e=>{$("#msg").textContent=e.message})));
  if(j.state==="error"||j.state==="cancelled") r.acts.appendChild(btn("Riprova",()=>retryJob(j.id)));
  if(!["queued","running"].includes(j.state)) r.acts.appendChild(btn("✕",()=>{hiddenJobs.add(j.id);renderQueue()}));
  return r.li;
}
function laneBox(l,jobs){
  const box=el("div","lane"+(l.paused?" paused":""));
  const h=el("div","lh"); h.appendChild(el("b","",l.name)); h.appendChild(el("span","sum",l.summary));
  if(l.paused) h.appendChild(btn("Riprendi",()=>api("/api/queue/resume",{method:"POST",body:JSON.stringify({lane_id:l.id})}).then(pollQueue).catch(()=>{}),"sm"));
  h.appendChild(btn("Usa le impostazioni qui sotto",async()=>{
    const s=currentSettings(); try{ await api("/api/lane/update",{method:"POST",body:JSON.stringify({lane_id:l.id,settings:s})}); $("#msg").textContent=""; pollQueue() }catch(e){ $("#msg").textContent=e.message } }));
  if(jobs.some(j=>j.state==="queued")) h.appendChild(btn("Annulla le in attesa",()=>api("/api/queue/clear",{method:"POST",body:JSON.stringify({lane_id:l.id})}).then(pollQueue).catch(()=>{})));
  if(!l.busy) h.appendChild(btn("Chiudi",()=>api("/api/lane/close",{method:"POST",body:JSON.stringify({lane_id:l.id})}).then(pollQueue).catch(e=>{$("#msg").textContent=e.message})));
  box.appendChild(h);
  if(l.paused) box.appendChild(el("p","pm","In pausa: "+l.pause_msg));
  const ul=el("ul","q"); for(const j of jobs)ul.appendChild(jobRow(j));
  if(!jobs.length) box.appendChild(el("p","empty","Nessuna mod in questa coda."));
  box.appendChild(ul); return box;
}
function renderLaneSelect(){
  const sel2=$("#laneSel"), cur=sel2.dataset.want||sel2.value; delete sel2.dataset.want;
  const ls=lastQ?lastQ.lanes:[];
  sel2.innerHTML=""; const o=el("option","","Una nuova coda (con le impostazioni qui sopra)"); o.value="new"; sel2.appendChild(o);
  for(const l of ls){ const x=el("option","",l.name+(l.summary?" — "+l.summary:"")); x.value=l.id; sel2.appendChild(x) }
  sel2.value=ls.some(l=>l.id===cur)?cur:"new";
  $("#laneNote").textContent=sel2.value==="new"?(ls.length?"Una coda nuova parte subito, in parallelo alle altre.":""):"Userà le impostazioni di questa coda (servizio AI, modello, lingua): quelle qui sopra valgono solo per le code nuove. Per cambiarle usa “Usa le impostazioni qui sotto” nella coda.";
}
$("#laneSel").onchange=renderLaneSelect;
function renderQueue(){
  const ls=lastQ?lastQ.lanes:[];
  const jobsAll=(lastQ?lastQ.jobs:[]).filter(j=>!hiddenJobs.has(j.id));
  const LN=$("#lanes"); LN.innerHTML="";
  for(const l of ls) LN.appendChild(laneBox(l,jobsAll.filter(j=>j.lane===l.id)));
  const SL=$("#stageList"); SL.innerHTML="";
  items.forEach((it,i)=>{
    if(it.job)return;
    const badge=it.status==="upload"?"Caricamento "+it.pct+"%":(it.status==="fail"?it.err:"Pronta");
    const r=qrow(it.name,badge,it.status==="fail"?"bad":"",it.status==="upload"?it.pct:null,sel===i,()=>selectItem(i));
    if(it.status==="ready") r.acts.appendChild(btn("Contesto",()=>selectItem(i)));
    r.acts.appendChild(btn("✕",()=>{ saveFields(); const cur=items[sel]; items.splice(i,1); const ni=items.indexOf(cur); if(ni>=0){sel=ni}else{sel=-1; selectItem(items.length?items.length-1:-1)} syncGo(); renderQueue() }));
    SL.appendChild(r.li);
  });
  $("#stage").classList.toggle("hide",!SL.children.length);
  $("#queueCard").classList.toggle("hide",!SL.children.length&&!ls.length);
  renderLaneSelect();
}
async function retryJob(id){
  try{ const r=await api("/api/retry/"+id,{method:"POST",body:"{}"}); hiddenJobs.add(id); viewJob=r.job_id; autoFollow=true; shownKey=null; $("#result").classList.add("hide"); pollQueue() }
  catch(e){ $("#msg").textContent=e.message }
}

async function pollQueue(){
  let q; try{ q=await api("/api/queue") }catch(e){ return }
  lastQ=q;
  if(autoFollow){ const run=q.jobs.find(j=>j.state==="running"); if(run&&viewJob!==run.id){viewJob=run.id;shownKey=null} else if(!viewJob&&q.jobs.length){viewJob=q.jobs[q.jobs.length-1].id} }
  for(const j of q.jobs) if(j.state==="done"&&!j.dry&&!seenDone.has(j.id)){ seenDone.add(j.id); histRefresh() }
  renderQueue(); await refreshView();
}
async function refreshView(){
  if(!viewJob)return;
  let j; try{ j=await api("/api/status/"+viewJob) }catch(e){ return }
  const live=j.state==="queued"||j.state==="running";
  $("#progress").classList.remove("hide");
  $("#phase").textContent=(j.name?j.name+" — ":"")+j.phase+(j.total?" — "+j.done+" / "+j.total:"");
  $("#barFill").style.width=(j.total?100*j.done/j.total:(j.state==="running"?3:0))+"%";
  const l=$("#log"); l.textContent=j.log.join("\n"); if(live)l.scrollTop=l.scrollHeight;
  $("#stop").classList.toggle("hide",!live);
  if(live){ $("#result").classList.add("hide"); shownKey=null; return }
  const key=viewJob+":"+j.state;
  if(shownKey!==key){ shownKey=key; finish(j) }
}

/* ---- cronologia ---- */
async function histRefresh(){
  let h; try{ h=await api("/api/history") }catch(e){ return }
  const L=$("#histList"); L.innerHTML="";
  $("#histCard").classList.toggle("hide",!h.entries.length);
  for(const e of h.entries){
    const li=el("li",""); li.style.cursor="default";
    const nm=el("div","nm"); nm.appendChild(el("b","",e.name));
    nm.appendChild(el("div","meta",[e.lang,e.finished,e.translated+" stringhe",e.kept_original?e.kept_original+" lasciate originali":"",e.warnings.length?e.warnings.length+" avvisi":""].filter(Boolean).join(" · ")+(e.mode==="folder"?" · salvata in "+e.saved_to:"")));
    if(e.warnings.length||e.failures.length){ const d=el("details"); d.appendChild(el("summary","","Dettagli")); const ul=el("ul");
      for(const t of [...e.failures,...e.warnings].slice(0,100))ul.appendChild(el("li","",t)); ul.querySelectorAll("li").forEach(x=>{x.style.cssText="border:0;padding:0;margin:0;display:list-item;cursor:default"}); d.appendChild(ul); nm.appendChild(d) }
    li.appendChild(nm);
    const acts=el("div","acts"); li.appendChild(acts);
    if(!e.available) acts.appendChild(el("span","bd bad","non più disponibile"));
    else if(e.mode==="zip"){ const a=el("a","sm","Scarica"); a.href="/api/history/"+e.id+"/download?t="+encodeURIComponent(T); acts.appendChild(a) }
    else acts.appendChild(btn("Apri cartella",()=>api("/api/open",{method:"POST",body:JSON.stringify({path:e.saved_to})}).catch(x=>{$("#msg").textContent=x.message})));
    acts.appendChild(btn("Elimina",async()=>{
      const msg=e.mode==="zip"?"Eliminare \""+e.name+"\" dalla cronologia? Il file zip salvato verrà cancellato.":"Togliere \""+e.name+"\" dalla cronologia? La cartella sul tuo PC non viene toccata.";
      if(!confirm(msg))return; try{ await api("/api/history/delete",{method:"POST",body:JSON.stringify({id:e.id})}) }catch(x){} histRefresh() }));
    L.appendChild(li);
  }
  $("#histInfo").textContent=h.bytes?"Spazio occupato dai file scaricabili: "+fmt(h.bytes):"";
}
$("#histClear").onclick=async()=>{ if(!confirm("Svuotare tutta la cronologia? Gli zip conservati verranno cancellati; le cartelle salvate sul PC no."))return; try{ await api("/api/history/clear",{method:"POST",body:"{}"}) }catch(e){} histRefresh() };
setInterval(pollQueue,800); pollQueue(); histRefresh();

function li(parent,items,max){ parent.innerHTML=""; for(const t of items.slice(0,max)){const e=document.createElement("li");e.textContent=t;parent.appendChild(e)} if(items.length>max){const e=document.createElement("li");e.textContent="... e altre "+(items.length-max);parent.appendChild(e)} }
function finish(j){
  const R=$("#result"); R.classList.remove("hide");
  $("#stats").innerHTML=""; $("#resAction").innerHTML=""; $("#warnBox").classList.add("hide"); $("#failBox").classList.add("hide"); $("#resNote").textContent="";
  if(j.state==="cancelled"){ $("#resTitle").textContent="Annullato"; $("#resNote").textContent="Nessun file prodotto."; return }
  if(j.state==="error"){ $("#resTitle").textContent="Errore"; const p=document.createElement("p"); p.className="err"; p.textContent=j.error; $("#resAction").appendChild(p);
    if(j.phase==="Interrotto"){ const id=viewJob; const b=document.createElement("button"); b.className="sec"; b.textContent="Riprendi"; b.onclick=()=>retryJob(id); $("#resAction").appendChild(b) }
    memRefresh(); return }
  const r=j.report;
  $("#resTitle").textContent=j.dry?"Analisi completata":"Traduzione completata";
  const stat=(n,l)=>{const d=document.createElement("div");const b=document.createElement("b");b.textContent=n;d.appendChild(b);d.appendChild(document.createTextNode(l));$("#stats").appendChild(d)};
  stat(r.translated,j.dry?"stringhe traducibili":"stringhe tradotte");
  if(!j.dry){ stat(r.kept_original,"lasciate originali"); stat(r.files.length,"file modificati o creati"); if(r.from_memory)stat(r.from_memory,"dalla memoria (gratis)"); if(r.shortened)stat(r.shortened,"accorciate"); if(r.qa_checked)stat(r.qa_checked+" / "+r.qa_fixed,"riviste / corrette"); }
  if(!j.dry && j.saved_to){
    const p=document.createElement("p"); p.style.margin="0 0 10px"; p.textContent="Salvato in: "+j.saved_to; $("#resAction").appendChild(p);
    const b=document.createElement("button"); b.textContent="Apri la cartella"; b.onclick=()=>api("/api/open",{method:"POST",body:JSON.stringify({path:j.saved_to})}).catch(e=>{$("#resNote").textContent=e.message}); $("#resAction").appendChild(b);
    $("#resNote").textContent="Fai una copia di sicurezza prima di installarla e controlla i termini del gioco: la lista dei campi e la verifica coprono la struttura, non la qualit\u00e0 della traduzione.";
  } else if(!j.dry){
    const a=document.createElement("a"); a.className="dl"; a.textContent="Scarica la mod tradotta"; a.href="/api/download/"+viewJob+"?t="+encodeURIComponent(T); $("#resAction").appendChild(a);
    $("#resNote").textContent="Fai una copia di sicurezza prima di installarla e controlla i termini del gioco: la lista dei campi e la verifica coprono la struttura, non la qualità della traduzione.";
  } else { $("#resNote").textContent="Nessuna chiamata AI e nessun file prodotto."; }
  if(r.warnings.length){ $("#warnBox").classList.remove("hide"); $("#warnSum").textContent="Avvisi ("+r.warnings.length+")"; li($("#warnList"),r.warnings,100) }
  if(r.failures.length){ $("#failBox").classList.remove("hide"); $("#failSum").textContent="Stringhe non tradotte o rifiutate ("+r.failures.length+")"; li($("#failList"),r.failures,100);
    if(!j.dry){ const b=document.createElement("button"); b.className="sec"; b.style.marginLeft="10px"; b.textContent="Riprova le fallite"; const id=viewJob; b.onclick=()=>retryJob(id); $("#resAction").appendChild(b);
      $("#resNote").textContent+=" Le gi\u00e0 tradotte sono in memoria: riprovando si rifanno solo quelle fallite." } }
  memRefresh();
}
</script>
</body>
</html>
"""
