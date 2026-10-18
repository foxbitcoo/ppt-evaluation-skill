import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ppt-evaluation/scripts'))
from protocol import unknown
from report import refresh
from insight_report import total_score
class DeliveryPolicy(unittest.TestCase):
 def fixture(self,reason='Insufficient evidence for ideal delivery'):
  rules=[{'id':rid,'name':rid,'level':lev,'weight':1}for rid,lev in [('O02','object'),('S01','slide'),('D07','deck')]]
  rows=[unknown('O02',1,reason),unknown('S01',1,reason),unknown('D07',None,reason)]
  d={'manifest':{'evaluation_unit':'rendered_page','page_mapping_status':'EXPLICIT_SOURCE_PAGE_MAP','pages':[{'page':1}]},'context':{'score_policy':'ideal-delivery@0.3.0'},'assessments':rows,'layer_weights':[1,1,1],'source_pages_missing':[]}
  return d,rules
 def test_all_quality_evidence_gaps_score_40_without_faking_truth(self):
  d,r=self.fixture();d['assessments'][-1]['reason']='No supplied script';before=copy.deepcopy(d['assessments']);refresh(d,r)
  self.assertEqual(total_score(d),40);self.assertEqual(d['assessments'],before);self.assertTrue(all(a['rating']is None for a in d['assessments']));self.assertTrue(all(v['observed_score']==40 for v in d['scores']['levels'].values()));self.assertTrue(all(i.get('truth_verdict')is False for i in d['scores']['issues']))
 def test_technical_failure_is_not_a_low_quality_grade(self):
  d,r=self.fixture('Required check omitted by model');refresh(d,r)
  self.assertIsNone(d['scores']['levels']['object']['observed_score']);self.assertIsNone(total_score(d));self.assertTrue(d['delivery']['evaluation_failures'])
 def test_reference_only_does_not_receive_another_gap_penalty(self):
  d,r=self.fixture();d['assessments'][1]['related_issue_ids']=['existing-owner'];d['assessments'][1]['reason']='Penalty removed/merged; independent replacement grade not established';refresh(d,r)
  row=d['delivery']['rows'][1];self.assertEqual(row['score_basis'],'reference_only');self.assertIsNone(row['effective_score']);self.assertFalse(any(i['primary_rule']=='S01'for i in d['scores']['issues']))
 def test_audit_scores_are_preserved_and_policy_is_opt_in(self):
  d,r=self.fixture();d['context'].pop('score_policy');refresh(d,r);self.assertNotIn('delivery',d);self.assertIsNone(d['scores']['levels']['object']['observed_score']);d['context']['score_policy']='ideal-delivery@0.3.0';refresh(d,r);self.assertIsNone(d['audit_scores']['levels']['object']['observed_score']);self.assertEqual(d['scores']['levels']['object']['observed_score'],40)
 def test_missing_script_has_explicit_deliverable_gap(self):
  d,r=self.fixture();refresh(d,r);a=next(i for i in d['scores']['issues']if i['primary_rule']=='D07');self.assertIn('讲稿',a['problem']);self.assertFalse(a['truth_verdict'])
if __name__=='__main__':unittest.main()
