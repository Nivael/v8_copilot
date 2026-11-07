import type {ExchangeRiskMembership} from './types'

const time=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})
const board:Record<string,string>={main:'沪市主板',star:'科创板',main_and_gem:'深市主板与创业板'}

export function ExchangeRiskLists({data,quoteDate}:{data:ExchangeRiskMembership;quoteDate?:string}){
  return <details className="market-source-notes" aria-label="交易所风险名单观测">
    <summary>交易所风险警示与退市整理名单 · 本次读取</summary>
    {data.availability!=='observed'?<p>暂无通过来源和完整分页核对的名单观测；未知不记为零，收盘名称组继续单独显示。</p>:<>
      <p>读取日期 {data.observed_on}：风险警示A股 {data.risk_warning_a_shares} 只，退市整理A股 {data.delisting_a_shares} 只；另列B股 {data.excluded_b_shares} 只。分类取自交易所名单，不由简称前缀推定。</p>
      {data.is_today_observation===false&&<p>这是上次读取的名单，当前名单需要重新采集。</p>}
      <p>{data.note} {quoteDate&&`上方收盘截面是 ${quoteDate}，本名单读取于 ${data.observed_on}。`}两个日期分别保留，不能直接合并计算历史ST收益。</p>
      <p className="learning-footnote market-recheck-scroll-hint">左右滑动表格可查看分类数量和来源数据日。</p>
      <div className="learning-table-wrap" role="region" aria-label="可滚动的风险名单分类表" tabIndex={0}>
        <table className="learning-table"><thead><tr><th scope="col">来源分类</th><th scope="col">A股 / B股</th><th scope="col">表内记录 / 查询次数</th><th scope="col">来源声明的数据日</th></tr></thead>
          <tbody>{data.groups?.map(group=><tr key={group.group}><th scope="row"><a href={group.source_url} target="_blank" rel="noreferrer">{board[group.board]||group.venue} ↗</a><small>{group.kind==='risk_warning'?'风险警示股票':'退市整理股票'}</small></th><td>{group.a_shares} / {group.b_shares}</td><td>{group.source_rows} 条 / {group.pages_read} 次</td><td>{group.source_as_of||'来源未声明数据日'}</td></tr>)}</tbody>
        </table>
      </div>
      <p>退市整理A股：{data.rows?.filter(row=>row.share_class==='A'&&row.kind==='delisting').map(row=>`${row.ts_code} ${row.name}`).join('、')||'本次选定分类表未列记录'}。</p>
      <p>另列B股：{data.rows?.filter(row=>row.share_class==='B').map(row=>`${row.ts_code} ${row.name}`).join('、')||'本次选定分类表未列记录'}。</p>
      <p>深交所的两个分类分别查询，未选中的空页不当作零记录；每个分类按其分页总数读完。</p>
      <p>实际取得 {data.started_at&&time(data.started_at)} 至 {data.completed_at&&time(data.completed_at)}（北京时间）。{data.reparsed_at&&`归档再解析 ${time(data.reparsed_at)}；首次取得时间保留。`}</p>
    </>}
  </details>
}
