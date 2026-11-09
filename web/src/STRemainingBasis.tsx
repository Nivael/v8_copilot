import {useState} from 'react'
import type {RegimeRemainingBasis} from './stRegimeTypes'
const pct=(n:number)=>(n>0?'+':'')+n.toFixed(2)+'%'
function Source({s}:{s:RegimeRemainingBasis['rows'][number]['cash_source']}){return <a href={s.url.split('#')[0]+'#page='+s.page} target="_blank" rel="noreferrer">{s.title} · 第{s.page}页 ↗</a>}
export function STRemainingBasis({data:d,explained}:{data:RegimeRemainingBasis|null|undefined;explained?:number}){
 const [symbol,setSymbol]=useState('000793')
 if(!d)return null
 const r=d.rows.find(x=>x.symbol===symbol)??d.rows[0],h=d.rows.find(x=>x.kind==='reorg_reference')!
 return <section className="regime-removal-cohort" aria-label="剩余复权差异与原件冲突">
 <h4>这些复权差异，哪些有解释，哪些仍有冲突？</h4><p>{d.answer}</p>
 <p>固定150只中，原137只直接前复权一致、11只直接读数差异的定义不改。连同此前绝味、章鼓、八菱，目前{explained??3+d.supported_count}只差异有冻结构造解释；京机仍有原件公式冲突。可以复现价格，与可以认证原件全部无误，是两项判断。</p>
 <h5>华闻：当日{pct(h.reference_day_pct)}，要怎样核旧5%边界？</h5>
 <p>6月18日因办理重整转增停牌，6月22日复牌。最后实际成交日是{h.previous_session}，原价{h.previous_raw}元；按公告调整的参考价为{h.reference}元。复牌收盘{h.ex_raw}元，相对原价{pct(h.raw_day_pct)}、相对参考价{pct(h.reference_day_pct)}。旧5%上边界按分币取整为{h.old_up_boundary}元；{Number(h.ex_raw)===Number(h.old_up_boundary)?'实际收盘等于边界，没有突破。':h.above_old_up_boundary?'实际收盘高于边界，需重核具体状态。':'实际收盘未超过该边界。'}不能用“涨幅超过5.00%”直接判突破。</p>
 <p>这是重整转增除权，不是派现金；新增股份不向原股东分配。6月22日公告确认转增股登记至管理人账户，后续分配给投资人、债权人以及整体计划执行仍是后面的程序，不由本次除权重建认证。</p>
 <div className="regime-scroll"><table className="regime-table"><caption>本轮8只；直接差异天数按原定义保留，不将重建结果覆盖旧读数</caption><thead><tr><th>公司</th><th>事项</th><th>价格构造</th><th>直接差异</th><th>原件冲突</th></tr></thead><tbody>{d.rows.map(x=><tr key={x.symbol}><th>{x.name}<small>{x.symbol}</small></th><td>{x.kind==='reorg_reference'?'重整转增除权':'现金分派与精度'}</td><td>{x.supported?'可重建':'未通过，待核'}</td><td>{x.direct_difference_days}日</td><td>{x.source_conflict?'公式分母与结果不一致，待澄清':'所核字段未见此类冲突'}</td></tr>)}</tbody></table></div>
 <p>本轮复用{d.quote_points.toLocaleString()}个报价口径点，对应{d.price_dates.toLocaleString()}个实际成交股票日期，没有新行情查询。三位小数产品、四位因子归一和分币参考价分别重建；不能由拟合成功断言报价商内部一定使用了哪一种算法。</p>
 <label>按公司核构造与原件 <select aria-label="剩余差异公司" value={r.symbol} onChange={e=>setSymbol(e.target.value)}>{d.rows.map(x=><option key={x.symbol} value={x.symbol}>{x.name} · {x.symbol}</option>)}</select></label>
 <article><h5>{r.name} · {r.effective_on}生效</h5><p>所引材料公开于{r.published_on}；登记日{r.record_on}。{r.kind==='reorg_reference'&&`财顾意见落款${r.document_dated_on}，与公开日分别记录。`}</p>
 {r.kind==='cash_dividend'?<p>公告每股含税现金{r.per_eligible_share_cash}元，公告除息参考额{r.reference_cash}元；总股本摊薄与参与分配股本分开。原前收盘{r.previous_raw}元，分币参考价{r.reference}元；按比例计算并取四位因子{r.factor_before}→{r.factor_on}，与原缓存一致。</p>:<p>按所引方案的转增前股本、抵债金额及投资人出资条款，除权参考价可复算为{r.reference}元。出资条款不是本轮到账凭证；“每10股转增12股”也不是向原持有人每10股送12股。</p>}
 {r.source_conflict&&<p className="regime-date-conflict"><strong>原件冲突保留：</strong>京机两处“每10股参考额”公式分母写为616,624,778股，但0.326688元的结果按总股本622,874,778股计算才一致。另一处每股参考额0.0326688元及日行情参考价可复核；不能因此替发行人把原式改写成无误，尚未核到正式更正。</p>}
 <details><summary>看原页、精度与不符日期</summary><Source s={r.cash_source}/><p><Source s={r.date_source}/></p>{r.reference_source&&<p><Source s={r.reference_source}/></p>}{r.reorg_sources?.map(s=><p key={s.url+'#'+s.page}><Source s={s}/></p>)}{r.source_conflict&&<p><Source s={r.source_conflict.source}/></p>}
 <p>实际成交{r.traded_days}日，构造不符{r.product_mismatch_dates.length}日，同因子归一不符{r.normalized_mismatch_dates.length}日；直接读数差异{r.direct_difference_days}日，两边同取分币后仍差{r.same_cent_difference_days}日。分币后的双重取整差异也保留。</p>
 {r.kind==='reorg_reference'?<p>腾讯冻结序列符合除权前原价×参考价÷最后实际前收盘，再取三位小数；两日同取分币仍不同，源于取整顺序。6月22日原件确认的是转增登记至管理人，并未用它认证最终受让人分配。</p>:<><p>公告精度的参考额减法取三位小数可以复现。用参与分配股东的每股现金同样复现：{r.eligible_cash_also_matches?'是，不能仅凭此产品区分两种输入':'否'}；用未取公告精度的摊薄额同样复现：{r.exact_virtual_also_matches?'是':'否'}。这是拟合范围，未取得报价商算法规范。</p><p>按所列参与股本与每股现金计算，并按公告金额精度核总额；参考额的舍入或截取另核。安排、测算与实际收款仍分开。</p></>}
 {r.source_conflict&&<p>按印刷分母计算的每10股额约{Number(r.source_conflict.literal_per_ten).toFixed(6)}元；按总股本计算并截取六位为{r.source_conflict.consistent_per_ten}元。原式与结果同时留存，未认证发行人更正。</p>}
 </details></article>
 <p><strong>判断更新：</strong>“待核”改为有条件的冻结构造解释，旧价格、日期、直接差异和旧制度边界统计保留。价格吻合不代替发行人更正、真实到账或重整执行凭据。</p><p><strong>什么会推翻支持：</strong>{d.what_would_change}</p>
 <details><summary>这轮新增、复用与剩余范围</summary><p>新增{d.new_files}份{d.new_pages}页，复用{d.reused_files}份；共{d.source_pages}页原件留档，按所引关键页核事实。5—6月材料用于解释前置构造，不表示7月以后目录已穷尽更早公告。原件算术冲突{d.source_conflict_companies}家公司；本轮未重建{d.remaining_unreconstructed}家。</p><p>{d.boundary}</p><p>动态ST线、两只退出样本原字节重放、历史官方全名单日期与个案后续程序仍有原有限制；不把11只差异可解释当作整个研究目标已完成。</p></details>
 </section>
}
