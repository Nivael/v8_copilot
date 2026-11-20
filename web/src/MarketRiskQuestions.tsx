import recent from './recentMarketBreadth.json'
import alignment from './stBreadthAlignment.json'
import timing from './stBreadthTiming.json'
import type {BreadthReading} from './readingTypes'
import {percent} from './readingFormat'
type Purpose='today'|'recent'|'st'
export function MarketRiskQuestions({data,onRead}:{data:BreadthReading;onRead:(purpose:Purpose)=>void}){
 const last=recent.rows[recent.rows.length-1]
 const group=data.groups[0]
 const bound=data.as_of===recent.as_of&&group?.observed_trading_stocks===last.trading&&group.advancing===last.advancing&&group.declining_5pct_or_more===last.declining_5pct_or_more&&alignment.breadth_evidence_sha256===recent.evidence_sha256
 if(!bound)return <section className="reading-section" aria-label="风险线索总览"><h2>先分清风险来自哪里</h2><p>连续复盘与当前收盘截面尚未对应，暂不合并成一份总览。可分别查看当天广度和注明日期的历史复盘。</p></section>
 const weakStart=recent.sequence.days[recent.sequence.days.length-last.streak]?.date
 const signal=alignment.reading.signals[alignment.reading.signals.length-1]
 const lag=timing.reading.rows.find(row=>row.signal_date===signal.date)
 const timingBound=timing.alignment_evidence_sha256===alignment.evidence_sha256&&lag?.following.through===signal.through
 const rebound=alignment.reading.signals.find(row=>row.complete_five&&row.market_pct>0&&row.st_pct<0)
 return <section className="reading-section" aria-label="风险线索总览"><header><h2>先分清风险来自哪里</h2><p>大盘参与面截至{data.as_of}；动态ST共同窗口截至{alignment.reading.common_through}。这是证据总览，尚未校准成危机等级。</p></header><p className="reading-lead">这次既有持续偏弱，也有单日大跌扩散；最近共同窗口中，ST跌得更深。退出能力仍缺直接证据。</p><p>带着目的读：先看压力是否扩散，再看它持续多久，最后核对ST是否更弱、退出是否受限。四组证据分别回答问题，暂不合成一个看似精确的危机分数。</p><aside aria-label="风险信号怎样读"><h3>持续走弱的确认，可能已经偏晚</h3>{timingBound&&lag?<p>{lag.signal_date}收盘三日条件成立时，从{lag.anchor}收盘起，ST参考已{percent(lag.already_st_pct)}、大盘已{percent(lag.already_market_pct)}。这里记录的是此前已经发生的跌幅，不能理解为下跌前预警，也不是你的账户损失。</p>:<p role="status">确认前跌幅与当前同窗来源尚未对应，暂不展示；可进入ST同窗对照分别核查。</p>}{rebound&&<p>同样条件也有反弹反例：{rebound.date}收盘后5个交易日，大盘{percent(rebound.market_pct)}，ST参考{percent(rebound.st_pct)}。持续偏弱不等于随后必跌，大盘反弹也不保证ST修复。</p>}<p><button type="button" onClick={()=>onRead('st')}>核对确认前后与反弹反例</button></p></aside><div className="learning-table-wrap"><table className="market-pressure-table"><caption>四个问题，各看一组证据</caption><thead><tr><th>要判断什么</th><th>已有证据</th><th>接着看什么</th></tr></thead><tbody>
 <tr><th>是一天冲击，还是持续走弱？</th><td>{weakStart}至{last.date}，上涨股票连续{last.streak}个交易日不足一半。</td><td><button type="button" onClick={()=>onRead('recent')}>看转弱过程</button></td></tr>
 <tr><th>当天压力扩散到多广？</th><td>{last.date}，有成交的{last.trading}只股票中，上涨{last.advancing_pct.toFixed(1)}%；跌幅至少5%的占{last.declining_5pct_or_more_pct.toFixed(1)}%。后者不是跌停率。</td><td><button type="button" onClick={()=>onRead('today')}>看当天分布</button></td></tr>
 <tr><th>ST是否比大盘更弱？</th><td>{signal.date}收盘至{signal.through}，ST参考{percent(signal.st_pct)}，大盘{percent(signal.market_pct)}；仅{signal.observed_following_sessions}日，未满5日。</td><td><button type="button" onClick={()=>onRead('st')}>看ST同窗对照</button></td></tr>
 <tr><th>需要退出时能否成交？</th><td>尚不能确认。11月9—19日每日名单主板组及固定150组已核限价配对；官方成员交叉核实、历史盘口队列与执行成本仍待补；日线有成交不等于能按收盘价退出。</td><td><button type="button" onClick={()=>onRead('st')}>核对限价与退出缺口</button></td></tr>
 </tbody></table></div><p>接下来检验：参与面改善能否持续、大跌比例是否收敛、ST是否同步修复。单日上涨或一次压力缓和，不直接改判为全面修复；这些条件还不是已经验证的仓位规则。</p></section>
}
