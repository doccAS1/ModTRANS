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
</style>
</head>
<body>
<main>
<header><h1>skyrimtrans</h1><p>Traduce le mod di Skyrim senza toccare la struttura: cambia solo il testo.</p></header>

<section class="card" id="drop" tabindex="0">
  <b id="dropTitle">Trascina qui la mod</b>
  <span id="dropSub">.zip, .7z, .esp, .esm, .esl &middot; oppure clicca per scegliere il file</span>
  <input type="file" id="file" class="hide" accept=".zip,.7z,.esp,.esm,.esl">
</section>

<section class="card" id="ctxCard">
  <h2>Contesto della mod</h2>
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
let uploadId=null, jobId=null, timer=null, briefTouched=false;

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

function upload(file){
  return new Promise((res,rej)=>{
    const x=new XMLHttpRequest();
    x.open("POST","/api/upload?name="+encodeURIComponent(file.name));
    x.setRequestHeader("X-Token",T);
    x.upload.onprogress=e=>{if(e.lengthComputable)$("#dropSub").textContent="Caricamento "+Math.round(100*e.loaded/e.total)+"%"};
    x.onload=()=>{let j={};try{j=JSON.parse(x.responseText)}catch(e){} x.status===200?res(j):rej(new Error(j.error||"Caricamento fallito"))};
    x.onerror=()=>rej(new Error("Caricamento fallito"));
    x.send(file);
  });
}
async function pick(file){
  if(!file)return;
  $("#msg").textContent=""; $("#go").disabled=true; uploadId=null;
  $("#dropTitle").textContent=file.name; $("#dropSub").textContent="Caricamento...";
  try{ const j=await upload(file); uploadId=j.upload_id; $("#dropSub").textContent=fmt(file.size)+" · clicca o trascina un altro file per cambiarlo"; $("#go").disabled=false; $("#ctxBtn").disabled=false;
       $("#nexus_ref").value=j.nexus_id||""; briefTouched=false; loadContext(false) }
  catch(e){ $("#dropTitle").textContent="Trascina qui la mod"; $("#dropSub").textContent=""; $("#msg").textContent=e.message }
}
const drop=$("#drop");
drop.onclick=()=>$("#file").click();
drop.onkeydown=e=>{if(e.key==="Enter"||e.key===" ")$("#file").click()};
$("#file").onchange=e=>pick(e.target.files[0]);
for(const ev of ["dragenter","dragover"])drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add("over")});
for(const ev of ["dragleave","drop"])drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove("over")});
drop.addEventListener("drop",e=>pick(e.dataTransfer.files[0]));
addEventListener("dragover",e=>e.preventDefault()); addEventListener("drop",e=>e.preventDefault());

