import copy,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ppt-evaluation/scripts'))
from reader_report import render_reader
from report import refresh

class ReaderReport(unittest.TestCase):
 def fixture(self,p):
  image=p/'page.png';Image.new('RGB',(160,90),'white').save(image)
  rules=[{'id':'O01','name':'文字正确','level':'object','weight':1},{'id':'S01','name':'主旨证据','level':'slide','weight':1},{'id':'D01','name':'任务覆盖','level':'deck','weight':1},{'id':'D02','name':'故事线','level':'deck','weight':1}]
  rows=[]
  for rid,page in [('O01',1),('O01',2),('S01',1),('S01',2),('D01',None),('D02',None)]:
   rows.append({'rule_id':rid,'page':page,'target_id':'deck'if page is None else f'slide-{page}','status':'GOOD','rating':3,'evidence':['可见按问题、证据、行动推进'],'reason':'STALE_REMOVED_ERROR','issues':[]})
  row=rows[0];row.update(status='BAD',rating=2,issues=[{'id':'visible-1','root_defect_id':'root-1','primary_rule':'O01','affected_pages':[1],'problem':'标题错字','repair':'改正标题并复看','location':'左上标题','severity':'P2','requires_redraw':False}])
  d={'schema_version':'ppt-evaluation-result@0.2.0','rubric_version':'test','manifest':{'evaluation_unit':'rendered_page','page_mapping_status':'EXPLICIT_SOURCE_PAGE_MAP','pages':[{'page':1,'image':str(image)},{'page':2,'image':str(image)}]},'context':{'query':'synthetic two-page deck'},'assessments':rows,'layer_weights':None,'process':{'secret_debug_marker':'DEBUG_ONLY_123'},'model_history':[{'summary':'STALE_HISTORY_ABC'}]};refresh(d,rules);return d,rules
 def test_only_problem_pages_are_expanded_and_no_stale_narrative(self):
  with tempfile.TemporaryDirectory()as t:
   p=Path(t);d,rules=self.fixture(p);before=copy.deepcopy(d['assessments']);render_reader(d,p/'report.html',rules);main=(p/'report.html').read_text();debug=(p/'report-debug.html').read_text()
   self.assertIn('id="page-1"',main);self.assertNotIn('id="page-2"',main);self.assertIn('第2页原图',main);self.assertIn('标题错字',main);self.assertNotIn('STALE_REMOVED_ERROR',main);self.assertNotIn('STALE_HISTORY_ABC',main);self.assertNotIn('DEBUG_ONLY_123',main);self.assertIn('DEBUG_ONLY_123',debug);self.assertIn('STALE_HISTORY_ABC',debug);self.assertEqual(d['assessments'],before)
 def test_deck_issue_is_associated_but_counted_once(self):
  with tempfile.TemporaryDirectory()as t:
   p=Path(t);d,rules=self.fixture(p);d['assessments'][4].update(status='BAD',rating=1,issues=[{'id':'d1','root_defect_id':'deck1','primary_rule':'D01','affected_pages':[1,2],'problem':'缺规定图表','repair':'补图','location':'两页图表区','severity':'P1','requires_redraw':True}]);refresh(d,rules);render_reader(d,p/'report.html',rules)
   main=(p/'report.html').read_text();self.assertIn('id="page-2"',main);self.assertIn('全稿只计一次',main);self.assertEqual(len(d['scores']['issues']),2)
 @unittest.skipUnless(shutil.which('node'),'Node needed for browser calculation parity test')
 def test_weight_engine_missing_values_page_weights_and_scope(self):
  js=str(ROOT/'ppt-evaluation/assets/score-explorer.js')
  script=r'''const {calculate}=require(process.argv[1]);const assert=require('node:assert/strict');
  const rule=(id,mean,coverage=1)=>({rule_id:id,mean_rating:mean,coverage,applicable:true});
  const data={mappingVerified:true,layers:{object:{complete_score:null,rules:[rule('O1',2),rule('O2',null,0)]},slide:{complete_score:100,rules:[rule('S1',4)]},deck:{complete_score:75,rules:[rule('D1',3)]}},pages:[{page:1,rows:[{rule_id:'O1',level:'object',rating:2,status:'BAD'},{rule_id:'O2',level:'object',rating:null,status:'UNCERTAIN'},{rule_id:'S1',level:'slide',rating:4,status:'GOOD'}]}]};
  const w={O1:1,O2:1,S1:1,D1:1},l={object:1,slide:1,deck:1};let x=calculate(data,w,l);assert.equal(x.layers.object.score,50);assert.equal(x.layers.object.coverage,.5);assert.equal(x.score,75);assert.equal(x.complete,null);
  x=calculate(data,{...w,O2:0},l);assert.equal(x.layers.object.coverage,1);assert.equal(x.complete,null);assert.equal(x.excluded,1);
  assert.throws(()=>calculate(data,{...w,O1:-1},l));assert.throws(()=>calculate(data,w,{object:0,slide:0,deck:0}));
  data.layers.object.rules[1]=rule('O2',4);data.pages[0].rows[1]={rule_id:'O2',level:'object',rating:4,status:'GOOD'};x=calculate(data,w,l);assert.equal(x.pages[1].object,75);x=calculate(data,{...w,O2:3},l);assert.equal(x.pages[1].object,87.5);assert.equal(x.layers.object.score,87.5);
  console.log('PASS');'''
  p=subprocess.run(['node','-e',script,js],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
if __name__=='__main__':unittest.main()
