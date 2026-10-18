"""Controller events against a small DOM fixture, not a real browser visual check."""
import shutil, subprocess, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ComparisonController(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node required for controller event test')
 def test_shared_weights_reset_invalid_input_and_report_navigation(self):
  script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const {calculate}=require(process.argv[1]);const levels=['object','slide','deck'];
const deck=(label,ratings)=>({label,report:label+'.html',page_count:8,mappingVerified:true,layers:Object.fromEntries(levels.map((l,n)=>[l,{complete_score:null,rules:[{rule_id:l,weight:1,mean_rating:ratings[n],coverage:.75,applicable:true}]}]))});
const data={decks:[deck('A',[2,4,3]),deck('B',[3,2,2])]};
const registry=new Map(),ids={},frames=[];
function el(dataset={},value=''){return {dataset,value,defaultValue:value,style:{},hidden:false,textContent:'',attrs:{},events:{},addEventListener(k,f){this.events[k]=f;},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]||null;}};}
function add(key,n){if(!registry.has(key))registry.set(key,[]);registry.get(key).push(n);return n;}
function field(attr,key){const n=el();add('['+attr+']',n);add('['+attr+'="'+key+'"]',n);return n;}
const ruleNodes=levels.map(l=>add('[data-compare-rule]',el({compareRule:l},'1')));
const layerNodes=levels.map(l=>add('[data-compare-layer]',el({compareLayer:l},'1')));
for(let n=0;n<2;n++){field('data-composite',n);field('data-coverage',n);for(const l of levels){field('data-score',n+'-'+l);field('data-cell-coverage',n+'-'+l);field('data-bar',n+'-'+l);}frames.push(el());frames[n].dataset.src=n+'.html';}
for(const l of levels)field('data-gap',l);
for(const a of ['data-comparison-gap','data-comparison-scope','data-comparison-error'])add('['+a+']',el());
ids['comparison-data']={textContent:JSON.stringify(data)};ids['reset-comparison']=el();ids.comparison=el();
const nav=['overview','0','1'].map(view=>el({view}));registry.set('button[data-view]',nav);registry.set('.compare-nav [data-view]',nav);registry.set('.detail-report',frames);
const fakeDocument={getElementById:k=>ids[k],querySelectorAll:k=>registry.get(k)||[],querySelector:k=>(registry.get(k)||[])[0]};
const fakeWindow={PPTScoreExplorer:{calculate},scrollTo(){}};vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{document:fakeDocument,window:fakeWindow});
assert.equal(fakeDocument.querySelector('[data-composite="0"]').textContent,'75.0');assert.equal(fakeDocument.querySelector('[data-composite="1"]').textContent,'58.3');
layerNodes[0].value='5';layerNodes[0].events.input();assert.equal(fakeDocument.querySelector('[data-composite="0"]').textContent,'60.7');assert.equal(fakeDocument.querySelector('[data-composite="1"]').textContent,'67.9');
layerNodes[0].value='-1';layerNodes[0].events.input();assert.equal(fakeDocument.querySelector('[data-composite="0"]').textContent,'—');assert.ok(fakeDocument.querySelector('[data-comparison-error]').textContent);
ids['reset-comparison'].events.click();assert.equal(fakeDocument.querySelector('[data-composite="0"]').textContent,'75.0');
nav[1].events.click();assert.equal(ids.comparison.hidden,true);assert.equal(frames[0].hidden,false);assert.equal(frames[0].src,'0.html');nav[0].events.click();assert.equal(ids.comparison.hidden,false);assert.ok(frames.every(f=>f.hidden));
console.log('PASS: both scores use common weights, invalid values clear, reset and tabs work');
'''
  r=subprocess.run(['node','-e',script,str(ROOT/'ppt-evaluation/assets/score-explorer.js'),str(ROOT/'ppt-evaluation/assets/comparison-report.js')],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)
