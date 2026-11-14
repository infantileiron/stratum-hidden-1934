import hashlib,json,math,threading
from src.constants.domain import DEPTH_STEP_M,MAX_FRAGMENTS_PER_BATCH,MAX_MISSING_PREVIEW
from src.constants.enums import BatchStatus,FragmentStatus
from src.models.entities import IngestBatch,IngestFragment,BoreholeDataset
from src.services.observations import parse_fragment_rows
from src.utils import repository as repo
from src.utils.identity import new_id,now
_SERIAL=threading.RLock()
def _row_key(row):return (row['borehole'],row['depth_m'])
def _checksum(rows):
 payload=json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
 return hashlib.sha256(payload.encode()).hexdigest()
def _load_batch(batch_id):return repo.get('ingest_batches',batch_id)
def _fragments(batch_id):
 out=[f for f in repo.all_rows('ingest_fragments') if f['batch_id']==batch_id]
 out.sort(key=lambda f:(f['fragment_no'],f['received_at']))
 return out
def _store_batch(b):return repo.put('ingest_batches',b)
def _store_fragment(f):return repo.put('ingest_fragments',f)
def _coverage(batch):
 by_hole={}
 for f in _fragments(batch['id']):
  if f['status']!=FragmentStatus.ACCEPTED.value:continue
  for r in json.loads(f.get('payload_rows') or '[]'):by_hole.setdefault(r['borehole'],set()).add(r['depth_m'])
 return by_hole
def _missing(batch):
 out={}
 for hole,depths in _coverage(batch).items():
  if not depths:continue
  lo,hi=min(depths),max(depths);gaps=[]
  d=lo+DEPTH_STEP_M
  while d<hi-1e-9:
   if not any(math.isclose(d,x,rel_tol=0,abs_tol=1e-9) for x in depths):gaps.append(round(d,6))
   d+=DEPTH_STEP_M
  if gaps:out[hole]=gaps
 return out
def _fmt_depth(d):return ('%f'%d).rstrip('0').rstrip('.')
def _summary(batch):
 fs=_fragments(batch['id'])
 accepted=[f for f in fs if f['status']==FragmentStatus.ACCEPTED.value]
 rejected=[f for f in fs if f['status']==FragmentStatus.REJECTED.value]
 duplicates=[f for f in fs if f['status']==FragmentStatus.DUPLICATE.value]
 missing=_missing(batch)
 reading_count=sum(len(json.loads(f.get('payload_rows') or '[]')) for f in accepted)
 ok_fragments=len(accepted)+len(duplicates)
 expected=batch.get('expected_fragments') or 0
 return {'fragment_total':len(fs),'accepted_fragments':len(accepted),'rejected_fragments':len(rejected),
  'duplicate_fragments':len(duplicates),'reading_count':reading_count,
  'borehole_count':len(_coverage(batch)),'expected_fragments':expected,
  'expected_complete':not expected or ok_fragments>=expected,
  'missing':{h:(v[:MAX_MISSING_PREVIEW]) for h,v in missing.items()},
  'missing_count':sum(len(v) for v in missing.values()),
  'missing_truncated':any(len(v)>MAX_MISSING_PREVIEW for v in missing.values()),
  'complete':not missing and reading_count>0,
  'sealed':batch['status'] in (BatchStatus.SEALED.value,BatchStatus.PUBLISHED.value),
  'published':batch['status']==BatchStatus.PUBLISHED.value}
def list_batches():
 out=[]
 for b in repo.all_rows('ingest_batches'):
  item=dict(b);item.update(_summary(b));out.append(item)
 return out
def detail(batch_id):
 b=_load_batch(batch_id)
 item=dict(b)
 item['fragments']=[{k:v for k,v in f.items() if k!='payload_rows'} for f in _fragments(batch_id)]
 item.update(_summary(b))
 if b['status']==BatchStatus.PUBLISHED.value and b.get('dataset_id'):
  item['dataset']=repo.get('datasets',b['dataset_id'])
 return item
def create_batch(data):
 with _SERIAL:
  b=IngestBatch(new_id('batch'),data.name,data.source,BatchStatus.RECEIVING.value,
   max(0,int(data.expected_fragments)),[],'','','',now())
  _store_batch(b)
  return detail(b.id)
def _next_fragment_no(fs):
 used={f['fragment_no'] for f in fs};no=1
 while no in used:no+=1
 return no
def _make_fragment(batch,no,rows,status,checksum,reason,new_count,dup_count):
 return IngestFragment(new_id('frag'),batch['id'],no,status,checksum,reason,len(rows),
  new_count,dup_count,sorted({r['borehole'] for r in rows}),
  min((r['depth_m'] for r in rows),default=None),max((r['depth_m'] for r in rows),default=None),now(),
  json.dumps(rows,ensure_ascii=False,allow_nan=False) if status==FragmentStatus.ACCEPTED.value else '')
