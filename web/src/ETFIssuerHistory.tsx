import {ETFName} from './ETFName'
import type {ETFIssuerHistory as History} from './types'
import {formatShareCount as exact} from './numbers'

const state:Record<string,string>={observed:'已核对返回记录表',empty_table_unconfirmed:'返回空表，尚不能确认无分红',query_failed:'查询失败，记录数量未知'}
const time=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})

export function ETFIssuerHistory({data}:{data:History}){
  return <div className="market-source-notes" role="region" aria-label="发行人ETF分红历史核对"><details>
    <summary>{data.funds.length>0?`发行人分红历史：有效记录表 ${data.history_tables_observed}/${data.declared_etfs}；空表待核 ${data.empty_tables_unconfirmed}；查询失败 ${data.query_failed_etfs}`:'发行人分红历史：尚无通过核验的快照'}</summary>
    <p>{data.note}</p>
    {data.funds.length===0?<p>尚无通过当前原响应、字段及单位校验的历史表，未将缺失记录填零。</p>:<>
      <p>本项核对窗 {data.window_start} 至 {data.through}；本次查询日期 {data.query_cutoff}，首次取得时间逐基金列出。登记日、现金发放日分别计数；原表未核实的除息日继续留空。</p>
      {data.market_target&&data.through!==data.market_target&&<p>当前市场目标为 {data.market_target}，此历史表尚未覆盖新目标，不能沿用为新目标核验。</p>}
      <p>“查询失败”和“暂无记录”可能在发行人页面显示成相同空态，此处保留实际查询状态。有效记录表未列窗口内事项，也不认证整个观察窗没有其他份额事件。</p>
      <p className="learning-footnote market-recheck-scroll-hint">左右滑动表格可查看日期、金额单位与核查范围。</p>
      <div className="learning-table-wrap" role="region" aria-label="可滚动的发行人分红核对表" tabIndex={0}><table className="learning-table market-issuer-history-table"><thead><tr><th scope="col">ETF / 发行人</th><th scope="col">实际返回状态</th><th scope="col">最近一条已列记录</th><th scope="col">本项窗口与拆分表</th></tr></thead><tbody>{data.funds.map(fund=>{
        const latest=fund.latest_listed_distribution
        return <tr key={fund.code}><th scope="row"><ETFName code={fund.code}/><small><a href={fund.source_url} target="_blank" rel="noreferrer">{fund.issuer} · 历史页 ↗</a></small><small>本次取得 {time(fund.observed_at)}（北京时间）</small></th>
          <td>{state[fund.availability]||'尚未核实'}{fund.table_records!=null&&<small>原表返回 {fund.table_records} 条分红记录</small>}{fund.availability!=='observed'&&<small>窗口内次数保持未知，未填零</small>}</td>
          <td>{latest?<><span>登记日 {latest.record_on}</span><small>现金发放日 {latest.cash_paid_on}</small><small>原表每{latest.source_unit_shares}份 {exact(latest.source_amount_text)} 元；折每份 {exact(latest.amount_yuan_per_share)} 元</small>{latest.off_exchange_record_on&&<small>场外登记 {latest.off_exchange_record_on}；场外发放 {latest.off_exchange_cash_paid_on}</small>}{latest.evaluation_reference_on&&<small>收益评价基准日 {latest.evaluation_reference_on}，不当作除息日</small>}<small>除息日未在本项核实</small></>:<span>未取得可用记录，未据空态推定无事件</span>}</td>
          <td>{fund.window_record_date_count==null?<span>分红窗口次数未知</span>:<><span>登记日在窗内 {fund.window_record_date_count} 条</span><small>现金发放日在窗内 {fund.window_cash_paid_date_count} 条</small></>}{fund.split_table_status==='observed'?<><small>拆分表已返回 {fund.splits.length} 条，其中本窗 {fund.window_split_count} 条</small><details><summary>原表所列拆分记录</summary>{fund.splits.map(split=><p key={split.effective_on}>{split.effective_on} · 比例 {split.ratio}</p>)}<p>属于本次取得的历史表，不回填为历史当时可见，不用于当前曲线校正。</p></details></>:<small>拆分表尚未核对</small>}</td>
        </tr>
      })}</tbody></table></div>
      <details className="learning-manifest"><summary>原响应、查询与字段依据</summary><p>本次归档 {data.completed_at&&time(data.completed_at)}（北京时间）；本次观察不作为历史当时可得的数据。</p>{data.reparsed_at&&<p>归档响应重新解析于 {time(data.reparsed_at)}（北京时间）；首次取得时间保留，未再次联网。</p>}{data.funds.map(fund=><p key={fund.code}>{fund.code}：{fund.responses.map((ref,i)=><span key={i}>{ref.method} {ref.url} · 参数 {JSON.stringify(ref.params)} · 取得 {time(ref.observed_at)}（北京时间）；</span>)}</p>)}<p>原响应按摘要保存；发行人字段映射和金额单位随原始页面及脚本一起核对。净申赎金额继续未发布。</p></details>
    </>}
  </details></div>
}
