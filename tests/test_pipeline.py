"""Local protocol fixtures only: these are not real-provider quality measurements."""
import hashlib, json, os, subprocess, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image
SCRIPTS=Path(__file__).resolve().parents[1]/'ppt-evaluation/scripts'

class EndToEnd(unittest.TestCase):
    def run_pipeline(self,budget=3):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));received.append(data)
                text=data['messages'][1]['content'][0]['text'];info=json.loads(text.split('评审输入：\n')[1]);page=info['source_page'];rows=[]
                for r in info['rules']:
                    missing=r['id'] in ['O02','D07'];rows.append({'rule_id':r['id'],'status':'UNCERTAIN'if missing else'GOOD','rating':None if missing else 3,'reason':'synthetic fixture; unavailable source/script'if missing else'fixture evidence','evidence':[]if missing else['Synthetic fixture: visible text'],'issues':[]})
                if page==1:rows[0]['target_id']='native-object-wrong'
                payload={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'summary':'synthetic local fixture, not a real evaluation','assessments':rows,'review_decisions':[]})}}],'model':'synthetic-fixture','usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
                body=json.dumps(payload).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory()as folder:
                p=Path(folder);pages=[]
                for n in [1,2]:
                    f=p/f'{n}.png';Image.new('RGB',(800,450),'white').save(f);pages.append({'page':n,'image':str(f),'image_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'objects':[{'id':'native-secret-id'}]})
                (p/'manifest.json').write_text(json.dumps({'evaluation_unit':'rendered_page','pages':pages,'page_mapping_status':'EXPLICIT_SOURCE_PAGE_MAP'}));(p/'context.json').write_text(json.dumps({'query':'Synthetic two-page fixture; no private material','mode':'reading'}))
                cmd=[sys.executable,str(SCRIPTS/'evaluate.py'),'--manifest',str(p/'manifest.json'),'--context',str(p/'context.json'),'--out',str(p/'out'),'--base-url',f'http://127.0.0.1:{server.server_port}','--max-calls',str(budget),'--retries','0','--save-trace']
                r=subprocess.run(cmd,capture_output=True,text=True,env={**os.environ,'DEEPSEEK_API_KEY':'synthetic-local-test-key'});self.assertEqual(r.returncode,0,r.stderr);result=json.loads((p/'out/result.json').read_text());self.assertTrue((p/'out/report.html').exists());self.assertNotIn('synthetic-local-test-key',''.join(f.read_text()for f in (p/'out').glob('*.json')));self.assertNotIn('native-secret-id',json.dumps(received))
                return result,received
        finally:server.shutdown();server.server_close();thread.join()
    def test_page_then_deck_and_local_failure_isolation(self):
        d,requests=self.run_pipeline();self.assertEqual(len(requests),3);self.assertEqual(d['source_pages_missing'],[])
        a={(x['page'],x['rule_id']):x for x in d['assessments']};self.assertIsNone(a[(1,'O01')]['rating']);self.assertEqual(a[(1,'S01')]['rating'],3);self.assertEqual(a[(2,'O01')]['rating'],3)
        self.assertEqual(d['review']['status'],'COMPLETE');self.assertIsNone(d['scores']['overall_complete'])
    def test_call_budget_exhaustion_is_reported_as_unknown(self):
        d,requests=self.run_pipeline(1);self.assertEqual(len(requests),1);self.assertEqual(d['source_pages_missing'],[2]);self.assertEqual(d['review']['status'],'NOT_RUN');self.assertEqual(d['scores']['levels']['deck']['coverage'],0)
if __name__=='__main__':unittest.main()
