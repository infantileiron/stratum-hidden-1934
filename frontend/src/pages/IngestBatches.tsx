import {useState} from 'react';
import * as api from '../api/ingestBatches';
import {useResource} from '../hooks/useResource';
import {refreshResources} from '../stores/resources';
import PageTitle from '../components/common/PageTitle';
import Notice from '../components/common/Notice';
import {fragmentStatusLabels,statusLabels} from '../constants/enums';
import {shortHash} from '../utils/format';
import type {IngestBatch,IngestFragment,User} from '../types/entities';

const canWrite=(user:User)=>user.role!=='viewer';

function MissingLayers({batch}:{batch:IngestBatch}){
 if(batch.missing_count===0)return <small className="ok-line">无缺层，孔段深度连续1米</small>;
 return <div className="missing-box"><b>缺层 {batch.missing_count} 点</b>
  {Object.entries(batch.missing).map(([hole,depths])=><small key={hole}>{hole}：缺 {depths.join('、')}{batch.missing_truncated?' …（仅显示前60点）':''}</small>)}
  <small>缺层期间可继续补片，但不能封存，也不能建立研究</small></div>;
}

function FragmentLedger({fragments}:{fragments:IngestFragment[]}){
 return <div className="table-scroll"><table><thead><tr><th>片段号</th><th>核对结果</th><th>孔段 / 深度</th><th>新增 / 重复行</th><th>校验与原因</th><th>接收时间</th></tr></thead>
 <tbody>{fragments.map(f=><tr key={f.id}><td>#{f.fragment_no}</td>
  <td><span className={'badge '+f.status}>{fragmentStatusLabels[f.status]||f.status}</span></td>
  <td>{f.boreholes.join(' / ')||'—'}<small>{f.depth_min==null?'—':`${f.depth_min}—${f.depth_max}m`}</small></td>
  <td>{f.accepted_rows} / {f.duplicate_rows}</td>
  <td className="reason-cell"><small>SHA256 {shortHash(f.checksum)}{f.reason?`　${f.reason}`:''}</small></td>
  <td><small>{f.received_at.replace('T',' ').slice(0,19)}</small></td></tr>)}</tbody></table></div>;
}

