import update from './catalogNov20Fixed.json'
import full from './catalogFullCoverage.json'
import type {STRegimeData} from './stRegimeTypes'
export function STNov20CatalogUpdate({data}:{data:STRegimeData}){
 const bound=data.content_digest===update.baseline_snapshot_digest&&full.evidence_sha256===update.full_catalog_evidence_sha256&&update.body_phases.every(p=>p.catalog_review_sha256===update.catalog_review_sha256)
 if(!bound)return <p role="status">20日公告补核与当前来源未对应，暂不显示更新。</p>
 return <aside aria-label="11月20日固定样本公告更新">
  <h4>最新补核：获批、回款和交易完成，要分开看</h4>
  <p>11月20日单日目录已补到固定历史150家公司：20家公司有41份附件候选，其中{update.reviewed_count}份已核正文，{update.remaining_count}份待筛审。固定历史样本不等于当日法律ST名单；这些附件也不是41个独立案例。</p>
  {update.findings.map(f=><article key={f.announcement_id}>
   <h5>{f.code} · {f.label}</h5>
   <p><strong>{f.answer}</strong></p><p>{f.boundary}</p>
   <details><summary>查看公告依据 · {f.announcement_id}</summary>
    <p>{f.source.title}。已提取全文，关键图像核看物理第{f.source.visual_physical_pages.join('、')}页；非全部页面逐页看图。</p>
    {f.pages.map(page=><p key={page}><a href={`${f.source.url}#page=${page}`} target="_blank" rel="noreferrer">原件第{page}页 ↗</a></p>)}
    <p>保存摘要：<code style={{overflowWrap:'anywhere'}}>{f.source.sha256}</code>。</p>
   </details>
  </article>)}
  <details><summary>单日查询范围与其余候选</summary>
   <p>150家查询均完成来源重放；先用已知11月12日公告作正向控制，再复用四家先行查询，仅新增146家。空返回未声明数据日，不能证明当天没有公告。原7—11月期间记录保持，未直接相加成统一窗口总数。</p>
   <p>{update.reviewed_count}份正文共{update.text_pages}页、{update.visual_pages}个关键图像页已核。未独立取得法院或交易所决定原件，未核生效后交易及实收，也未据公告推定当日涨跌原因。</p>
   <ul>{update.titles.map(t=><li key={t.announcement_id}><a href={'https://static.cninfo.com.cn/'+t.adjunct_url} target="_blank" rel="noreferrer">{t.codes.join('、')} · {t.title}</a> — {update.findings.some(f=>f.announcement_id===t.announcement_id)?'本轮正文已核，执行边界见上':'标题候选，正文待核'}</li>)}</ul>
   <p>目录证据摘要：<code style={{overflowWrap:'anywhere'}}>{update.catalog_evidence_sha256}</code>；正文补核摘要：<code style={{overflowWrap:'anywhere'}}>{update.body_phases.map(p=>p.sha256).join('；')}</code>。</p>
  </details>
 </aside>
}
