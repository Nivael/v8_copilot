import type {ETFQuarterlyReport,MarketRiskStatus} from './types'
import {formatShareCount as shares} from './numbers'
import {ETFName} from './ETFName'

function ReportSource({report,label}:{report:ETFQuarterlyReport;label:string}){
  if(report.availability!=='observed')return <small>{label}份额表尚未通过校验</small>
  const url=report.pdf_url?`${report.pdf_url}#page=${report.table_page}`:report.source_url
  return <>
    <small>{label}披露于 {report.publication_date}</small>
    <small><a href={url} target="_blank" rel="noreferrer">{label}{report.pdf_url?` · PDF第${report.table_page}页`:'原文'} ↗</a></small>
  </>
}

function MidyearDetails({report}:{report:ETFQuarterlyReport}){
  return <details><summary>上半年份额明细</summary>
    <p>期初 {shares(report.opening_shares)} 份；申购 {shares(report.subscription_shares)} 份；赎回 {shares(report.redemption_shares)} 份。申购－赎回 {shares(report.net_subscription_shares)} 份，仅属于上半年。</p>
    <p>拆分栏原值 {report.split_entry}；表内平衡差 {shares(report.accounting_residual_shares)} 份。拆分栏横线按原文保留，事件依据见公告核对。</p>
    <p>{report.audit_status==='report_states_unaudited'?'中报财务资料未经审计。':'中报审计状态尚未确认。'}本次取得于 {report.document_observed_at?new Date(report.document_observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'}（北京时间）。</p>
  </details>
}

export function ETFReportContinuity({data}:{data:NonNullable<MarketRiskStatus['etf_report_continuity']>}){
  return <section className="learning-freshness" aria-label="ETF中报与季报衔接">
    <header className="learning-section-head"><div><p className="eyebrow">报告期间 / 发布日期</p><h2>中报与三季报份额衔接</h2></div><span>总份额相等 {data.matched_etfs}/{data.declared_etfs}</span></header>
    <p>{data.note}</p>
    {data.period_start&&<p>中报期间 {data.period_start} 至 {data.period_end}；三季报期间 {data.following_period_start} 至 {data.following_period_end}。披露日另列于原文链接旁。</p>}
    <p>已核对中报份额表 {data.observed_midyear_reports}/{data.declared_etfs}；可比较 {data.compared_etfs} 只；总份额不一致 {data.mismatched_etfs} 只。</p>
    {data.reports.length===0?<p>{data.availability==='not_applicable'?'本项只比较相邻的中报与三季报；当前报告期不适用。':'匹配原文尚未通过校验，暂不比较。'}</p>:
      <div className="learning-table-wrap"><table className="learning-table market-continuity-table"><thead><tr>
        <th scope="col">ETF / 报告原文</th><th scope="col">中报期末总份额</th><th scope="col">三季报期初总份额</th><th scope="col">三季报期初－中报期末</th>
      </tr></thead><tbody>{data.reports.map(({code,midyear_report:mid,quarterly_report:quarter,comparison})=><tr key={code}>
        <th scope="row"><ETFName code={code}/><ReportSource report={mid} label="中报"/><ReportSource report={quarter} label="三季报"/></th>
        <td>{mid.availability==='observed'?<>{shares(mid.closing_shares)} 份<MidyearDetails report={mid}/></>:'中报缺失或校验未通过'}</td>
        <td>{quarter.availability==='observed'?<>{shares(quarter.opening_shares)} 份</>:'三季报缺失或校验未通过'}</td>
        <td>{comparison.availability!=='observed'?<span>缺少可比报告，未比较</span>:<>
          <span>{shares(comparison.total_difference_shares)} 份 · {comparison.total_relation==='equal'?'总份额相等':'不一致，待核对'}</span>
          {comparison.off_exchange_relation==='not_disclosed_in_both'?<small>场外份额未在两份报告同时明确列示，未按零补齐</small>:<small>明示场外份额差 {shares(comparison.off_exchange_difference_shares)} 份 · {comparison.off_exchange_relation==='equal'?'相等':'不一致，待核对'}</small>}
          {mid.off_exchange_closing_shares!=null&&<small>中报期末明确包含场外 {shares(mid.off_exchange_closing_shares)} 份</small>}
          {quarter.off_exchange_opening_shares!=null&&<small>三季报期初明确包含场外 {shares(quarter.off_exchange_opening_shares)} 份</small>}
        </>}</td>
      </tr>)}</tbody></table></div>}
  </section>
}
