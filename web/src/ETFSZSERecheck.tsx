import type {SZSERevisionRecheck} from './types'
import {formatShareCount as exact} from './numbers'

const time=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})

export function ETFSZSERecheck({data}:{data:SZSERevisionRecheck}){
  return <section className="learning-freshness" aria-label="深市ETF份额重读核对">
    <header className="learning-section-head"><div><p className="eyebrow">重读记录 / 最终修订证据</p><h2>深市份额的次日复核</h2></div><span>最终修订版仍待确认</span></header>
    <p>{data.note}</p>
    {data.availability!=='observed'?<p>{data.availability==='baseline_changed'?'原份额快照已更新，旧复核已失配，需按新快照重读。':'尚无与当前份额快照匹配且通过校验的完整重读记录。'}</p>:<>
      <p>本次重读 {data.share_observations} 条份额，较所绑定原快照变化 {data.share_changes} 条；{data.start} 至 {data.through}，每只 {data.sessions} 个交易日。原份额快照保留，下表只展示本次复核差异。</p>
      <p>实际取得 {data.first_observed_at&&time(data.first_observed_at)} 至 {data.last_observed_at&&time(data.last_observed_at)}（北京时间）；实际请求为深交所官方 {data.transport} 接口。净值仅返回 {data.nav_observations} 条，不能当作覆盖同一完整窗。</p>
      <details className="market-source-notes"><summary>查看三只ETF的复核差异与来源</summary>
        <p className="learning-footnote market-recheck-scroll-hint">左右滑动表格可查看份额与净值比较。</p>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的深市ETF复核表" tabIndex={0}><table className="learning-table market-recheck-table"><thead><tr><th scope="col">ETF / 目标日份额</th><th scope="col">份额与原快照比较</th><th scope="col">实际净值范围 / 比较</th></tr></thead><tbody>{data.funds.map(fund=><tr key={fund.code}>
          <th scope="row">{fund.code}<small>{exact(fund.latest_shares_ten_thousand)} 万份</small><small>目标日 {data.through}</small></th>
          <td>{fund.share_observations} 条重读，变化 {fund.share_comparison.changed_observations} 条{fund.share_comparison.changes.map(change=><small key={change.date}>{change.date}：{exact(change.before)} → {exact(change.after)} 万份</small>)}<small>无变化也不等于最终修订已认证</small></td>
          <td>{fund.nav_observations} 条，截至 {fund.nav_through}<small>与原快照重叠 {fund.nav_comparison.overlap_observations} 条，变化 {fund.nav_comparison.changed_observations} 条</small>
            <small>本次新增日期 {fund.nav_comparison.new_dates.length} 个，原有日期未返回 {fund.nav_comparison.missing_previous_dates.length} 个</small>
            <small>{fund.issuer_nav_comparison.overlap_observations>0?`与基金公司重叠 ${fund.issuer_nav_comparison.overlap_observations} 条，不一致 ${fund.issuer_nav_comparison.changed_observations} 条`:'基金公司净值未取得匹配日期，尚未交叉核对'}</small>
            {fund.nav_comparison.changes.map(change=><small key={change.date}>原净值差异 {change.date}：{change.before} → {change.after} 元</small>)}
            {fund.issuer_nav_comparison.changes.map(change=><small key={change.date}>基金公司净值差异 {change.date}：基金公司 {change.before} / 深交所 {change.after} 元</small>)}
          </td>
        </tr>)}</tbody></table></div>
        <details className="learning-manifest"><summary>实际查询与归档绑定</summary><p>原快照取得 {data.baseline_fetched_at&&time(data.baseline_fetched_at)}（北京时间）；响应逐页归档并核对摘要、代码、单位、查询窗和分页。首次取得时间不回填成历史当时可见。</p><p>原快照摘要 <code>{data.baseline_digest}</code></p>{data.responses?.map(ref=><p key={`${ref.code}-${ref.kind}-${ref.page}`}><a href={ref.url} target="_blank" rel="noreferrer">{ref.code} · {ref.kind==='NAV'?'净值':'份额'} · 查询第{ref.page}页 ↗</a><small>取得 {time(ref.observed_at)}（北京时间）</small></p>)}</details>
      </details>
    </>}
  </section>
}
