import {useState,type ReactNode} from 'react'
import type {EvidenceInventory} from './stRegimeTypes'
function isSinaMirror(url:string|null){
 try{return url!==null&&new URL(url).hostname==='file.finance.sina.com.cn'}catch{return false}
}
export function STEvidenceInventory({data,leading}:{data?:EvidenceInventory|null;leading?:ReactNode}){
 const [query,setQuery]=useState('')
 const [page,setPage]=useState(0)
 if(!data)return null
 const matches=data.documents.filter(d=>`${d.announcement_id} ${d.symbols.join(' ')} ${d.title}`.includes(query.trim()))
 const rows=matches.slice(page*25,(page+1)*25)
 return <section id="st-evidence-inventory" aria-label="研究材料覆盖与缺口" style={{scrollMarginTop:80}}>
  <h2>{data.title}</h2>{leading}<p>统计范围固定于本次核账基准输入；后续专题不会自动累计进这张清单，新增材料需另行核账。</p><p>{data.answer.replace('当前正式快照','核账基准快照')}</p><p>{data.scope.replace('当前正式快照','核账基准快照')}</p>
  <table className="regime-table"><caption>保存范围，不是已读或已验证事实数量</caption><thead><tr><th>当前输入中的材料</th><th>去重数量</th><th>含义</th></tr></thead><tbody><tr><th>保留提取文本</th><td>{data.counts.with_retained_extracted_text}</td><td>可能是摘录或部分页，不能视为全文已读</td></tr><tr><th>仅元数据或引用</th><td>{data.counts.metadata_or_reference_only}</td><td>此处未保留正文，不表示硬盘其他位置没有原件</td></tr><tr><th>合计文件身份</th><td>{data.counts.unique_id_sha_pairs}</td><td>公告ID＋文件摘要去重，不累计重复引用</td></tr></tbody></table>
  <h3>现在最需要补什么？</h3>{data.current_limits.map(l=><article key={l.topic}><h4>{l.topic}</h4><p>{l.status} <a href={'#'+l.anchor}>查看具体问题 →</a></p></article>)}
  <details><summary>查找逐文件清单</summary><label>按代码、公告ID或标题查找 <input value={query} onChange={e=>{setQuery(e.target.value);setPage(0)}}/></label><p>匹配{matches.length}份，每页最多25份。</p><table className="regime-table"><caption>文件身份与保存范围</caption><thead><tr><th>代码与公告</th><th>材料状态</th><th>非空页位置</th></tr></thead><tbody>{rows.map(d=><tr key={d.announcement_id+d.sha256}><th>{d.symbols.join('、')} · {d.announcement_id}<br/>{d.url?<a href={d.url} target="_blank" rel="noreferrer">{d.title}</a>:d.title}{isSinaMirror(d.url)&&<p>新浪镜像保存件；官方原件字节待补核。</p>}<details><summary>核对文件身份</summary><p>公告标识：{d.announcement_id}</p><p style={{overflowWrap:'anywhere'}}>保存文件摘要（SHA-256）：{d.sha256}</p><p>摘要用于区分保存文件，不单独证明来源官方、正文完整或已经人工核读。</p></details></th><td>{d.has_retained_extracted_text?'含提取文本':'仅元数据／引用'}</td><td>{d.retained_nonempty_page_positions}（非已读页数）</td></tr>)}</tbody></table><button disabled={page===0} onClick={()=>setPage(page-1)}>上一页</button><span> 第{page+1}页 </span><button disabled={(page+1)*25>=matches.length} onClick={()=>setPage(page+1)}>下一页</button></details>
  <details><summary>怎样去重，发现了什么，哪些不能据此认证？</summary><p>{data.what_changed}</p><ul>{data.boundaries.map(b=><li key={b}>{b}</li>)}</ul></details><p>{data.next}</p>
 </section>
}
