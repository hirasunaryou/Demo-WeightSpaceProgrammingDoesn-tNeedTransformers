"use strict";
/* Weight-Space Programming Live Lab
 * The score calculator is a pedagogical analogue, NOT the paper's torch model.
 * Original authored fact lines and paper results are explicitly attributed.
 */
(() => {
  const $=id=>document.getElementById(id);
  const NS="http://www.w3.org/2000/svg";
  const letters=["A","B","C","D"];
  const stages=[
    {tag:"STAGE 01 / WRITTEN KNOWLEDGE",title:"書かれた知識が重みの材料になる",
     desc:"著者が公開したテキストの知識行を読み込みます。勾配降下ではなく、コンパイラが概念と連想関係に変えます。"},
    {tag:"STAGE 02 / TOKEN → CONCEPT",title:"質問と選択肢を「概念」に対応させる",
     desc:"語を概念IDへ写し、質問の主要な概念を抽出。ここでは教材用の単純な分かち書きを使います。原著の語彙統合とは異なります。"},
    {tag:"STAGE 03 / PAIR ADDRESS",title:"2つの概念から、連想テーブルの行を読む",
     desc:"原著arch.pyの (a × 1,000,003 + b) mod H というアドレス計算を使った教材例。概念ID自体は簡略版です。"},
    {tag:"STAGE 04 / OPTION SCORES",title:"連想された情報が、選択肢のスコアに集まる",
     desc:"一次・二次の結合から証拠を集めて4択を比較します。数値は教育用近似モデルによる値で、確率や著者報告の正答率ではありません。"},
    {tag:"STAGE 05 / ABLATION",title:"1行の変更が、どの選択肢を動かすか",
     desc:"右側で原著の知識行を無効化したり、自分の行を足して差分を再計算。元データと原著の重みは変更しません。"}
  ];
  const s={
    catalog:null,scenario:null,result:null,tab:"play",stage:0,timer:null,speed:1,
    disabled:new Set(),favorite:null,search:"",originalRows:[],font:1,project:false,theme:"dark",
    busy:false,token:0,sourceFile:"arch.py",sourceLine:15
  };
  const jsText=x=>String(x==null?"":x);
  const escapeHTML=x=>jsText(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num=x=>Number(x||0).toLocaleString("ja-JP");
  function toast(msg){$("toast").textContent=msg;$("toast").classList.remove("hidden");clearTimeout(toast.t);toast.t=setTimeout(()=>$("toast").classList.add("hidden"),5200);}
  async function api(path,payload){
    const args=payload===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)};
    const response=await fetch(path,args);
    let result;
    try{result=await response.json();}catch(_){throw Error("JSON形式の応答を受け取れませんでした");}
    if(!response.ok||result.error)throw Error(result.error||"HTTP "+response.status);
    return result;
  }
  function error(e){toast("確認が必要です: "+(e.message||String(e)));console.error(e);}
  function element(tag,cls,text){
    const e=document.createElement(tag);
    if(cls)e.className=cls;
    if(text!==undefined)e.textContent=jsText(text);
    return e;
  }
  function stageAt(index){
    stop();
    s.stage=Math.max(0,Math.min(4,Math.round(index)));
    $("stageSeek").value=String(s.stage);
    $("transportPosition").textContent=(s.stage+1)+" / 5";
    $("stageKicker").textContent=stages[s.stage].tag;
    $("stageTitle").textContent=stages[s.stage].title;
    $("stageDescription").textContent=stages[s.stage].desc;
    document.querySelectorAll("[data-stage]").forEach(button=>button.classList.toggle("active",Number(button.dataset.stage)===s.stage));
    renderDiagram();
  }
  function stop(){
    if(s.timer!==null)clearInterval(s.timer);
    s.timer=null;
    $("stagePlay").textContent="▶ 再生";
  }
  function play(){
    if(s.timer!==null){stop();return;}
    if(s.stage===4){s.stage=0;stageAt(0);}
    $("stagePlay").textContent="Ⅱ 一時停止";
    s.timer=setInterval(()=>{
      if(s.stage>=4){stop();return;}
      s.stage++;
      stageAtWithoutStop(s.stage);
    },Math.max(150,1250/s.speed));
  }
  function stageAtWithoutStop(index){
    s.stage=Math.max(0,Math.min(4,index));
    $("stageSeek").value=String(s.stage);
    $("transportPosition").textContent=(s.stage+1)+" / 5";
    $("stageKicker").textContent=stages[s.stage].tag;
    $("stageTitle").textContent=stages[s.stage].title;
    $("stageDescription").textContent=stages[s.stage].desc;
    document.querySelectorAll("[data-stage]").forEach(button=>button.classList.toggle("active",Number(button.dataset.stage)===s.stage));
    renderDiagram();
    if(s.stage===4)stop();
  }
  function svgNode(tag,attrs={},text){
    const node=document.createElementNS(NS,tag);
    for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));
    if(text!==undefined)node.textContent=jsText(text);
    return node;
  }
  function rectNode(parent,x,y,w,h,title,subtitle,active,color){
    const group=svgNode("g",{class:"diagram-card"+(active?" active":"")});
    const rect=svgNode("rect",{x,y,width:w,height:h,rx:13,fill:active?"#225c59":"#183648",stroke:active?"#ffe0a4":"#447181","stroke-width":active?3:1.4});
    group.append(rect);
    group.append(svgNode("text",{x:x+w/2,y:y+27,"text-anchor":"middle",fill:active?"#fff2d8":"#d8f4f5","font-size":"14","font-weight":"850"},title));
    group.append(svgNode("text",{x:x+w/2,y:y+48,"text-anchor":"middle",fill:active?"#cff5db":"#9ebcc9","font-size":"10"},subtitle));
    parent.append(group);return group;
  }
  function renderDiagram(){
    const edges=$("diagramEdges"),nodes=$("diagramNodes");
    edges.replaceChildren();nodes.replaceChildren();
    const positions=[36,218,400,582,764];
    const names=["知識行","概念ID","ペア読み出し","候補スコア","変更の影響"];
    const subtitles=["Original text","Concept bag","Hash table","4 options","One-row edit"];
    for(let i=0;i<5;i++){
      if(i>0)edges.append(svgNode("path",{d:"M"+(positions[i-1]+154)+",199 C"+(positions[i-1]+171)+",199 "+(positions[i]-17)+",199 "+positions[i]+",199",
      fill:"none",stroke:i<=s.stage?"#ffd28f":"#4c8890","stroke-width":i===s.stage?4:2.2,"marker-end":"url(#arrowFlow)"}));
      rectNode(nodes,positions[i],164,154,67,names[i],subtitles[i],i===s.stage);
    }
    if(!s.result){
      nodes.append(svgNode("text",{x:460,y:104,"text-anchor":"middle",fill:"#b4cbd7","font-size":"17","font-weight":"750"},"左側で問題を選んで「知識を読み出す」"));
      nodes.append(svgNode("text",{x:460,y:288,"text-anchor":"middle",fill:"#80abb7","font-size":"12"},"公開された実際の知識行 × 教材用の再現計算"));
      return;
    }
    const r=s.result.edited;
    const selected=r.question_concepts||[];
    const pairs=r.pair_addresses||[];
    const win=r.choice;
    let title="",items=[];
    if(s.stage===0){
      title="ORIGINAL RULE EXCERPTS";
      const evidence=(s.result.baseline.scores||[]).flatMap(x=>x.evidence||[]);
      const unique=new Map();
      for(const ev of evidence){if(!unique.has(ev.id))unique.set(ev.id,ev);}
      items=[...unique.values()].slice(0,3).map(row=>row.text.slice(0,85));
      if(!items.length)items=["公開された行が選択肢へ一致していません"];
    }else if(s.stage===1){
      title="SIMPLIFIED CONCEPT BAG";
      items=selected.slice(0,7).map(x=>x.word+"  #"+x.concept+"  IDF "+x.idf);
      if(!items.length)items=["既知の語がありません。元モデルの語彙と異なる場合があります"];
    }else if(s.stage===2){
      title="PAIR HASH (DEMO CONCEPT IDS)";
      items=pairs.slice(0,5).map(x=>"("+x.left+" , "+x.right+")  →  row "+num(x.address)+(x.materialized?" · hit":" · empty"));
      if(!items.length)items=["2つ以上の既知概念を入力してください"];
    }else if(s.stage===3){
      title="OPTION EVIDENCE / ILLUSTRATIVE";
      items=r.scores.map((x,i)=>letters[i]+" : "+(x.option||"").slice(0,33)+" = "+x.score.toFixed(2)+(win===i?"  ✓":""));
    }else{
      title="COUNTERFACTUAL / ONE ROW EDIT";
      items=r.scores.map((x,i)=>{
        const delta=s.result.changes[i];
        return letters[i]+" : "+s.result.baseline.scores[i].score.toFixed(2)+" → "+x.score.toFixed(2)+"  (Δ "+(delta>=0?"+":"")+delta.toFixed(2)+")";
      });
    }
    nodes.append(svgNode("text",{x:460,y:68,"text-anchor":"middle",fill:"#85e5d2","font-size":"12","font-weight":"900","letter-spacing":".1em"},title));
    let y=96;
    for(const item of items.slice(0,7)){
      const box=svgNode("rect",{x:160,y:y-15,width:600,height:27,rx:7,fill:"#234356",stroke:"#396c76","stroke-width":"0.7"});
      nodes.append(box);
      nodes.append(svgNode("text",{x:460,y:y+3,"text-anchor":"middle",fill:"#e1f2f1","font-size":"11","font-family":"ui-monospace,Menlo,Consolas,monospace"},jsText(item).slice(0,94)));
      y+=32;
      if(y>157)break;
    }
    nodes.append(svgNode("text",{x:460,y:286,"text-anchor":"middle",fill:"#9dc7c9","font-size":"11"},
      s.stage===4?"無効化 "+s.result.disabled_count+"件 / 追加 "+(s.result.custom_rule?"あり":"なし"):
      "一次リンク "+num(r.first_order_activations)+" · 二次リンク "+num(r.second_order_activations)));
    const caveat="SRC: original facts   |   MATH: educational analogue (not original torch)";
    nodes.append(svgNode("text",{x:460,y:323,"text-anchor":"middle",fill:"#b1a5ec","font-size":"10","font-weight":"800"},caveat));
  }
  function renderScores(){
    const box=$("scoreBars");box.replaceChildren();
    if(!s.result){box.append(element("div","score-placeholder","問題を選び「知識を読み出す」を押してください。"));return;}
    const r=s.result.edited,base=s.result.baseline;
    const max=Math.max(1,...r.scores.map(x=>Math.abs(x.score)),...base.scores.map(x=>Math.abs(x.score)));
    $("answerStatus").textContent=r.choice===null?"判定保留":"教材モデル: "+letters[r.choice]+" を選択";
    r.scores.forEach((row,i)=>{
      const outer=element("div","score-item"+(i===r.choice?" winner":""));
      outer.append(element("div","score-letter",letters[i]));
      const middle=element("div");
      middle.append(element("div","score-option",row.option));
      const track=element("div","score-track");
      const filled=element("i");
      filled.style.width=(Math.min(100,Math.abs(row.score)/max*100)).toFixed(1)+"%";
      filled.style.background=row.score<0?"#da8ca9":"";
      track.append(filled);middle.append(track);outer.append(middle);
      const value=element("div","score-value",row.score.toFixed(2));
      const delta=s.result.changes[i]||0;
      if(Math.abs(delta)>.0001)value.append(element("span","score-delta","  Δ"+(delta>0?"+":"")+delta.toFixed(2)));
      outer.append(value);box.append(outer);
    });
  }
  function renderEvidence(){
    const box=$("evidenceRows");box.replaceChildren();
    if(!s.result){
      box.append(element("p","placeholder","計算すると、スコアに寄与した原著の知識行を確認できます。"));
      return;
    }
    const unique=new Map();
    for(const row of s.result.baseline.scores){
      for(const ev of row.evidence){
        const current=unique.get(ev.id);
        if(!current || Math.abs(ev.effect)>Math.abs(current.effect))unique.set(ev.id,ev);
      }
    }
    const items=[...unique.values()].sort((a,b)=>Math.abs(b.effect)-Math.abs(a.effect)).slice(0,13);
    $("rowCount").textContent=items.length+" ROWS";
    if(!items.length){box.append(element("p","placeholder","一致する知識行を特定できませんでした。別の問題を試してください。"));return;}
    items.forEach(item=>{
      const outer=element("div","evidence-row"+(item.id===s.favorite?" focus":""));
      const main=element("div","evidence-main");
      const checkbox=element("input");
      checkbox.type="checkbox";checkbox.checked=!s.disabled.has(item.id);
      checkbox.setAttribute("aria-label",item.text+" を教材メモリに含める");
      checkbox.onchange=()=>{if(checkbox.checked)s.disabled.delete(item.id);else s.disabled.add(item.id);calculate();};
      const btn=element("button",null,item.text);
      const isUserRule=item.path.startsWith("local/");
      btn.title=isUserRule?"教材で追加した行（原著ではありません）":"オリジナルの行を開く";
      btn.onclick=isUserRule?()=>{$("customRule").focus();toast("これは教材内で追加した行です。原著ファイルには存在しません。");}
        :()=>openSource(item.path,item.line);
      main.append(checkbox,btn);outer.append(main);
      const meta=element("div","evidence-meta");
      meta.append(element("span",null,isUserRule?"LIVE LAB / 教材の追加行":item.path.split("/").pop()+":"+item.line));
      meta.append(element("strong",item.effect<0?"negative":"",(item.effect>0?"+":"")+item.effect.toFixed(3)));
      outer.append(meta);
      box.append(outer);
    });
  }
  async function searchFacts(){
    try{
      const q=$("searchFacts").value.trim().slice(0,180);
      const data=await api("/api/facts?q="+encodeURIComponent(q)+"&limit=32");
      const box=$("searchResults");box.replaceChildren();
      if(!data.facts.length){box.append(element("div","placeholder","見つかりませんでした"));return;}
      for(const fact of data.facts){
        const btn=element("button");
        btn.textContent=fact.text;
        btn.append(element("small",null,fact.path.split("/").pop()+":"+fact.line+" · "+fact.kind));
        btn.onclick=()=>{s.favorite=fact.id;openSource(fact.path,fact.line);};
        box.append(btn);
      }
    }catch(e){error(e);}
  }
  function syncScenario(item){
    s.scenario=item.id;s.disabled.clear();s.favorite=null;
    $("question").value=item.question;
    document.querySelectorAll(".option-row input").forEach((x,i)=>x.value=item.options[i]||"");
    $("customRule").value="";
    document.querySelectorAll("[data-scenario]").forEach(button=>button.classList.toggle("active",button.dataset.scenario===item.id));
    s.result=null;renderScores();renderEvidence();renderDiagram();stageAt(0);
  }
  function renderScenarios(){
    const box=$("scenarioChips");box.replaceChildren();
    s.catalog.scenarios.forEach(item=>{
      const btn=element("button",null,item.title);
      btn.dataset.scenario=item.id;
      btn.onclick=()=>syncScenario(item);
      box.append(btn);
    });
    if(s.catalog.scenarios.length)syncScenario(s.catalog.scenarios[0]);
  }
  function renderInputs(){
    const box=$("optionRows");box.replaceChildren();
    letters.forEach(letter=>{
      const row=element("div","option-row");
      row.append(element("span",null,letter));
      const input=element("input");
      input.type="text";input.maxLength=180;input.placeholder="Option "+letter;
      input.setAttribute("aria-label","選択肢 "+letter);
      row.append(input);box.append(row);
    });
  }
  async function calculate(){
    if(s.busy)return;
    s.busy=true;
    $("evaluate").disabled=true;$("applyChanges").disabled=true;
    try{
      const request={
        question:$("question").value,
        options:[...document.querySelectorAll(".option-row input")].map(x=>x.value),
        disabled:[...s.disabled],
        custom:$("customRule").value
      };
      const data=await api("/api/evaluate",request);
      s.result=data;
      renderScores();renderEvidence();renderDiagram();
      if(s.stage===0)stageAt(1);
      if(data.edited.choice===null)toast("教材の簡略化した規則では、回答の根拠が十分に集まりませんでした。");
    }catch(e){error(e);}finally{s.busy=false;$("evaluate").disabled=false;$("applyChanges").disabled=false;}
  }
  function renderCatalog(){
    const models=$("modelMetrics");models.replaceChildren();
    const meta=s.catalog.statistics;
    const items=[
      ["公開モデルの知識行",num(meta.bundled_fact_rows)+"行","収録した原著の9ファイル（全体ではありません）"],
      ["今回のモデル",meta.selected_model.test_accuracy.toFixed(2)+"%","原著公開のテスト結果・このアプリの測定値ではありません"],
      ["公開モデルの非ゼロ重み",num(meta.selected_model.nonzero),"result.json記載。学習用計算とは別"]
    ];
    items.forEach(([label,value,sub])=>{
      const el=element("div","metric-card");
      el.append(element("span",null,label));
      el.append(element("b",null,value));
      el.append(element("p",null,sub));
      models.append(el);
    });
    const chart=$("resultChart");chart.replaceChildren();
    for(const item of meta.published.writers){
      const group=element("div","chart-group");
      group.append(element("div","chart-title",item.name));
      const lines=element("div","chart-bars");
      const variants=[
        ["LLMが書いた公開アーキテクチャ",item.fixed,""],
        ["LLMが重みを書いた2層Transformer",item.transformer,""],
        ["自由設計の最終世代",item.free_last,"free"],
        ["提案連想メモリの最終世代",item.assoc_last,"assoc"]
      ];
      for(const [label,value,cssClass] of variants){
        const row=element("div","chart-line "+cssClass);
        row.append(element("span",null,label));
        const track=element("div","bar");
        const filled=element("i");filled.style.width=Math.min(100,value/65*100).toFixed(1)+"%";
        track.append(filled);row.append(track);
        row.append(element("b",null,value.toFixed(1)+"%"));
        lines.append(row);
      }
      group.append(lines);chart.append(group);
    }
  }
  async function openSource(file,line=1){
    s.sourceFile=file;s.sourceLine=line;
    tab("source");
    document.querySelectorAll("[data-source]").forEach(btn=>btn.classList.toggle("active",btn.dataset.source===file));
    try{
      const data=await api("/api/source?file="+encodeURIComponent(file)+"&line="+line+"&context=85");
      $("editorPath").textContent=data.path+" : L"+data.focus;
      $("editorLink").href=data.url;
      const area=$("editorCode");area.replaceChildren();
      for(const row of data.lines){
        const el=element("div","source-line"+(row.line===data.focus?" highlight":""));
        el.append(element("span",null,row.line));
        el.append(element("code",null,row.code));
        area.append(el);
      }
      const focus=area.querySelector(".highlight");
      if(focus)area.scrollTop=Math.max(0,focus.offsetTop-area.offsetTop-area.clientHeight*.3);
    }catch(e){error(e);}
  }
  function tab(name){
    s.tab=name;
    const names=["play","source","research"];
    for(const key of names){
      $("view"+key[0].toUpperCase()+key.slice(1)).classList.toggle("hidden",key!==name);
      const b=document.querySelector("[data-tab='"+key+"']");
      b.classList.toggle("active",key===name);
      b.setAttribute("aria-selected",String(key===name));
    }
  }
  function setupSettings(){
    let stored=null;
    try{stored=localStorage.getItem("wsp-lab-theme");}catch(_){}
    s.theme=stored==="dark"||stored==="light"?stored:
      (window.matchMedia&&window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");
    function paint(){
      document.documentElement.dataset.theme=s.theme;
      document.documentElement.style.colorScheme=s.theme;
      $("theme").textContent=s.theme==="dark"?"☀ ライト":"☾ ダーク";
    }
    paint();
    $("theme").onclick=()=>{
      s.theme=s.theme==="dark"?"light":"dark";paint();
      try{localStorage.setItem("wsp-lab-theme",s.theme);}catch(_){}
    };
    let font=1;
    try{const v=Number(localStorage.getItem("wsp-lab-font"));if(v>=1&&v<=1.75)font=v;}catch(_){}
    function setFont(v){
      font=Math.max(1,Math.min(1.75,v));
      document.documentElement.style.setProperty("--scale",String(font));
      $("fontText").textContent=Math.round(font*100)+"%";
      try{localStorage.setItem("wsp-lab-font",String(font));}catch(_){}
    }
    setFont(font);
    $("fontDown").onclick=()=>setFont(font-.25);
    $("fontUp").onclick=()=>setFont(font+.25);
    $("projector").onclick=()=>{
      s.project=!s.project;
      document.documentElement.dataset.present=s.project?"on":"off";
      $("projector").setAttribute("aria-pressed",String(s.project));
      $("projector").textContent=s.project?"発表終了":"発表";
      if(s.project&&font<1.25)setFont(1.25);
    };
  }
  async function init(){
    setupSettings();renderInputs();renderDiagram();
    document.querySelectorAll("[data-tab]").forEach(button=>button.onclick=()=>tab(button.dataset.tab));
    document.querySelectorAll("[data-stage]").forEach(button=>button.onclick=()=>stageAt(Number(button.dataset.stage)));
    $("stageFirst").onclick=()=>stageAt(0);
    $("stagePrevious").onclick=()=>stageAt(s.stage-1);
    $("stagePlay").onclick=play;
    $("stageNext").onclick=()=>stageAt(s.stage+1);
    $("stageLast").onclick=()=>stageAt(4);
    $("stageSeek").oninput=event=>stageAt(Number(event.target.value));
    $("stageSpeed").onclick=()=>{
      s.speed=s.speed===1?2:s.speed===2?4:s.speed===4?.5:1;
      $("stageSpeed").textContent="×"+s.speed;
      if(s.timer!==null){stop();play();}
    };
    $("evaluate").onclick=calculate;
    $("applyChanges").onclick=()=>{stageAt(4);calculate();};
    $("restore").onclick=()=>{s.disabled.clear();$("customRule").value="";calculate();};
    $("searchButton").onclick=searchFacts;
    $("searchFacts").onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();searchFacts();}};
    document.querySelectorAll("[data-source]").forEach(button=>
      button.onclick=()=>openSource(button.dataset.source,Number(button.dataset.line)));
    document.addEventListener("keydown",e=>{
      if(s.tab!=="play"||["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName))return;
      if(e.code==="Space"){e.preventDefault();s.timer?stop():play();}
      if(e.code==="ArrowLeft"){e.preventDefault();stageAt(s.stage-1);}
      if(e.code==="ArrowRight"){e.preventDefault();stageAt(s.stage+1);}
    });
    try{
      s.catalog=await api("/api/catalog");
      const count=s.catalog.statistics.bundled_fact_rows;
      $("status").innerHTML="<i></i> 実際の公開知識行 "+num(count)+"件";
      renderScenarios();renderCatalog();
      await searchFacts();
      await openSource("arch.py",15);
      tab("play");
    }catch(e){error(e);$("status").textContent="データ取得エラー";}
  }
  document.addEventListener("DOMContentLoaded",init);
})();
