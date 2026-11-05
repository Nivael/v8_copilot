import type {MarketRiskStatus} from './types'
import {formatShareCount as shares} from './numbers'
import {useState} from 'react'

type Review=NonNullable<MarketRiskStatus['etf_share_events']>
const roles:Record<string,string>={plan:'计划',reminder:'提示',result:'结果',cancellation:'取消',unit_notice:'单位调整'}
const kinds:Record<string,string>={merge:'份额合并',split:'份额拆分',conversion:'份额折算',creation_unit:'最小申赎单位调整'}
const scopes:Record<string,string>={exchange:'场内',off_exchange:'场外',fund_total:'基金总额'}
const rounding:Record<string,string>={ceil_to_whole_share:'逐户小数份额上进位',floor_to_whole_share:'逐户截去小数部分',nearest_whole_share:'份额四舍五入到整数位',not_stated:'结果公告未重述逐户舍入方式'}

export function ETFShareEventReview({data}:{data:Review}){
  const [selectedCode,setSelectedCode]=useState('all')
  const codes=[...new Set(data.events.map(event=>event.code))].sort()
  const shownEvents=data.events.filter(event=>selectedCode==='all'||event.code===selectedCode)
    .slice().sort((first,second)=>second.event_date.localeCompare(first.event_date))
  return <section className="learning-freshness" aria-label="已核对ETF公告事项">
    <header className="learning-section-head">
      <div><p className="eyebrow">公告逐条核对 / 历史事项</p><h2>计划、取消与实施结果</h2></div>
      <span>局部核对 · {data.reviewed_events}条事项</span>
    </header>
    <p>{data.note}</p>
    {data.events.length===0?<p>本批事项尚未通过当前原文、日期和关系核对；公告目录与文本提取仍单独列出。</p>:<>
      <p>已核对 {new Set(data.events.map(event=>event.code)).size} 只ETF的 {data.reviewed_events} 条历史事项，涉及 {data.reconciled_documents}/{data.selected_documents??'—'} 份筛选材料；其余 {data.pending_documents??'—'} 份尚未完成这类核对。多份提示公告合为同一事项，不重复计作折算。</p>
      <div className="learning-filters"><label>ETF事项 <select aria-label="ETF事项筛选" value={selectedCode} onChange={event=>setSelectedCode(event.target.value)}>
        <option value="all">全部ETF</option>{codes.map(code=><option key={code} value={code}>{code}</option>)}
        {selectedCode!=='all'&&!codes.includes(selectedCode)&&<option value={selectedCode} disabled>{selectedCode}（当前未取得）</option>}
      </select></label><span>当前显示 {shownEvents.length}/{data.events.length} 条 · 按事项日期从近到远</span></div>
      {shownEvents.length===0&&<p>该ETF当前没有通过原文核对的事项；可切回全部ETF查看其余结果。</p>}
      <div className="learning-table-wrap"><table className="learning-table market-event-table">
        <thead><tr><th scope="col">ETF / 事项与原文</th><th scope="col">结果与实际日期</th><th scope="col">比例或每笔单位</th><th scope="col">登记结果与口径</th></tr></thead>
        <tbody>{shownEvents.map(event=><tr key={event.event_id}>
          <th scope="row">{event.code}<small>{kinds[event.kind]||'事项未分类'}</small>
            {event.source_scope==='result_only'&&<small>本条仅核对结果原文</small>}
            <details><summary>原文链（{event.documents.length}份）</summary>
              <ul className="market-announcement-docs">{event.documents.map(doc=><li key={doc.document_id}>
                <span>{roles[doc.role]||'来源'} · {doc.published_on}</span>
                {doc.role==='reminder'&&doc.published_on>event.event_date&&<small>生效日后的提示，不回填为事前已知</small>}
                <small>{doc.title}</small>
                {doc.observed_at&&<small>本次取得 {new Date(doc.observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）</small>}
                {(doc.role==='plan'||doc.role==='reminder')&&doc.announced_ratio!==undefined&&<small>{doc.announced_ratio==null?'本公告未给定确定比例':`本公告给定比例 ${doc.announced_ratio}`}</small>}
                {doc.format==='issuer_html'?<small><a href={doc.url} target="_blank" rel="noreferrer">发行人正文 ↗</a></small>:doc.pages.map(page=><small key={page}><a href={`${doc.url}#page=${page}`} target="_blank" rel="noreferrer">{roles[doc.role]||'原文'} · PDF第{page}页 ↗</a></small>)}
              </li>)}</ul>
            </details>
          </th>
          <td>{event.resolution==='cancelled'?'拆分已取消':event.resolution==='implemented'?'实施结果已披露':'单位调整公告'}
            <small>{event.resolution==='cancelled'?'原计划日期':event.kind==='creation_unit'?'公告生效日':`${kinds[event.kind]||'份额事项'}日`} {event.event_date}</small>
            {event.record_date&&<small>权益登记日 {event.record_date}</small>}
            {event.registration_date&&<small>变更登记日 {event.registration_date}</small>}
            {event.ex_right_date&&<small>除权日 {event.ex_right_date}</small>}
            <small>{event.resolution==='cancelled'?'取消公告披露':event.kind==='creation_unit'?'调整公告披露':'结果公告披露'} {event.resolution_published_on}</small>
            <small>{event.within_catalog_window?'位于目录筛选观察窗内':'位于本次观察窗外'}</small>
          </td>
          <td>{event.kind==='creation_unit'?
            <>{shares(event.unit_before_shares||'—')} → {shares(event.unit_after_shares||'—')} 份<small>每笔最小申赎单位</small></>:
            <>{event.effective_ratio||'无有效折算比例'}{event.resolution==='cancelled'?<small>原计划比例 {event.planned_ratio}，未生效</small>:<small>每1份原份额对应的新份额</small>}</>}
          </td>
          <td>{event.reported_totals?.length?<>
            <span>{rounding[event.holder_rounding||'not_stated']||'舍入方式尚未核对'}；简单比例不能精确反推登记总额。</span>
            {event.plan_holder_rounding?.length&&event.holder_rounding==='not_stated'?<small>计划公告载明：{event.plan_holder_rounding.map(rule=>rounding[rule]||'尚未核对').join('、')}。与结果公告分开记录。</small>:null}
            <details><summary>登记总额与比例乘积</summary>{event.reported_totals?.map(total=><div key={total.scope}>
              <p>{scopes[total.scope]||'范围待核对'}：变更前 {shares(total.before_shares)} 份，登记后 {shares(total.after_shares)} 份。</p>
              <p>登记后－原总额×比例：{shares(total.after_minus_simple_ratio_shares)} 份。该差额不计作净申赎。</p>
            </div>)}</details>
          </>:event.kind==='creation_unit'?<span>每笔单位改变，不将其倍数用于基金总份额。</span>:<span>仅拆分计划被取消；同一公告的申赎单位调整另行处理，不作有效拆分。</span>}</td>
        </tr>)}</tbody>
      </table></div>
    </>}
    <p>本表没有证明整个观察窗无其他份额事件。净申赎金额继续未发布，历史事项不自动用于当前曲线校正。</p>
  </section>
}
