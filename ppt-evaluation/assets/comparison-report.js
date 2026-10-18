/* Shared weights across compared decks. No model calls or persistent storage. */
(function () {
  const data = JSON.parse(document.getElementById('comparison-data').textContent);
  const rules = [...document.querySelectorAll('[data-compare-rule]')];
  const layers = [...document.querySelectorAll('[data-compare-layer]')];
  const read = (nodes, key) => Object.fromEntries(nodes.map(n => [n.dataset[key], n.value.trim()==='' ? NaN : Number(n.value)]));
  const text = (s, value) => document.querySelectorAll(s).forEach(n => n.textContent = value);
  const fmt = n => n === null ? '—' : n.toFixed(1);
  const percent = n => n === null ? '—' : (n*100).toFixed(1)+'%';
  const rounded = n => Math.round((n+Number.EPSILON)*10)/10;
  const gap = (a,b) => { if(a===null||b===null)return '—';const d=rounded(rounded(a)-rounded(b));return (d>0?'+':'')+d.toFixed(1); };
  function update() {
    try {
      const weights=read(rules,'compareRule'), layerWeights=read(layers,'compareLayer');
      const scores=data.decks.map(d=>window.PPTScoreExplorer.calculate(d,weights,layerWeights));
      scores.forEach((score,n)=>{
        text('[data-composite="'+n+'"]',fmt(score.score));
        text('[data-coverage="'+n+'"]',percent(score.coverage));
        for (const [level,item] of Object.entries(score.layers)) {
          text('[data-score="'+n+'-'+level+'"]',fmt(item.score));
          text('[data-cell-coverage="'+n+'-'+level+'"]',percent(item.coverage));
          document.querySelector('[data-bar="'+n+'-'+level+'"]').style.width=(item.score===null?0:Math.max(0,Math.min(100,item.score)))+'%';
        }
      });
      if(scores.length===2) {
        const a=scores[0], b=scores[1];
        text('[data-comparison-gap]',a.score===null||b.score===null?'已评项目不足，暂不形成综合分差。':data.decks[0].label+' − '+data.decks[1].label+'：'+gap(a.score,b.score)+' 分');
        for(const level of Object.keys(a.layers)) text('[data-gap="'+level+'"]',gap(a.layers[level].score,b.layers[level].score));
      }
      text('[data-comparison-scope]',scores.some(s=>s.excluded)?'当前权重排除了部分视角或维度；这是自定义范围的比较，不代表全范围完整分。':'统一权重已应用于全部参评PPT；未知项保留在覆盖率中。');
      text('[data-comparison-error]','');
    } catch(e) {
      text('[data-composite]','—');text('[data-coverage]','—');text('[data-score]','—');text('[data-cell-coverage]','—');text('[data-gap]','—');
      document.querySelectorAll('[data-bar]').forEach(n=>n.style.width='0%');
      text('[data-comparison-gap]','');text('[data-comparison-scope]','');text('[data-comparison-error]',e.message);
    }
  }
  [...rules,...layers].forEach(n=>n.addEventListener('input',update));
  document.getElementById('reset-comparison').addEventListener('click',()=>{[...rules,...layers].forEach(n=>n.value=n.defaultValue);update();});
  document.querySelectorAll('button[data-view]').forEach(button=>button.addEventListener('click',()=>{
    const view=button.dataset.view;
    document.querySelectorAll('.compare-nav [data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
    document.getElementById('comparison').hidden=view!=='overview';
    document.querySelectorAll('.detail-report').forEach((frame,n)=>{frame.hidden=String(n)!==view;if(!frame.hidden&&!frame.getAttribute('src'))frame.src=frame.dataset.src;});
    window.scrollTo({top:0});
  }));
  update();
})();
