import type {RegimeExitQuoteReplay} from './stRegimeTypes'
const pct=(n:number|null)=>n==null?'缺实际成交端点':(n>0?'+':'')+n.toFixed(2)+'%'
const label:Record<string,string>={before20:'规则前20日',after20:'规则后20日',before40:'规则前40日',after40:'规则后40日','5':'最近5日'}
export function STExitQuoteReplay({data:d}:{data:RegimeExitQuoteReplay|null|undefined}){
 if(!d)return null
 return <section className="regime-removal-cohort" aria-label="退出样本原字节重放">
 <h4>退出样本核回来了，哪些比较要更新？</h4><p>{d.answer}</p>
 <p>康佳在共同终点前已摘牌，萃华在共同起点没有成交；所以7月3日至11月6日仍不能给它们计算共同区间收益。退出不等于收益为零，也不能直接删掉公司。本轮补回的是可复核的报价证据，以及实际具备两端成交的短窗口。</p>
 <div className="regime-scroll"><table className="regime-table"><caption>两家公司都留在固定150名单；空值不由其他日期代填</caption><thead><tr><th>样本</th><th>已核实际成交</th><th>7月3日</th><th>11月6日</th><th>完整区间收益</th></tr></thead><tbody>{d.rows.map(r=><tr key={r.symbol}><th>{r.name}<small>{r.symbol}</small></th><td>{r.traded_days}日<small>{r.first_trade}至{r.last_trade}</small></td><td>{r.anchor_actual_close==null?'缺成交':r.anchor_actual_close.toFixed(2)+'元'}</td><td>{r.endpoint_actual_close==null?'摘牌后无成交':r.endpoint_actual_close.toFixed(2)+'元'}</td><td>{pct(r.windows.all.checked_pct)}</td></tr>)}</tbody></table></div>
 <p>原价逐日核验从{d.old_raw_agree_companies}只扩展到{d.new_raw_agree_companies}只；直接前复权一致从{d.old_qfq_agree_companies}只到{d.new_qfq_agree_companies}只，原11只直接差异及其构造解释保留。完整区间同一{d.full_window_summary.paired}只的{d.full_window_summary.primary_positive}只上涨、中位数{pct(d.full_window_summary.primary_median_pct)}不变；下列短窗因新核样本纳入，分母与中位数需要更新。</p>
 <details><summary>看哪些短窗口变化，以及为什么</summary><div className="regime-scroll"><table className="regime-table"><thead><tr><th>窗口</th><th>补入可比样本</th><th>旧→新配对数</th><th>旧→新中位数</th></tr></thead><tbody>{d.changed_windows.map(x=><tr key={x.window}><th>{label[x.window]??x.window}</th><td>{x.added_symbols.includes('000016')?'康佳':'萃华'}</td><td>{x.before.paired}→{x.after.paired}</td><td>{pct(x.before.primary_median_pct)}→{pct(x.after.primary_median_pct)}</td></tr>)}</tbody></table></div><p>前后20日、前后40日均维持同一批公司，两段都能算才纳入。康佳可补入这两组；萃华可补入最近5日，不能借此补齐7月3日起点。变化来自覆盖范围补全，不能解释为行情重新发生或制度效果改变。</p></details>
 <details><summary>核对旧响应、退出原因与剩余限制</summary><p>本轮找回并重放{d.responses}份旧响应、{d.quote_points}个报价口径点，对应{d.traded_security_days}个实际成交股票日期；没有新报价请求。每家腾讯/东方财富各有原始价和前复权，两口径不是两个独立渠道，底层供数独立性仍未认证。</p>{d.rows.map(r=><article key={r.symbol}><h5>{r.name}：{r.explanation}</h5><p>无成交但有提供方参考值{r.reference_only_dates.length}日；不当实际成交；另有{r.zero_price_placeholder_dates.length}日零价占位，不当参考价或收益端点。最后实价{r.last_actual_close.toFixed(2)}元，日期{r.last_trade}，不搬到缺价端点。</p>{r.channels.map(c=><p key={c.key}><a href={c.source.url} target="_blank" rel="noreferrer">{c.key} · 原请求地址 ↗</a><small>使用冻结响应{c.points}点；原取得时间{c.source.observed_at}，摘要{c.source.sha256.slice(0,12)}。链接可能更新，不代表本轮重新请求。</small></p>)}</article>)}<p>{d.boundary}</p></details>
 <p><strong>什么会推翻更新：</strong>原字节摘要、实际成交日期或任一渠道价格出现冲突，就撤回相应覆盖认证并重算受影响窗口；缺口不能靠补零消失。动态ST逐日线及历史官方名单边界继续核。</p>
 </section>
}
