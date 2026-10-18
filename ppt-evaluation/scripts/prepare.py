#!/usr/bin/env python3
"""Read-only ordered PPTX/slide-image inventory; does not claim visual validation."""
import argparse,hashlib,json,re,posixpath
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from PIL import Image
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def order(p):return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',p.name)]
def relationships(z,path):
 return {e.get('Id'):e.attrib for e in ET.fromstring(z.read(path))} if path in z.namelist() else {}
def resolve(path,target):return posixpath.normpath(posixpath.join(posixpath.dirname(path),target))
def pptx_inventory(path):
 with ZipFile(path) as z:
  pr=ET.fromstring(z.read('ppt/presentation.xml'));size=pr.find('p:sldSz',NS);w,h=int(size.get('cx')),int(size.get('cy'));rels=relationships(z,'ppt/_rels/presentation.xml.rels');slides=[]
  for index,ref in enumerate(pr.findall('p:sldIdLst/p:sldId',NS),1):
   file=resolve('ppt/presentation.xml',rels[ref.get('{'+NS['r']+'}id')]['Target']);root=ET.fromstring(z.read(file));srels=relationships(z,posixpath.dirname(file)+'/_rels/'+posixpath.basename(file)+'.rels');objects=[]
   for e in root.findall('p:cSld/p:spTree/*',NS):
    kind=e.tag.rsplit('}',1)[-1]
    if kind not in ['sp','pic','graphicFrame','grpSp','cxnSp']:continue
    nv=e.find('.//p:cNvPr',NS);text='\n'.join(t.text or '' for t in e.findall('.//a:t',NS));xfrm=e.find('.//a:xfrm',NS)
    if xfrm is None:xfrm=e.find('p:xfrm',NS)
    bbox=None
    if xfrm is not None:
     off=xfrm.find('a:off',NS);ext=xfrm.find('a:ext',NS)
     if off is not None and ext is not None:bbox=[round(int(off.get('x'))/w,5),round(int(off.get('y'))/h,5),round(int(ext.get('cx'))/w,5),round(int(ext.get('cy'))/h,5)]
    charts=[]
    for c in e.findall('.//c:chart',NS):
     rid=c.get('{'+NS['r']+'}id');rel=srels.get(rid)
     if rel:
      cf=resolve(file,rel['Target']);cr=ET.fromstring(z.read(cf));charts.append({'part':cf,'cached_values':[v.text for v in cr.findall('.//c:v',NS)]})
    oid=f'p{index}-o{nv.get("id")}' if nv is not None else f'p{index}-o{len(objects)+1}'
    objects.append({'id':oid,'kind':kind,'name':nv.get('name') if nv is not None else None,'text':text,'bbox_normalized':bbox,'bbox_status':'group_transform_unresolved' if kind=='grpSp' else 'approximate_shape_bounds','alt_text':nv.get('descr') if nv is not None else None,'charts':charts})
   notes=[]
   for rel in srels.values():
    if rel.get('Type','').endswith('/notesSlide'):
     nr=ET.fromstring(z.read(resolve(file,rel['Target'])))
     for sp in nr.findall('.//p:sp',NS):
      ph=sp.find('.//p:ph',NS)
      if ph is not None and ph.get('type')=='body':notes.extend(t.text or '' for t in sp.findall('.//a:t',NS))
   candidates=[]
   for o in objects:
    b=o['bbox_normalized']
    if b and (b[0]<0 or b[1]<0 or b[0]+b[2]>1.001 or b[1]+b[3]>1.001):candidates.append({'object_id':o['id'],'kind':'bounds_candidate','not_a_quality_verdict':True,'reason':'May be intentional bleed/crop; verify visible information loss.'})
   slides.append({'page':index,'slide_part':file,'hidden':root.get('show')=='0','objects':objects,'geometry_candidates':candidates,'notes':'\n'.join(notes),'inventory_complete':False,'inventory_scope':'slide top-level objects only; group descendants and inherited master/layout objects require separate visual inventory'})
  return {'file':str(Path(path).resolve()),'sha256':digest(path),'width_emu':w,'height_emu':h,'slides':slides}
def prepare(images,pptx=None,page_map=None):
 files=sorted([f for f in Path(images).iterdir() if f.suffix.lower() in ['.png','.jpg','.jpeg','.webp']],key=order)
 if page_map:
  mapping=json.loads(Path(page_map).read_text());keys=sorted(int(k) for k in mapping)
  assert keys==list(range(1,len(keys)+1)),'Page map must be a consecutive source-page mapping'
  files=[Path(images)/mapping[str(k)] for k in keys]
  assert all(f.exists() for f in files) and len(set(files))==len(files),'Missing or repeated image in page map'
 if not files:raise ValueError('No page images; visual scoring requires actual rendered pixels.')
 inv=pptx_inventory(pptx) if pptx else None
 if inv and len(files)!=len(inv['slides']):raise ValueError('Image count must match all source slides, including hidden. Declare selection downstream.')
 pages=[]
 for i,f in enumerate(files,1):
  with Image.open(f) as im:dim=list(im.size)
  source=inv['slides'][i-1] if inv else {'objects':[],'hidden':False,'inventory_complete':False}
  pages.append({**source,'page':i,'image':str(f.resolve()),'image_sha256':digest(f),'image_size':dim,'viewed':False})
 return {'schema_version':'ppt-evaluation-input@0.2.0','evaluation_unit':'rendered_page','pages':pages,'source':{k:v for k,v in inv.items() if k!='slides'} if inv else {'type':'images'},'page_mapping_status':'EXPLICIT_SOURCE_PAGE_MAP' if page_map else 'INFERRED_FILENAME_ORDER_REQUIRES_REVIEW','render_surface':'caller supplied; record native/generic renderer in context','hidden_policy':'all included; flag hidden in report','coverage_note':'Native objects are optional support, never required grading targets. Image-to-source mapping and render clarity require review; grouped/inherited geometry is not resolved.'}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--images',required=True);ap.add_argument('--pptx');ap.add_argument('--page-map');ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(prepare(args.images,args.pptx,args.page_map),ensure_ascii=False,indent=2));print(str(out))
