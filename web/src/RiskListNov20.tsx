import packet from './riskListNov20.json'
import cohort from './stLimitCohorts.json'
export function RiskListNov20({priceAsOf}:{priceAsOf:string}){
 if(priceAsOf!==packet.reading.target_day)return null
 if(packet.input_asset!==cohort.input_asset)return <p role="status">名单参照与原研究输入不对应，待重新核对。</p>
 const r=packet.reading
 return <details className="reading-disclosure"><summary>11月20日的官方ST名单，已核到哪一步？</summary><p>深市风险警示表已明确标注20日，所选主板A股74只与19日保存参照的代码、简称一致。沪市当前主板表68只也与旧参照一致，但未注明数据日，不能据此写成“沪深20日名单已全部确认”。</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>名单适用日与实际读取日分开</caption><thead><tr><th>来源分类</th><th>主板A股</th><th>来源注明的数据日</th><th>实际读取日</th><th>与19日参照</th></tr></thead><tbody>{r.comparisons.map(g=><tr key={g.group}><th>{g.group==='szse_risk'?'深市风险警示表':'沪市主板风险警示表'}</th><td>{g.main_a_shares}只<small>表内全部{g.all_rows}条，含其他范围</small></td><td>{g.source_as_of||'未声明，20日仍待确认'}</td><td>{g.observed_on}</td><td>{g.codes_equal_prior&&!g.name_differences.length?'代码、简称一致':'有差异，需核对'}</td></tr>)}<tr><th>深市退市整理表</th><td>本次读取为空</td><td>未声明，不认证20日为零</td><td>{r.observation_day}</td><td>不作目标日数量证明</td></tr></tbody></table></div>
 <p>21日读取到的内容，不自动等于21日或20日的适用名单；两份列表恰好相同，也不能代替缺失的日期依据。固定150只旧样本观察与当日名单继续分开。</p>
 <details><summary>分页、分类及来源怎样核？</summary><p>深市风险表6页共115条，其中113条A股、2条B股；本轮只比较其中74只主板A股，39只创业板A股另在原表保留。沪市主板表69条，其中68条A股、1条B股；科创板不在这次主板比较范围。</p><p>官网目录及查询定义与已核版本一致，按声明页数读全，逐页日期、代码、简称、A/B股与主板范围均核。空的未选分类不当作零记录；这次另行查询退市整理选中表，仍保留其未注明日期的限制。</p><p>{r.boundary}</p>{packet.source_refs.filter(s=>['szse_risk:1','sse_main_risk','szse_delisting:1'].includes(s.key)).map(s=><p key={s.key}><a href={s.final_url} target="_blank" rel="noreferrer">{s.key==='szse_risk:1'?'深市风险警示表第一页':s.key==='sse_main_risk'?'沪市主板风险警示表':'深市退市整理选中表'} ↗</a> · 取得{s.observed_at}；SHA256 <code>{s.response_sha256}</code>。</p>)}<p><a href={'/runs#research-'+packet.research_run_id}>查看名单日期、完整分页与逐项对照研究 →</a></p></details></details>
}
