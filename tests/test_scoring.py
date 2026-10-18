import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ppt-evaluation/scripts'))
from protocol import normalize_stage, deduplicate, apply_decisions
from report import aggregate, refresh, render
from review import review_result
from evaluate import judge_info

class PageProtocol(unittest.TestCase):
    def setUp(self):
        self.rules=[{'id':'O01','level':'object','weight':1,'name':'文字'}, {'id':'O02','level':'object','weight':1,'name':'事实'}, {'id':'S01','level':'slide','weight':1,'name':'主旨'}, {'id':'D01','level':'deck','weight':1,'name':'任务'}, {'id':'D07','level':'deck','weight':1,'name':'讲稿'}]
        self.manifest={'evaluation_unit':'rendered_page','pages':[{'page':1,'objects':[{'id':'native-a'}]},{'page':2,'objects':[{'id':'b'},{'id':'c'}]}],'page_mapping_status':'EXPLICIT_SOURCE_PAGE_MAP'}
        self.context={'query':'two-page review','facts':[{'id':'F1','subject':'Example','metric':'revenue','period':'FY2025','unit':'USD million','value':120,'source':{'locator':'table 1'}}]}
    def good(self,r='S01',p=1):return {'rule_id':r,'page':p,'target_id':'deck'if p is None else f'slide-{p}','status':'GOOD','rating':4,'evidence':['可见完整标题和支撑关系'],'reason':'可读证据','issues':[]}
    def defect(self,r='O01',p=1):
        a=self.good(r,p);a.update(status='BAD',rating=2,issues=[{'kind':'text','location':'左上标题','quote':'revenuee','problem':'标题拼写错误','repair':'改为revenue','severity':'P2','requires_redraw':False}]);return a
    def normalize(self,items,page=1,rules=None):return normalize_stage({'assessments':items},rules or [r for r in self.rules if (r['level']=='deck')==(page is None)],page,self.context,{1,2})
    def test_native_objects_not_a_request_requirement(self):
        info=judge_info('page',self.manifest['pages'][0],self.context,self.rules,[],[])
        self.assertNotIn('native-a',json.dumps(info));self.assertNotIn('objects',info)
    def test_no_object_inventory_needed_for_page_checks(self):
        rows,events,_=self.normalize([self.good('O01'),self.good()]);self.assertEqual(sum(r['rating']is not None for r in rows),2)
    def test_one_wrong_target_does_not_discard_other_checks(self):
        bad=self.good('O01');bad['target_id']='native-a';rows,events,_=self.normalize([bad,self.good()]);by={a['rule_id']:a for a in rows}
        self.assertIsNone(by['O01']['rating']);self.assertEqual(by['S01']['rating'],4);self.assertTrue(events)
    def test_wrong_source_page_is_isolated(self):
        bad=self.good('O01',2);rows,_,_=self.normalize([bad,self.good()]);self.assertEqual(next(r for r in rows if r['rule_id']=='S01')['rating'],4);self.assertIsNone(next(r for r in rows if r['rule_id']=='O01')['rating'])
    def test_native_object_count_does_not_change_grade(self):
        a=[self.good('O01',1),self.good('O01',2)];first=aggregate(a,self.rules,manifest=self.manifest,context=self.context)
        other=copy.deepcopy(self.manifest);other['pages'][0]['objects']=[{'id':str(n)}for n in range(200)]
        second=aggregate(a,self.rules,manifest=other,context=self.context);self.assertEqual(first,second)
    def test_missing_page_remains_in_denominator(self):
        s=aggregate([self.good()],self.rules,manifest=self.manifest,context=self.context)
        self.assertEqual(s['levels']['slide']['coverage'],.5);self.assertIsNone(s['levels']['slide']['complete_score'])
    def test_na_requires_reason(self):
        a=self.good();a.update(status='NOT_APPLICABLE',rating=None,reason='');rows,events,_=self.normalize([a]);self.assertEqual(next(r for r in rows if r['rule_id']=='S01')['status'],'UNCERTAIN')
    def test_unscored_missing_rating_is_canonical_null(self):
        for state in ['UNCERTAIN', 'NOT_APPLICABLE']:
            with self.subTest(state=state):
                a=self.good();a.update(status=state,reason='No image or insufficient evidence');a.pop('rating')
                rows,events,_=self.normalize([a]);row=next(x for x in rows if x['rule_id']=='S01')
                self.assertIn('rating',row);self.assertIsNone(row['rating']);self.assertEqual(row['status'],state)
                aggregate(rows,self.rules,manifest=self.manifest,context=self.context)
    def test_scored_missing_rating_is_isolated(self):
        a=self.good('O01');a.pop('rating');rows,events,_=self.normalize([a,self.good()]);by={r['rule_id']:r for r in rows}
        self.assertIsNone(by['O01']['rating']);self.assertEqual(by['S01']['rating'],4);self.assertTrue(events)
    def test_missing_fact_cannot_be_false(self):
        a=self.defect('O02');a['issues'][0]['kind']='factual';rows,events,candidates=self.normalize([a]);self.assertIsNone(next(r for r in rows if r['rule_id']=='O02')['rating']);self.assertTrue(candidates)
    def test_numeric_source_proof_and_rounding(self):
        a=self.defect('O02');a['issues'][0].update(kind='factual',proof={'type':'source','fact_id':'F1','claim':{'subject':'Example','metric':'revenue','period':'FY2025','unit':'USD million','value':'80','quote':'Revenue 80'}})
        rows,_,_=self.normalize([a]);self.assertEqual(rows[0]['rating'],2)
        a['issues'][0]['proof']['claim'].update(value='120',quote='Revenue 120');rows,_,_=self.normalize([a]);self.assertIsNone(rows[0]['rating'])
    def test_wrong_period_not_source_counterevidence(self):
        a=self.defect('O02');a['issues'][0].update(kind='factual',proof={'type':'source','fact_id':'F1','claim':{'subject':'Example','metric':'revenue','period':'FY2024','unit':'USD million','value':'80','quote':'Revenue 80'}})
        rows,_,_=self.normalize([a]);self.assertIsNone(rows[0]['rating'])
    def test_missing_script_never_na_or_full_score(self):
        a=self.good('D07',None);rows,_,_=self.normalize([a],None);d=next(r for r in rows if r['rule_id']=='D07');self.assertEqual(d['status'],'UNCERTAIN')
    def test_same_fact_different_model_ids_only_charged_once(self):
        def row(r,p):
            a=self.defect(r,p);a['issues'][0].update(kind='factual',id='invented-'+r,root_defect_id='invented-'+r,proof={'type':'source','fact_id':'F1','claim':{'subject':'Example','metric':'revenue','period':'FY2025','unit':'USD million','value':'80','quote':'Revenue 80'}});return a
        a,_,_=self.normalize([row('O02',1)]);b,_,_=self.normalize([row('O02',2)],2);rows,merges=deduplicate(a+b)
        self.assertEqual(sum(len(r['issues'])for r in rows),1);self.assertEqual(len(merges),1)
    def test_required_chart_missing_charged_once_across_layers(self):
        self.context['requirements']=[{'id':'R1','text':'required chart'}]
        page=self.defect('S01');page['issues'][0].update(kind='chart',requirement_id='R1')
        deck=self.defect('D01',None);deck['issues'][0].update(kind='task',requirement_id='R1',affected_pages=[1])
        a,_,_=self.normalize([page]);b,_,_=self.normalize([deck],None)
        rows,merges=deduplicate(a+b)
        issues=[i for r in rows for i in r['issues']]
        self.assertEqual(len(issues),1);self.assertEqual(issues[0]['primary_rule'],'D01');self.assertTrue(merges)
    def test_page_issue_cannot_claim_other_pages(self):
        page=self.defect();page['issues'][0]['affected_pages']=[1,2]
        rows,_,candidates=self.normalize([page]);self.assertIsNone(rows[0]['rating']);self.assertTrue(candidates)
    def test_semantic_review_merge_not_automatic_full_grade(self):
        a,_,_=self.normalize([self.defect()]);braw=self.defect('S01');braw['issues'][0]['location']='上方标题区';b,_,_=self.normalize([braw]);rows=[a[0],next(x for x in b if x['rule_id']=='S01')];owner=rows[0]['issues'][0]['id'];loser=rows[1]['issues'][0]['id']
        reviewed,errors=apply_decisions(rows,[{'issue_id':loser,'action':'merge','merge_into':owner,'reason':'同一标题错字'}]);self.assertFalse(errors);self.assertEqual(reviewed[1]['status'],'UNCERTAIN');self.assertEqual(len(reviewed[0]['issues']),1)
    def test_review_cycle_rejected(self):
        a,_,_=self.normalize([self.defect()]);braw=self.defect('S01');braw['issues'][0]['location']='右侧';b,_,_=self.normalize([braw]);rows=[a[0],next(x for x in b if x['rule_id']=='S01')];x,y=[r['issues'][0]['id']for r in rows]
        _,errors=apply_decisions(rows,[{'issue_id':x,'action':'merge','merge_into':y,'reason':'x'},{'issue_id':y,'action':'merge','merge_into':x,'reason':'y'}]);self.assertTrue(errors)
    def test_removed_defect_disappears_from_final_summary(self):
        rows,_,_=self.normalize([self.defect()]);d={'schema_version':'ppt-evaluation-result@0.2.0','manifest':self.manifest,'context':self.context,'assessments':rows,'layer_weights':None,'model_history':[{'summary':'标题拼写错误'}]};refresh(d,self.rules);issue=d['scores']['issues'][0]['id']
        reviewed=review_result(d,[{'issue_id':issue,'action':'drop','reason':'识字误判'}],'unit reviewer',self.rules)
        self.assertEqual(reviewed['final_summary']['open_issues'],[]);self.assertIn('标题拼写错误',reviewed['model_history'][0]['summary']);self.assertIsNone(reviewed['assessments'][0]['rating'])
    def test_invalid_good_with_defect_is_not_accepted(self):
        a=self.defect();a.update(status='GOOD',rating=3);rows,_,_=self.normalize([a]);self.assertIsNone(rows[0]['rating'])
    def test_conflicting_duplicate_rows_not_cherry_picked(self):
        a=self.good();b=self.good();b['rating']=3;rows,_,_=self.normalize([a,b]);self.assertEqual(next(x for x in rows if x['rule_id']=='S01')['status'],'UNCERTAIN')
    def test_legacy_manifest_rejected_explicitly(self):
        m=copy.deepcopy(self.manifest);m.pop('evaluation_unit')
        with self.assertRaises(ValueError):aggregate([],self.rules,manifest=m)

if __name__=='__main__':unittest.main()
