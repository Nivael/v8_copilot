import type {RegimeJueweiAdjustment} from './stRegimeTypes'
const pct=(n:number)=>(n>0?'+':'')+n.toFixed(2)+'%'
export function STJueweiAdjustment({data:d,oldCount,newCount}:{data:RegimeJueweiAdjustment|null|undefined;oldCount?:number;newCount:number}){
 if(!d)return null
 const a=d.action,c=d.calculation
 return <section aria-label="绝味分红与复权构造更新">
  <p><strong>绝味的报价差异，判断更新了什么？</strong>{d.answer}{d.comparison_reconstruction_supported&&oldCount!=null&&<>5日配对由旧严格匹配组{oldCount}只更新为同口径{newCount}只；绝味20/40日仍未满，不新增观察窗口。</>}</p>
  <details><summary>为什么除息日原价下跌，复权读数却上涨？</summary>
   <p>{a.published_on}公告安排每股有权现金红利{a.eligible_cash_per_share}元（含税），登记日{a.record_date}、除息及安排的发放日{a.ex_date}。不把发放安排当作个人到账记录。</p>
   <p>实际前一成交日{c.previous_session}收盘{c.previous_raw_close}元，除息日收盘{c.ex_raw_close}元，裸收盘变化{pct(c.raw_price_change_pct)}；除息参考价{c.reference_cent}元，相对参考价变化{pct(c.reference_change_pct)}。两个方向可以同时成立，分红不能被漏掉，也不能把价格比值直接当作个人实际持有收益。</p>
   <div className="regime-scroll"><table className="regime-table"><thead><tr><th>价格构造</th><th>除息前的处理</th><th>摘帽前5日</th><th>摘帽后5日</th></tr></thead><tbody><tr><th>面板沿用的因子法</th><td>按比例缩放；使用缓存因子和本次参考价核验</td><td>{pct(d.five_day_examples.before.factor_pct)}</td><td>{pct(d.five_day_examples.after.factor_pct)}</td></tr><tr><th>冻结腾讯前复权</th><td>本序列符合原价减0.25元</td><td>{pct(d.five_day_examples.before.additive_pct)}</td><td>{pct(d.five_day_examples.after.additive_pct)}</td></tr><tr><th>腾讯原始价按同一因子法重建</th><td>{d.comparison_reconstruction_supported?d.reconstructed_dates+'个成交日回算与面板原值相符':'回算条件未全部通过，暂不认证'}</td><td>{pct(d.five_day_examples.before.normalized_pct)}</td><td>{pct(d.five_day_examples.after.normalized_pct)}</td></tr></tbody></table></div>
   <p>即使两个日期都在除息前，事后减同一现金数也会改变价格比值；按同一比例缩放则保持该段比值。这里解释的是冻结序列的数值关系，未取得腾讯通用算法规范，不外推所有股票。</p>
   <p>本次因子由{c.factor_before}变为{c.factor_on}；以除息前因子×前收盘÷分币参考价计算为{Number(c.formula_factor_before_rounding).toFixed(8)}，四位小数为{c.formula_factor_rounded}，与缓存一致。没有把两个直接前复权产品改写为相同数字。</p>
   <details><summary>分红总额、摊薄精度与原件页码</summary>
    <p>总股本{Number(a.total_shares).toLocaleString('zh-CN')}股，扣除回购专户{Number(a.repurchase_shares).toLocaleString('zh-CN')}股，实际参与{Number(a.eligible_shares).toLocaleString('zh-CN')}股。总分红由{Number(a.prior_scheduled_total_yuan).toLocaleString('zh-CN')}元调为{Number(a.scheduled_total_yuan).toLocaleString('zh-CN')}元，有权每股0.25元不变。</p>
    <p>按全部股本摊薄的参考现金约{Number(c.virtual_cash_per_total_share).toFixed(6)}元，公告按分币展示为0.25元；这不是有权持有人少收。律师意见使用{d.opinion_example.date}的{d.opinion_example.raw_close}元作示例，两种参考价按分币都为{d.opinion_example.reported_reference}元，故按展示值报告影响0%。未舍入算式的相对差约{Number(c.opinion_unrounded_reference_effect_pct).toFixed(4)}%，两种精度分别保留；示例日不当实际除息前一日。</p>
    {d.facts.map((f,n)=><p key={f.source.sha256+'-'+n}>{f.text} <a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title} · 物理第{f.source.page}页 ↗</a></p>)}
   </details>
   <p className="reading-caption">{d.boundary}</p>
  </details>
 </section>
}
