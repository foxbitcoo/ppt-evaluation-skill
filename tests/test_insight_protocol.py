import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ppt-evaluation/scripts'))
from insight_report import validate_insights
from analyze_comparison import recover_level_delimiters
class InsightBindings(unittest.TestCase):
 def fixture(self):
  entries=[]
  for ident in ['a','b']:
   result={'manifest':{'pages':[{'page':1}]},'scores':{'levels':{l:{'observed_score':50}for l in ['object','slide','deck']}},'insight_evidence':[{'id':ident+'-E1','page_numbers':[1]}]}
   entries.append({'id':ident,'label':ident,'result':result})
  sections=[]
  for level in ['object','slide','deck']:
   profiles=[]
   for ident in ['a','b']:profiles.append({'deck_id':ident,'score_100':50,'summary':'test','strengths':[{'text':'test','evidence_ids':[ident+'-E1'],'refs':[{'deck_id':ident,'page_numbers':[1],'scope':'pages'}]}],'deductions':[]})
   sections.append({'level':level,'decks':profiles,'pairwise':[]})
  return entries,{'headline':{'winner_ids':['a','b'],'score_lines':[{'deck_id':'a','score_100':50},{'deck_id':'b','score_100':50}]},'level_sections':sections,'iteration_plan':[]}
 def test_valid_score_and_page_bindings(self):
  entries,d=self.fixture();self.assertIs(validate_insights(d,entries),d)
 def test_wrong_page_or_score_is_not_accepted(self):
  for field in ['page','score','winner']:
   entries,d=self.fixture()
   if field=='page':d['level_sections'][0]['decks'][0]['strengths'][0]['refs'][0]['page_numbers']=[2]
   if field=='score':d['headline']['score_lines'][0]['score_100']=99
   if field=='winner':d['headline']['winner_ids']=['b']
   with self.assertRaises(ValueError):validate_insights(d,entries)
 def test_format_recovery_only_closes_known_schema_delimiters(self):
  raw='{"headline":{},"level_sections":[{"level":"object", "level": "slide", "level": "deck", "iteration_plan":[], "quality_flags":[], "evaluator_notes":[]}'
  repaired=recover_level_delimiters(raw);self.assertEqual([x['level']for x in repaired['level_sections']],['object','slide','deck']);self.assertEqual(repaired['iteration_plan'],[])
 def test_unrecognized_broken_output_is_not_fabricated(self):
  with self.assertRaises(ValueError):recover_level_delimiters('{"headline":')
if __name__=='__main__':unittest.main()