function BatchCard({batch,user,onMessage}:{batch:IngestBatch;user:User;onMessage:(m:string,e?:boolean)=>void}){
 const [open,setOpen]=useState(false);
 const [detail,setDetail]=useState<IngestBatch|null>(null);
 const [no,setNo]=useState('');const [source,setSource]=useState('');const [text,setText]=useState('');
 const loadDetail=()=>api.detail(batch.id).then(setDetail).catch(e=>onMessage(e.message,true));
 const toggle=()=>{const next=!open;setOpen(next);if(next)loadDetail();};
 const submit=async(e:React.FormEvent)=>{
  e.preventDefault();
  try{await api.sendFragment(batch.id,{fragment_no:no?Number(no):null,csv_text:text});
   setNo('');setText('');setSource('');onMessage('片段已核对接收');refreshResources();loadDetail();}
  catch(err:any){onMessage(err.message,true);refreshResources();loadDetail();}
 };
 const cur=open&&detail?detail:batch;
 return <article className={'paper batch-card '+batch.status}>
  <header className="record">
   <div><b>{batch.name}</b><small>{batch.source}　<span className={'badge '+batch.status}>{statusLabels[batch.status]||batch.status}</span></small></div>
   <div className="actions">
    {canWrite(user)&&batch.status==='receiving'&&<button onClick={async()=>{try{await api.seal(batch.id);refreshResources();onMessage('封存成功：读数已冻结')}catch(e:any){onMessage(e.message,true)}}}>封存冻结 ↗</button>}
    {canWrite(user)&&batch.status==='sealed'&&<button className="primary" onClick={async()=>{try{await api.publish(batch.id);refreshResources();onMessage('完整数据集已一次发布')}catch(e:any){onMessage(e.message,true)}}}>发布完整数据集 ↗</button>}
    <button onClick={toggle}>{open?'收起台账':'核对台账 ↗'}</button>
   </div>
  </header>
  <div className="batch-stats">
   <div><strong>{batch.reading_count}</strong><span>组装读数</span></div>
   <div><strong>{batch.accepted_fragments}</strong><span>接收片段</span></div>
   <div><strong>{batch.duplicate_fragments}</strong><span>重复不计数</span></div>
   <div><strong className={batch.rejected_fragments?'warn-text':''}>{batch.rejected_fragments}</strong><span>整片拒收</span></div>
   <div><strong className={batch.missing_count?'warn-text':''}>{batch.missing_count}</strong><span>缺层点数</span></div>
   <div><strong>{batch.borehole_count}</strong><span>孔段数</span></div>
  </div>
  <MissingLayers batch={batch}/>
  {batch.status==='receiving'&&batch.expected_fragments>0&&<small>预计片段 {batch.expected_fragments}，已核对 {batch.accepted_fragments+batch.duplicate_fragments}；齐全且无缺层才能封存</small>}
  {batch.published&&<small className="ok-line">已发布数据集 {batch.dataset_id}，迟到片段拒收，数据集与研究快照不再变化</small>}
  {open&&cur.fragments&&<div className="ledger"><FragmentLedger fragments={cur.fragments}/></div>}
  {open&&canWrite(user)&&batch.status==='receiving'&&<form className="paper form-grid fragment-form" onSubmit={submit}>
   <label>片段编号（同号重传做同文/异文核对，留空自动编号）<input aria-label="片段编号" type="number" min={1} value={no} onChange={e=>setNo(e.target.value)} placeholder="例如 3"/></label>
   <label>碎片CSV文件<input aria-label="碎片CSV文件" type="file" accept=".csv" onChange={async e=>{const f=e.target.files?.[0];if(f){if(f.size>400000){onMessage('CSV不能超过400KB',true);return}setSource(f.name);setText(await f.text())}}}/></label>
   <label className="wide">碎片内容（可乱序、可重传）<textarea aria-label="碎片内容" value={text} onChange={e=>setText(e.target.value)} placeholder="borehole,depth_m,value,truth"/></label>
   {source&&<small>已载入 {source}</small>}
   <button className="primary">核对并接收片段</button>
  </form>}
  {open&&batch.status!=='receiving'&&<small className="ok-line">{batch.status==='sealed'?'批次已封存：迟到片段将被拒收，可执行一次发布':'批次已发布：封存结果与读数永久冻结'}</small>}
 </article>;
}

export default function IngestBatches({user}:{user:User}){
 const {data,error}=useResource(api.list,[] as IngestBatch[]);
 const [name,setName]=useState('野外采集批次 · 碎片回传'),[source,setSource]=useState('field_fragment_202611.csv'),[expected,setExpected]=useState(0),[message,setMessage]=useState(''),[fatal,setFatal]=useState('');
 const notify=(m:string,isError=false)=>{setFatal(isError?m:'');setMessage(isError?'':m);};
 return <><PageTitle chapter="02 / FRAGMENT INTAKE" title="碎片陆续回传，组装同一采集批次" description="同一批次按片段分批接收，乱序自动组装；重复片段不增加读数，同号异文与重叠深度异值整片拒收。缺层可继续补片但不能封存、不能建研究；齐全封存后一次发布完整数据集，封存/发布后迟到片段拒收，已发布数据与研究快照不变。"/>
  <Notice error={error||fatal||message}/>
  {canWrite(user)&&<form className="paper form-grid" onSubmit={async e=>{e.preventDefault();try{await api.create({name,source,expected_fragments:expected});setMessage('采集批次已建立，可开始回传片段');setFatal('');refreshResources()}catch(e:any){notify(e.message,true)}}}>
   <label>采集批次名称<input aria-label="采集批次名称" value={name} onChange={e=>setName(e.target.value)}/></label>
   <label>野外来源文件<input aria-label="野外来源文件" value={source} onChange={e=>setSource(e.target.value)}/></label>
   <label>预计片段数（0表示不预设，仅用于齐全核对）<input aria-label="预计片段数" type="number" min={0} max={200} value={expected} onChange={e=>setExpected(Number(e.target.value))}/></label>
   <button className="primary">建立采集批次</button>
  </form>}
  {data.length===0?<div className="paper empty">暂无采集批次，建立后即可按片段回传野外测井。</div>:data.map(b=><BatchCard key={b.id} batch={b} user={user} onMessage={notify}/>)}
 </>;
}
