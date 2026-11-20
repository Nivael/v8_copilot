import terms from './lingnanJudgmentTerms.json'
const yuan=(s:string)=>Number(s).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})+'元'
export function STLingnanJudgmentTerms(){
 const a=terms.award,r=terms.request,s=terms.source
 return <section aria-label="岭南一审判项金额补核">
  <h4>判项金额已补核，仍不是已兑付金额</h4>
  <p>公司2026-124号公告转述的一审判项列示：债券本息<strong>{yuan(a.bond_principal_and_interest)}</strong>，约3.77亿元；资金占用利息另算。付款条件是<strong>{a.payment_trigger}</strong>，不是从公告日直接数七日。</p>
  <div className="regime-scroll"><table className="regime-table" aria-label="岭南判项金额构成"><thead><tr><th scope="col">判项列示金额</th><th scope="col">金额</th><th scope="col">怎样读</th></tr></thead><tbody>
   <tr><th scope="row">债券本息</th><td>{yuan(a.bond_principal_and_interest)}</td><td>上市公司支付；不是只有本金，也不是已付款回执。</td></tr>
   <tr><th scope="row">律师费</th><td>{yuan(a.lawyer_fee)}</td><td rowSpan={2}>四被告共同支付；不能按四家各加一遍。</td></tr>
   <tr><th scope="row">保全担保保险费</th><td>{yuan(a.insurance_fee)}</td></tr>
   <tr><th scope="row">以上三项小计</th><td>{yuan(a.three_item_subtotal)}</td><td>不包含另算的资金占用利息及未列入本表的其他费用。</td></tr>
  </tbody></table></div>
  <p>三项小计按万元保留两位为{a.header_wan}万元，与公告标题涉案金额相符；不能再把标题金额当第四笔相加。这不是截至今日的全部应付额或实付额。</p>
  <details><summary>原告诉请与判项，哪里不同？</summary>
   <p>原诉请债券本金{yuan(r.principal)}＋利息{yuan(r.bond_interest)}＝{yuan(r.subtotal)}；判项债券本息比这项诉请少{yuan(a.difference_from_requested_bond_subtotal)}。本轮未核差额形成原因，不反推已经偿还或现金到账。</p>
   <p>占用利息也不能照搬诉请算法：诉请按6%/年、首段从2024年8月15日开始；公告转述判项改用一年期LPR、首段从8月22日开始，且分段基数不同。</p>
   <table className="regime-table" aria-label="判项资金占用利息分段"><thead><tr><th scope="col">起止期间</th><th scope="col">计息基数</th></tr></thead><tbody>{a.interest_segments.map(x=><tr key={x.start}><th scope="row">{x.start} → {x.through}</th><td>{yuan(x.base)}</td></tr>)}</tbody></table>
   <p>这里没有补造实际清偿日或适用利率的计算口径，因此不计算截至今日的占用利息总额。</p><a href={s.url+'#page=1'} target="_blank" rel="noreferrer">诉请第1—2页 ↗</a> · <a href={s.url+'#page=2'} target="_blank" rel="noreferrer">判项第2—4页 ↗</a>
  </details>
  <details><summary>优先受偿权与资产价值，怎样分开？</summary>
   <p>一审判项载明对相应质押股权及应收账款的优先受偿权，仍须结合判决生效与实际处分。股权出资额不当可卖价格，也不与同一底层应收账款重复加总。</p>
   <table className="regime-table" aria-label="判项应收账款金额上限"><thead><tr><th scope="col">出质方</th><th scope="col">判项载明上限</th></tr></thead><tbody>{terms.receivable_limits.map(x=><tr key={x.pledgor}><th scope="row">{x.pledgor}</th><td>{yuan(x.cap)}</td></tr>)}</tbody></table>
   <p>上限不是已收回金额，也不是已核定可变现价格；本轮不据此确定所有其他权利人的最终顺位。</p><a href={s.url+'#page=3'} target="_blank" rel="noreferrer">股权及应收账款判项第3—4页 ↗</a>
  </details>
  <details><summary>这次补到的是什么原件？</summary><p>公司《{s.title}》，公告编号{s.notice_number}，披露{s.announcement_date}；案号{terms.case_ref}与受托报告相同。4页均已看图并核金额，但这是公司对判决的披露，不是法院出具的判决书原始文件。</p><p>公告第4页明确一审尚未生效，15日上诉期从判决送达起算。各方送达日及后续上诉、生效、执行或兑付原件未核，不能从10月28日公告日推算已经生效或已经逾期。</p><a href={s.url+'#page=4'} target="_blank" rel="noreferrer">状态及公告日期第4页 ↗</a><p>保存SHA256：<code>{s.sha256}</code></p><p><a href="/runs#research-RUN-A621C45FC204409DB7B7EFF1">查看本轮研究与计算记录 →</a></p></details>
 </section>
}