def receive_fragment(batch_id,data):
 with _SERIAL:
  batch=_load_batch(batch_id)
  if batch['status']!=BatchStatus.RECEIVING.value:
   raise ValueError('批次已%s，迟到片段拒收；已发布数据与研究快照保持不变'%('封存' if batch['status']==BatchStatus.SEALED.value else '发布'))
  fs=_fragments(batch_id)
  if len(fs)>=MAX_FRAGMENTS_PER_BATCH:raise ValueError('单批次最多%d个片段'%MAX_FRAGMENTS_PER_BATCH)
  try:
   rows=parse_fragment_rows(data.csv_text)
  except ValueError as exc:
   no=data.fragment_no if data.fragment_no is not None else _next_fragment_no(fs)
   _store_fragment(_make_fragment(batch,no,[],FragmentStatus.REJECTED.value,_checksum([]),str(exc),0,0))
   return detail(batch_id)
  checksum=_checksum(rows)
  if data.fragment_no is not None:
   canonical=next((f for f in fs if f['fragment_no']==data.fragment_no and f['status']==FragmentStatus.ACCEPTED.value),None)
   if canonical is not None:
    if canonical['checksum']==checksum:
     _store_fragment(_make_fragment(batch,data.fragment_no,rows,FragmentStatus.DUPLICATE.value,checksum,
      '同号同文重传：与片段%d读数完全一致，不增加读数'%data.fragment_no,0,len(rows)))
     return detail(batch_id)
    _store_fragment(_make_fragment(batch,data.fragment_no,rows,FragmentStatus.REJECTED.value,checksum,
     '同号异文：片段%d已有不同读数（校验%s），整片拒收'%(data.fragment_no,canonical['checksum'][:12]),0,0))
    return detail(batch_id)
  prior={}
  for f in fs:
   if f['status']!=FragmentStatus.ACCEPTED.value:continue
   for r in json.loads(f.get('payload_rows') or '[]'):prior[_row_key(r)]=r
  new_rows=[];dup=0;conflicts=[]
  for row in rows:
   old=prior.get(_row_key(row))
   if old is None:new_rows.append(row);continue
   if old['value']==row['value'] and (old.get('truth') or None)==(row.get('truth') or None):dup+=1
   else:conflicts.append((_row_key(row),old,row))
  if conflicts:
   (hole,depth),old,row=conflicts[0]
   reason='重叠深度异值：%s深度%s已接收读数%r，新片段为%r，整片拒收'%(hole,_fmt_depth(depth),old['value'],row['value'])
   no=data.fragment_no if data.fragment_no is not None else _next_fragment_no(fs)
   _store_fragment(_make_fragment(batch,no,rows,FragmentStatus.REJECTED.value,checksum,reason,0,0))
   return detail(batch_id)
  no=data.fragment_no if data.fragment_no is not None else _next_fragment_no(fs)
  if not new_rows:
   _store_fragment(_make_fragment(batch,no,rows,FragmentStatus.DUPLICATE.value,checksum,
    '与已接收读数完全一致，重复片段不增加读数',0,dup))
   return detail(batch_id)
  reason='部分深度与已接收读数一致（%d点去重），新增%d点'%(dup,len(new_rows)) if dup else ''
  _store_fragment(_make_fragment(batch,no,new_rows,FragmentStatus.ACCEPTED.value,checksum,reason,len(new_rows),dup))
  batch['boreholes']=sorted(_coverage(batch));_store_batch(batch)
  return detail(batch_id)
def seal_batch(batch_id):
 with _SERIAL:
  batch=_load_batch(batch_id)
  if batch['status']==BatchStatus.PUBLISHED.value:raise ValueError('批次已发布，封存结果不可更改')
  if batch['status']==BatchStatus.SEALED.value:return detail(batch_id)
  summary=_summary(batch)
  if summary['reading_count']==0:raise ValueError('没有任何已接收读数，不能封存')
  if not summary['expected_complete']:
   raise ValueError('预计%d个片段，仅接收核对%d个，不能封存'%(summary['expected_fragments'],
    summary['accepted_fragments']+summary['duplicate_fragments']))
  if not summary['complete']:raise ValueError('仍有%d个缺层，补齐后才能封存'%summary['missing_count'])
  batch['status']=BatchStatus.SEALED.value;batch['sealed_at']=now();_store_batch(batch)
  return detail(batch_id)
def publish_batch(batch_id):
 with _SERIAL:
  batch=_load_batch(batch_id)
  if batch['status']==BatchStatus.PUBLISHED.value:return detail(batch_id)
  if batch['status']!=BatchStatus.SEALED.value:raise ValueError('须先封存且确认齐全，才能一次发布完整数据集')
  rows=[]
  for f in _fragments(batch_id):
   if f['status']==FragmentStatus.ACCEPTED.value:rows.extend(json.loads(f.get('payload_rows') or '[]'))
  rows.sort(key=lambda r:(r['borehole'],r['depth_m']))
  per_hole={}
  for r in rows:per_hole.setdefault(r['borehole'],[]).append(r['depth_m'])
  for hole,depths in per_hole.items():
   if len(depths)<3:raise ValueError('孔段%s不足3点，不能发布'%hole)
   for a,b in zip(depths,depths[1:]):
    if not math.isclose(b-a,DEPTH_STEP_M,rel_tol=0,abs_tol=1e-9):raise ValueError('孔段%s存在缺层或倒序，不能发布'%hole)
  ds_id=batch.get('dataset_id') or new_id('ds')
  repo.put('datasets',BoreholeDataset(ds_id,batch['name'],batch['source'],rows,now()))
  batch['status']=BatchStatus.PUBLISHED.value;batch['published_at']=now()
  batch['dataset_id']=ds_id;batch['boreholes']=sorted(per_hole);_store_batch(batch)
  return detail(batch_id)
