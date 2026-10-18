/* One set of weights for every evidence-bound report; no model calls. */
(function () {
 const data=JSON.parse(document.getElementById('comparison-data').textContent);
 const rules=[...document.querySelectorAll('[data-compare-rule]')],layers=[...document.querySelectorAll('[data-compare-layer]')];
 const read=(nodes,key)=>Object.fromEntries(nodes.map(n=>[n.dataset[key],n.value.trim()===''?NaN:Number(n.value)]));
 const text=(s,value)=>document.querySelectorAll(s).forEach(n=>n.textContent=value);
 const fmt=n=>n===null?'—':n.toFixed(1);
 function update(){
  try{
   const weights=read(rules,'compareRule'),layerWeights=read(layers,'compareLayer');
   const scores=data.decks.map(d=>{const x=window.PPTScoreExplorer.calculate(d,weights,layerWeights);if(d.evaluationFailed)x.score=null;return x;});
   scores.forEach((score,n)=>{
    text('[data-composite="'+n+'"]',fmt(score.score));
    for(const[level,item]of Object.entries(score.layers)){
     text('[data-score="'+n+'-'+level+'"]',fmt(item.score));text('[data-insight-score="'+n+'-'+level+'"]',fmt(item.score));
     const bar=document.querySelector('[data-bar="'+n+'-'+level+'"]');if(bar)bar.style.width=(item.score===null?0:Math.max(0,Math.min(100,item.score)))+'%';
     const active=data.decks[n].layers[level].rules.filter(r=>r.applicable&&r.mean_rating!==null&&weights[r.rule_id]>0),den=active.reduce((sum,r)=>sum+weights[r.rule_id],0);
     data.decks[n].layers[level].rules.forEach(r=>text('[data-rule-loss="'+n+'-'+level+'-'+r.rule_id+'"]',den?((100-r.mean_rating*25)*(weights[r.rule_id]||0)/den).toFixed(2):'—'));
    }
   });
   const valid=scores.every(s=>s.score!==null);let verdict='本轮评测未完成，暂不比较作品';
   if(valid){const rounded=scores.map(s=>Math.round(s.score*10)/10),best=Math.max(...rounded),winner=rounded.map((s,n)=>s===best?n:null).filter(n=>n!==null);verdict=winner.length>1?'本轮综合评分并列':'本轮胜出：'+data.decks[winner[0]].label;}
   text('[data-verdict]',verdict);
   const custom=[...rules,...layers].some(n=>n.value!==n.defaultValue);
   document.querySelectorAll('[data-baseline-insight]').forEach(n=>n.hidden=custom);
   document.querySelectorAll('[data-custom-verdict]').forEach(n=>n.hidden=!custom);
   text('[data-comparison-scope]',scores.some(s=>s.excluded)?'部分视角或维度权重为0，当前评分按自定义范围汇总。':'统一权重已应用于全部参评PPT。');text('[data-comparison-error]','');
  }catch(e){text('[data-composite]','—');text('[data-score]','—');text('[data-insight-score]','—');text('[data-verdict]','评分权重配置无效');text('[data-comparison-scope]','');text('[data-comparison-error]',e.message);document.querySelectorAll('[data-bar]').forEach(n=>n.style.width='0%');}
 }
 [...rules,...layers].forEach(n=>n.addEventListener('input',update));
 document.getElementById('reset-comparison').addEventListener('click',()=>{[...rules,...layers].forEach(n=>n.value=n.defaultValue);update();});
 document.querySelectorAll('button[data-view]').forEach(button=>button.addEventListener('click',()=>{
  const view=button.dataset.view;document.querySelectorAll('.compare-nav [data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));document.getElementById('comparison').hidden=view!=='overview';
  document.querySelectorAll('.detail-report').forEach((frame,n)=>{frame.hidden=String(n)!==view;if(!frame.hidden&&!frame.getAttribute('src'))frame.src=frame.dataset.src;});window.scrollTo({top:0});
 }));
 const dialog=document.getElementById('insight-lightbox');
 if(dialog){document.querySelectorAll('[data-insight-zoom]').forEach(b=>b.addEventListener('click',()=>{const img=b.querySelector('img');dialog.querySelector('img').src=img.src;dialog.querySelector('img').alt=img.alt;dialog.querySelector('p').textContent=img.alt;dialog.showModal();}));dialog.querySelector('button').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});}
 update();
})();
