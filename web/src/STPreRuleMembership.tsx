import {useState} from 'react'
import type {RegimePreRuleMembership} from './stRegimeTypes'
const label:Record<string,string>={warning_removed:'撤销风险警示',terminal_entry:'进入退市整理',delisted:'公告摘牌'}
export function STPreRuleMembership({data:d}:{data:RegimePreRuleMembership|null|undefined}){
 const [filter,setFilter]=useState('all'),[symbol,setSymbol]=useState('000972')
 if(!d)return null
 const rows=d.rows.filter(r=>filter==='all'||(filter==='mirror'?r.verification_level!=='official_body':r.kind===filter))
 const r=d.rows.find(r=>r.symbol===symbol)??d.rows[0]
 return <section className="regime-removal-cohort" aria-label="制度前成员移出边界"><h4>制度前移出的48只，究竟去了哪里？</h4><p>{d.answer}</p>
 <p>移出名单不能一概当摘帽：退市整理开始后可能仍在交易，摘牌又是另一阶段。这轮补核的是“何日、因何离开ST研究范围”；不把48个边界说成197只期初名单或125日全体成员均已独立认证。</p>
 <h5>与7月新规后的摘帽，有什么具体不同？</h5><p>制度前这{d.warning_removed}次撤销发生在7月6日之前，公告均明示撤销后的普通股日涨跌幅为10%；其中{d.explicit_5_to_10}份还直接写明5%→10%，另{d.warning_removed-d.explicit_5_to_10}份只明示撤销后10%，不把未写的前值冒充原文。新规后此前核过的{d.post_rule_removed}次，摘帽后仍为10%，不能照搬同一种“放宽涨跌幅”的解释。</p><p>这是机制差异，不是收益因果结论。两批公司、日期和市场环境不同，仍需同窗收益与大盘对照，不能直接分摊涨幅限制的贡献。</p>
 <p><strong>中基的判断更新：</strong>6月29日撤销退市风险警示、恢复“中基健康”，11月4日再次ST。早期移出日期已有原件支持；本次重新入池不称历史首次，摘帽也没有保证未来不再出现新风险。</p>
 <label>按移出结果查看<select aria-label="制度前边界范围" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">全部48处边界</option><option value="warning_removed">撤销风险警示37处</option><option value="terminal_entry">退市整理10处</option><option value="delisted">公告摘牌1处</option><option value="mirror">官方原PDF字节待补5处</option></select></label>
 <details><summary>展开逐公司日期与来源级别</summary><div className="regime-scroll"><table className="regime-table"><thead><tr><th>当时公司</th><th>提供方最后在册</th><th>公告实施/首次移出</th><th>去向</th><th>原文层级</th></tr></thead><tbody>{rows.map(x=><tr key={x.symbol}><th>{x.name}<small>{x.symbol}</small></th><td>{x.last_provider_member}</td><td>{x.effective_on}<small>与首次移出日一致</small></td><td>{label[x.kind]}</td><td>{x.verification_level==='official_body'?'官方文档':'交易所目录＋公告PDF镜像'}</td></tr>)}</tbody></table></div></details>
 <label>按公司核原文<select aria-label="制度前边界公司" value={r.symbol} onChange={e=>setSymbol(e.target.value)}>{d.rows.map(x=><option key={x.symbol} value={x.symbol}>{x.name} · {x.symbol}</option>)}</select></label>
 <article><h5>{r.name}：{r.effective_on}{label[r.kind]}</h5><p>原文所列实施日与提供方首次移出日相同；此前最后在册日为{r.last_provider_member}。{r.kind==='warning_removed'?`撤销后简称为${r.post_name}，不再保留ST标记。`:r.kind==='terminal_entry'?'这里核的是进入退市整理，不用它认证实际最后交易日或后续摘牌日。':'这里核公告明确的摘牌日，不误写为退市整理起点。'}</p>
 <details><summary>看所引原页、日期差异与认证限制</summary><a href={r.source.url.split('#')[0]+'#page='+r.source.page} target="_blank" rel="noreferrer">{r.source.title} · 第{r.source.page}页 ↗</a>{r.source.catalog_url&&<p><a href={r.source.catalog_url} target="_blank" rel="noreferrer">交易所目录原公告链接 ↗</a></p>}<p>目录/载体日期{r.metadata_published_on}；原文落款{r.document_dated_on??'本轮未可靠提取'}。{r.date_conflict?'两日期先后存在差异，保留两种日级行情窗口，不强定最早反应。':'不将文件落款与披露时间混用。'}</p>{r.kind==='warning_removed'&&<p>{r.old_band_explicit?'原件在涨跌幅段明确写5%改为10%。':'原件明示撤销后10%；本轮未把前5%标成这份原文明确写出。'}</p>}<p>{r.source.host_is_official?'本份PDF来自官方披露载体，字节与所引页文本已核。':'本份为发行人公告PDF镜像，已与交易所目录的代码、标题、日期核对；官方原PDF字节尚未取得，不称直接官方原件认证。'}</p><p>摘要{r.source.sha256.slice(0,12)}；取得于{r.source.observed_at}。实施日期吻合不证明全年没有其他状态变化，也不代替公司经营、回款或后续程序核验。</p></details></article>
 <details><summary>这轮补了什么，还有什么没核齐</summary><p>另取4月1日至7月5日48家公司目录，{d.catalog_pages}页元数据、{d.catalog_rows}条记录；不把它并成原7月以后156家公司目录。48份147页公告，其中{d.official_body_files}份直接官方文档、{d.mirror_files}份PDF镜像；5份官方原字节仍待补，目录/落款差异{d.date_conflicts}处保留。旧价格、名单、日路径和旧原问保留。</p><p>{d.boundary}</p><p>巨潮公司检索403、沪市PDF网页校验拦截及3次目录超时均留档；后者经有界重试补齐目录，没有反复绕过受限接口。</p></details>
 <p><strong>什么会推翻这轮支持：</strong>正式更正、撤销后仍保留ST的证据、实际实施日与目录不符，或原件与镜像冲突。出现后先修正相应边界与受影响窗口，不能因报价能复现就保留错误名单。</p></section>
}
