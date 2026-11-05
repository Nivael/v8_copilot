import type {SSEHistoryArchive} from './types'

const num=(value:number|undefined)=>value==null?'—':value.toLocaleString('zh-CN')
const time=(value:string|undefined)=>value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'

export function SSEHistorySources({data,reconciled=false}:{data:SSEHistoryArchive;reconciled?:boolean}){
  return <details className="market-source-notes" aria-label="沪市历史价格来源核对"><summary>沪市历史来源 · 范围与价格原件核对</summary>
    {data.availability!=='observed'?<p>尚无通过全量来源核对的沪市价格归档，历史涨跌分布与ST路径继续待补。旧数量不作为当前覆盖。</p>:<>
      <p>{data.start} 至 {data.through}，涉及 {num(data.distinct_securities)} 只不同A股、{num(data.days?.length)} 个收盘日期。按上市与终止日期重建每日范围，保留后来退出者；期内新上市 {num(data.new_listings?.length)} 只，终止上市 {num(data.ended_listings?.length)} 只。</p>
      <p>每日挂牌数已逐一与上交所日统计核对；原始登记表 {num(data.registry_source_rows)} 条、登记及日统计原件 {num(data.basis_responses)} 份。另核对 {num(data.price_responses)} 只证券的价格原件，期末 {num(data.endpoint_compared_trading)} 条有成交记录与独立收盘截面逐项一致。</p>
      <p>目标范围共 {num(data.expected_security_days)} 股票日；有成交价格记录 {num(data.observed_trading_days)} 条，源端未返回 {num(data.not_returned_days)} 股票日，源端明确无成交 {num(data.explicit_nontrading_days)} 股票日。保留原始前收参考价，缺失不填零。</p>
      <p>{reconciled?'此项保留原价格归档的未返回数量；缺日已另由停复牌登记全部解释，沪深合并分布见上方独立核对。历史ST成员与价格路径仍需独立核验。':'缺日原因和历史ST成员生效依据继续核实；沪市完整历史分布、历史ST成员与价格路径仍未发布。来源本次简称单独列示，整体覆盖保持原状态。'}</p>
      <p className="learning-footnote market-recheck-scroll-hint">左右滑动表格可查看完整日期、挂牌数量和缺日代码。</p>
      <div className="learning-table-wrap" role="region" aria-label="可滚动的沪市区间上市变化表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">证券 / 来源本次简称</th><th scope="col">区间变化</th><th scope="col">日期</th></tr></thead><tbody>
        {data.new_listings?.map(row=><tr key={row.code+'new'}><th scope="row">{row.code}<small>{row.observed_name}</small></th><td>上市</td><td>{row.listed_on}</td></tr>)}
        {data.ended_listings?.map(row=><tr key={row.code+'end'}><th scope="row">{row.code}<small>{row.observed_name}</small></th><td>终止上市</td><td>{row.ended_on}</td></tr>)}
      </tbody></table></div>
      <details><summary>查看逐日价格输入与缺日代码</summary><div className="learning-table-wrap" role="region" aria-label="可滚动的沪市每日价格输入表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">收盘日</th><th scope="col">挂牌 / 有成交</th><th scope="col">源端未返回代码</th><th scope="col">明确无成交代码</th></tr></thead><tbody>{data.days?.map(day=><tr key={day.date}><th scope="row">{day.date}</th><td>{num(day.listed_members)} / {num(day.observed_trading)}</td><td>{day.not_returned.join('、')||'无'}</td><td>{day.explicit_nontrading.join('、')||'无'}</td></tr>)}</tbody></table></div></details>
      <p>价格原件实际取得 {time(data.first_price_observed_at)} 至 {time(data.source_fetched_at)}；范围依据取得至 {time(data.basis_fetched_at)}；本次核对生成于 {time(data.materialized_at)}（北京时间）。这是事后取得的历史输入，效果尚未测量。</p>
      <p><a href="https://www.sse.com.cn/assortment/stock/list/share/" target="_blank" rel="noreferrer">证券登记来源 ↗</a> · <a href="https://www.sse.com.cn/market/stockdata/overview/day/" target="_blank" rel="noreferrer">每日挂牌统计 ↗</a> · <a href="https://www.sse.com.cn/market/price/trends/" target="_blank" rel="noreferrer">个股历史行情入口 ↗</a></p>
    </>}
  </details>
}