$("#brief").oninput=()=>{briefTouched=true};
$("#nexus_game").value=D.saved.nexus_game||"skyrimspecialedition";
async function loadContext(withNexus){
  if(!uploadId)return;
  $("#ctxErr").textContent=""; $("#ctxMsg").textContent=withNexus?"Leggo la pagina Nexus e preparo il riassunto...":"Leggo il plugin...";
  const p=PRESETS[$("#preset").value];
  const body={upload_id:uploadId,provider:p.provider,model:$("#model").value.trim(),base_url:$("#base_url").value.trim(),api_key:$("#api_key").value.trim()};
  if(withNexus){body.nexus_ref=$("#nexus_ref").value.trim();body.nexus_key=$("#nexus_key").value.trim();body.nexus_game=$("#nexus_game").value}
  try{
    const j=await api("/api/context",{method:"POST",body:JSON.stringify(body)});
    if(withNexus||!briefTouched){$("#brief").value=j.brief;briefTouched=false}
    $("#ctxMsg").textContent="Fonti: "+j.sources.join(", ")+(j.nexus_name?" · Nexus: "+j.nexus_name:"")+(j.warning?" · "+j.warning:"");
  }catch(e){ $("#ctxMsg").textContent=""; $("#ctxErr").textContent=e.message }
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

function setRunning(r){ $("#go").disabled=r||!uploadId; $("#stop").classList.toggle("hide",!r); }
$("#go").onclick=async()=>{
  $("#msg").textContent=""; $("#result").classList.add("hide");
  const p=PRESETS[$("#preset").value];
  const s={upload_id:uploadId,lang:$("#lang").value,source:$("#source").value,provider:p.provider,preset:$("#preset").value,
    model:$("#model").value.trim(),base_url:$("#base_url").value.trim(),api_key:$("#api_key").value.trim(),
    batch_items:parseInt($("#batch").value)||40,brief:$("#brief").value.trim(),nexus_game:$("#nexus_game").value,out_where:$("#out_where").value,out_dir:$("#out_dir").value.trim(),out_mode:$("#out_mode").value,glossary:$("#glossary").value.trim(),dry_run:$("#dry").checked};
  try{ const j=await api("/api/start",{method:"POST",body:JSON.stringify(s)}); jobId=j.job_id; }
  catch(e){ $("#msg").textContent=e.message; return }
  setRunning(true); $("#progress").classList.remove("hide"); $("#log").textContent="";
  clearInterval(timer); timer=setInterval(poll,600); poll();
};
$("#stop").onclick=()=>api("/api/cancel/"+jobId,{method:"POST",body:"{}"}).catch(()=>{});

async function poll(){
  let j; try{ j=await api("/api/status/"+jobId) }catch(e){ return }
  $("#phase").textContent=j.phase+(j.total?" — "+j.done+" / "+j.total:"");
  $("#barFill").style.width=(j.total?100*j.done/j.total:(j.state==="running"?3:0))+"%";
  const l=$("#log"); l.textContent=j.log.join("\n"); l.scrollTop=l.scrollHeight;
  if(j.state!=="running"){ clearInterval(timer); setRunning(false); finish(j); }
}
function li(parent,items,max){ parent.innerHTML=""; for(const t of items.slice(0,max)){const e=document.createElement("li");e.textContent=t;parent.appendChild(e)} if(items.length>max){const e=document.createElement("li");e.textContent="... e altre "+(items.length-max);parent.appendChild(e)} }
function finish(j){
  const R=$("#result"); R.classList.remove("hide");
  $("#stats").innerHTML=""; $("#resAction").innerHTML=""; $("#warnBox").classList.add("hide"); $("#failBox").classList.add("hide"); $("#resNote").textContent="";
  if(j.state==="cancelled"){ $("#resTitle").textContent="Annullato"; $("#resNote").textContent="Nessun file prodotto."; return }
  if(j.state==="error"){ $("#resTitle").textContent="Errore"; const p=document.createElement("p"); p.className="err"; p.textContent=j.error; $("#resAction").appendChild(p); return }
  const r=j.report;
  $("#resTitle").textContent=j.dry?"Analisi completata":"Traduzione completata";
  const stat=(n,l)=>{const d=document.createElement("div");const b=document.createElement("b");b.textContent=n;d.appendChild(b);d.appendChild(document.createTextNode(l));$("#stats").appendChild(d)};
  stat(r.translated,j.dry?"stringhe traducibili":"stringhe tradotte");
  if(!j.dry){ stat(r.kept_original,"lasciate originali"); stat(r.files.length,"file modificati o creati"); }
  if(!j.dry && j.saved_to){
    const p=document.createElement("p"); p.style.margin="0 0 10px"; p.textContent="Salvato in: "+j.saved_to; $("#resAction").appendChild(p);
    const b=document.createElement("button"); b.textContent="Apri la cartella"; b.onclick=()=>api("/api/open",{method:"POST",body:JSON.stringify({path:j.saved_to})}).catch(e=>{$("#resNote").textContent=e.message}); $("#resAction").appendChild(b);
    $("#resNote").textContent="Fai una copia di sicurezza prima di installarla e controlla i termini del gioco: la lista dei campi e la verifica coprono la struttura, non la qualit\u00e0 della traduzione.";
  } else if(!j.dry){
    const a=document.createElement("a"); a.className="dl"; a.textContent="Scarica la mod tradotta"; a.href="/api/download/"+jobId+"?t="+encodeURIComponent(T); $("#resAction").appendChild(a);
    $("#resNote").textContent="Fai una copia di sicurezza prima di installarla e controlla i termini del gioco: la lista dei campi e la verifica coprono la struttura, non la qualità della traduzione.";
  } else { $("#resNote").textContent="Nessuna chiamata AI e nessun file prodotto."; }
  if(r.warnings.length){ $("#warnBox").classList.remove("hide"); $("#warnSum").textContent="Avvisi ("+r.warnings.length+")"; li($("#warnList"),r.warnings,100) }
  if(r.failures.length){ $("#failBox").classList.remove("hide"); $("#failSum").textContent="Stringhe non tradotte o rifiutate ("+r.failures.length+")"; li($("#failList"),r.failures,100) }
}
</script>
</body>
</html>
"""
