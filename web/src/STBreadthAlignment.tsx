import {STBreadthTiming} from './STBreadthTiming'
import packet from './stBreadthAlignment.json'
import breadth from './recentMarketBreadth.json'
import {percent} from './readingFormat'
export function STBreadthAlignment(){
 if(packet.breadth_evidence_sha256!==breadth.evidence_sha256)return <p role="status">广度来源已更新，同窗比较需重新核算。</p>
 const r=packet.reading
 return <section className="reading-section" aria-label="广度转弱后的ST同窗对照"><header><h2>大盘修复，ST也会修复吗？</h2><p>冻结复盘 · 共同覆盖{r.common_start} — {r.common_through}，{r.common_days}个交易日</p></header>
 <p className="reading-lead">不一定。9月11日提示后5日，大盘涨1.61%，动态ST参考仍跌0.83%；9月24日后两者都跌，ST却相对少跌。</p><p>大盘参与面、ST相对强弱和绝对损失要分别看。“不和大盘作对”可以成为风险检查原则，但这组结果不足以确定减仓阈值、危机概率或交易效果。</p>
 <STBreadthTiming/><details className="reading-disclosure"><summary>展开三段事后同窗结果，包括未满窗口</summary><div className="learning-table-wrap"><table className="market-pressure-table"><caption>从提示日收盘起算；完整5日与未满3日分别标注</caption><thead><tr><th>三日条件首提示</th><th>共同后窗</th><th>动态ST参考</th><th>中证全指</th><th>ST相对差</th></tr></thead><tbody>{r.signals.map(s=><tr key={s.date}><th>{s.date}</th><td>{s.observed_following_sessions}交易日 · {s.complete_five?'完整5日':'未满5日'}<small>至{s.through}</small></td><td>{percent(s.st_pct)}</td><td>{percent(s.market_pct)}</td><td>{percent(s.st_minus_market_pp).replace('%','个百分点')}</td></tr>)}</tbody></table></div><p>11月16日后ST共同资料只到19日，只有3日。广度虽到20日，也不能把20日大盘与19日ST拼成同窗；最近完整5日结果仍为空。</p></details>
 <details className="reading-disclosure"><summary>这组对照支持什么，什么会推翻判断？</summary><p>支持同时检查市场持续偏弱与ST自身表现，不用旧全段“相对抗跌”替代近期判断。9月反弹反例也说明，连续三日上涨不足半数并不意味着随后大盘必跌。</p><p>下一步需其他独立市场阶段及假警报对照：如果大盘广度改善时ST也稳定修复，或市场走弱时ST仍保持低回撤，应相应修正“风险叠加”的解释。条件尚未做样本外检验，不据此计算仓位。</p></details>
 <details className="reading-disclosure"><summary>来源、日期与计算限制</summary><p>每段连续第三日仅记一次，后续弱日不重复增加案例。后窗逐日复合动态ST等权收益及同源配对的中证全指收益；ST成分随日变化，不是固定成员账户收益。提示日收盘后才能观察完整广度，未假定该收盘可成交。</p>{packet.boundaries.map(b=><p key={b}>{b}</p>)}<p>ST源标识<code>{packet.st_content_digest}</code>；本轮证据<code>{packet.evidence_sha256}</code>。引用原来源不算新增独立验证。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看ST与广度同窗研究 →</a></p></details></section>
}
