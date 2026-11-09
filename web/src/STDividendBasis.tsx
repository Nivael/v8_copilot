import type {RegimeDividendBasis} from './stRegimeTypes'
const pct=(n:number)=>(n>0?'+':'')+n.toFixed(2)+'%'
const money=(n:string)=>Number(n).toLocaleString('zh-CN',{maximumFractionDigits:2})
function Source({source:s}:{source:RegimeDividendBasis['rows'][number]['actions'][number]['cash_source']}){return <a href={s.url.split('#')[0]+'#page='+s.page} target="_blank" rel="noreferrer">{s.title} · 第{s.page}页 ↗</a>}
export function STDividendBasis({data:d}:{data:RegimeDividendBasis|null|undefined}){
 if(!d)return null
 const may=d.rows.find(r=>r.symbol==='002592')!.actions.find(a=>a.ex_on==='2026-05-19')!
 return <section id="st-dividend-basis" className="regime-removal-cohort" aria-label="章鼓八菱分红与复权解释">
 <h4>同一天的涨幅，为什么有三种读数？</h4><p>{d.answer}</p>
 <p><strong>最容易误读的一天：</strong>八菱5月19日，原价变化{pct(may.raw_day_pct)}，按当天除息参考价为{pct(may.reference_day_pct)}，今天的直接前复权回看为{pct(may.direct_qfq_day_pct)}。后一个数已包含9月后来分红对历史价格的调整，不是当时的日涨跌幅。</p>
 <p>当日参考价{may.reference}元，旧5%上边界按分币取整为{may.old_up_boundary}元，实际收盘也是{may.ex_raw}元；没有突破这条价格边界。不能把前复权回看的约5.05%，当作新规前已经越过旧5%边界的证据。整批复盘原本使用日行情参考价和分币边界，相关旧统计不需回填。</p>
 <h5>先看分派安排，再解释价格构造</h5>
 <div className="regime-scroll"><table className="regime-table"><caption>含税每股现金；公告安排不等于具体持有人到账或税后回报</caption><thead><tr><th>公司与除息日</th><th>每股现金</th><th>登记日</th><th>原始收盘变化</th><th>按当日参考价</th><th>直接前复权回看</th></tr></thead><tbody>{d.rows.flatMap(r=>r.actions.map(a=><tr key={a.announcement_id}><th>{r.name}<small>{a.ex_on}</small></th><td>{a.cash_per_share}元</td><td>{a.record_on}</td><td>{pct(a.raw_day_pct)}</td><td>{pct(a.reference_day_pct)}</td><td>{pct(a.direct_qfq_day_pct)}</td></tr>))}</tbody></table></div>
 <p>章鼓7月每股0.1元；八菱5月0.05元、9月再0.1元。冻结的腾讯序列在除息之前减去后续现金，面板原序列则按逐次、四位小数的复权因子比例缩放。{d.supported?'用独立原始收盘重建后，两家各126个成交日期都能复现；这是解释差异，不是删除差异。':'重建尚有未通过条件，先保留对应差异，不作整体认证。'}</p>
 <h5>哪些判断更新，哪些数字保留？</h5><p>{d.what_changed}</p>
 <div className="regime-scroll"><table className="regime-table"><caption>共同区间2026-07-03至{d.through}；收盘价格构造与含税费的持有回报分开</caption><thead><tr><th>公司</th><th>面板原窗口</th><th>腾讯直接读数</th><th>同因子重建</th><th>直接差异仍保留</th></tr></thead><tbody>{d.rows.map(r=><tr key={r.symbol}><th>{r.name}</th><td>{pct(r.windows.all.primary_pct)}</td><td>{pct(r.windows.all.direct_pct)}</td><td>{pct(r.windows.all.rebuilt_pct)}</td><td>{r.direct_difference_days}日</td></tr>)}</tbody></table></div>
 {d.rows.map(r=><details key={r.symbol}><summary>{r.name}：核分红、股数和重建依据</summary>{r.actions.map(a=><div className="regime-price-window" key={a.announcement_id}><h5>{a.published_on}公开 · {a.ex_on}除息</h5><p>每10股{a.cash_per_ten}元，即每股{a.cash_per_share}元。公告所列股本{money(a.shares)}股，按此测算总额{money(a.indicative_total)}元；股本时点为{a.shares_as_of}，没有认证登记日最终股数或实际派付总额。</p><p>{a.share_note}</p><Source source={a.cash_source}/><p>登记{a.record_on}，除息及代派安排{a.ex_on}。 <Source source={a.date_source}/></p>{a.prior_shares&&<p>7月方案基数{money(a.prior_shares)}股，实施公告所列增加{money(a.added_shares!)}股；每股现金不变，测算总额从{money(a.prior_indicative_total!)}元增至{money(a.indicative_total)}元，相差{money(a.total_increase!)}元。</p>}<p>前一成交日{a.previous_session}原价{a.previous_raw}元，除息参考价{a.reference}元；原因子{a.factor_before}按“前因子 × 原前收盘 ÷ 除息参考价”计算并取四位小数后为{a.factor_on}，与冻结因子一致。{Number(a.remaining_future_cash)>0&&`后来仍有每股${a.remaining_future_cash}元分红，直接前复权回看同时受其影响。`}</p></div>)}<p>{r.traded_days}成交日：原始价一致；减后续现金构造不符{r.additive_mismatch_dates.length}日，同因子重建不符{r.normalized_mismatch_dates.length}日。两种原始前复权产品的{r.direct_difference_days}日直接差异继续留在核价专题。</p></details>)}
 <p><strong>可保留的经验：</strong>先问使用的是当日参考价、未复权收盘，还是事后复权序列；再判断涨跌、价格边界和持有回报。两家公司三次分派可检验这条核对方法，不能算三次独立的新规效应验证。</p>
 <p><strong>什么证据会改变判断：</strong>{d.what_would_change}</p><details><summary>来源、历史判断与未完成范围</summary><p>新增{d.primary_documents}份{d.primary_pages}页原件；{d.direct_quote_points}个报价口径点、{d.price_dates}个成交股票日期全部复用，未新增行情查询。八菱5月原件只为解释前置因子补读，不代表已穷尽5月公告。</p><p>{d.boundary}</p><p>旧核价快照保留，两家从“差异待核”更新为“构造可重建”。该结论不改变当时公告或旧价格，也不替代经营、警示解除或实际收款证据。</p></details>
 </section>
}
