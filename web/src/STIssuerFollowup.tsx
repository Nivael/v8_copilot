import type {RegimeIssuerFollowup} from './stRegimeTypes'
const wan=(s:string)=>(Number(s)/10000).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
export function STIssuerFollowup({followup:f}:{followup:RegimeIssuerFollowup}){
 return <section aria-label="华鹏财报与新冻结更新">
  <p>截至{f.as_of}已核资料：上半年与前三季经营现金流均为正，归母亏损和负净资产也同时存在。财报未经审计；半年、前三季是不同累计期间，净资产是各期末存量。</p>
  <details><summary>看两期财报、单季核对与新冻结原件</summary>
   <p>下表单位万元，显示至两位小数；精确元值与报告页码保留在原件。流量按各自报告期，不能将半年与前三季直接作同比。</p>
   <div className="regime-scroll"><table className="regime-table"><thead><tr><th>指标</th>{f.reports.map(r=><th key={r.period_end}>{r.label}<small>公开{r.published_on}</small></th>)}</tr></thead><tbody>
    <tr><th>营业收入 · 累计</th>{f.reports.map(r=><td key={r.period_end}>{wan(r.revenue)}<small>较上年同期{Number(r.revenue_yoy_pct)>0?'+':''}{r.revenue_yoy_pct}%</small></td>)}</tr>
    <tr><th>归母净利润 · 累计</th>{f.reports.map(r=><td key={r.period_end}>{wan(r.parent_profit)}</td>)}</tr>
    <tr><th>经营现金流净额 · 累计</th>{f.reports.map(r=><td key={r.period_end}>{wan(r.operating_cash)}</td>)}</tr>
    <tr><th>归母净资产 · 各期末</th>{f.reports.map(r=><td key={r.period_end}>{wan(r.parent_equity)}</td>)}</tr>
   </tbody></table></div>
   <p>9月末现金及现金等价物余额{wan(f.cash_rollforward.closing_yuan)}万元，较期初净减少{wan(String(Math.abs(Number(f.cash_rollforward.net_change_yuan))))}万元。经营净流入不等于期末现金余额增加；该余额不是全部货币资金或自由可用资金。</p><p>单独看7—9月：收入{wan(f.quarter_revenue_yuan)}万元，归母净利润{wan(f.quarter_parent_profit_yuan)}万元，仍为亏损。{f.quarter_difference_basis}</p>
   <p>{f.new_freeze.published_on}新冻结为{f.new_freeze.entity}{f.new_freeze.account_count}个账户，冻结资金{wan(f.new_freeze.frozen_yuan)}万元；申请保全额度{wan(f.new_freeze.applied_preservation_yuan)}万元。两者不混为一项，也不等于已确认损失。</p>
   <p>公司当时称：{f.new_freeze.issuer_impact_statement}这是发行人表述，不是资金风险已解除的独立证明。新冻结与7月石岛玻璃部分解冻分属不同主体，不相抵。</p>
   <p>冻结原件报告占最近一期经审计净资产{f.new_freeze.reported_net_assets_pct}%，原比例保留；已核上年末归母净资产为负，不能把该比例读成安全垫充足，也不自行改写其会计口径。</p>
   {f.facts.map((x,n)=><div key={`${x.source.announcement_id}-${n}`}><p>{x.published_on}公开（落款{x.document_dated_on}）：{x.text}</p><a href={x.source.url} target="_blank" rel="noreferrer">{x.source.title} · 第{x.source.page}页 ↗</a></div>)}
   <p><strong>什么证据会推翻或修正：</strong>{f.what_would_change}</p><p className="reading-caption">{f.boundary}</p>
  </details>
 </section>
}
