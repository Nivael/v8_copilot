import type {SSEGapReview as Review} from './types'

const num=(n:number|undefined)=>n==null?'—':n.toLocaleString('zh-CN')
const time=(s:string)=>new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})
const roles:Record<string,string>={halt_start:'停牌起点',resume:'复牌日',continuous_until_listing_end:'持续至终止上市'}

export function SSEGapReview({data}:{data:Review}){
  const available=['observed','partial'].includes(data.availability)
  const pending=data.episodes?.filter(row=>!row.interval_closed)??[]
  return <details className="market-source-notes" aria-label="沪市历史缺日原因核对">
    <summary>沪市历史缺日 · {available?`已解释 ${num(data.confirmed_missing_days)}/${num(data.not_returned_days)} 股票日`:'依据尚未通过核对'}</summary>
    {!available?<p>公告依据或其绑定的行情原件尚未通过核对，暂不沿用旧的已解释数量；整体历史覆盖继续待补。</p>:<>
      <p>{data.start} 至 {data.through}，已核对 {num(data.distinct_companies)} 家公司的 {num(data.reviewed_episodes)} 组缺日、{num(data.original_pdfs)} 份公告原件。其中 {num(data.closed_episodes)} 组有完整区间依据，解释 {num(data.confirmed_missing_days)} 个缺失股票日；另有 {num(data.unresolved_missing_days)} 日仍待补证。</p>
      {pending.length>0&&<p>区间待补证：{pending.map(row=>`${row.symbol}（${row.unresolved_missing_days}日）`).join('、')}。已核实停牌起点和期末无成交状态，这两项不能独立证明中间每个交易日的状态。</p>}
      <p>{data.note} {data.historical_breadth_ready?'缺日区间已闭合，完整历史分布仍须单独生成及校验。':'沪市完整历史涨跌分布继续待补，沪深整体覆盖不因此提升。'}</p>
      <p className="learning-footnote market-recheck-scroll-hint">左右滑动可查看停复牌日期、区间结论及公告页码。</p>
      <div className="learning-table-wrap" role="region" aria-label="可滚动的沪市停复牌依据表" tabIndex={0}>
        <table className="learning-table"><thead><tr><th scope="col">证券 / 公司</th><th scope="col">日期与区间结论</th><th scope="col">本窗口缺日</th><th scope="col">公告依据</th></tr></thead><tbody>
          {data.episodes?.map(row=><tr key={row.case_id}>
            <th scope="row">{row.symbol}<small>{row.company}</small></th>
            <td>停牌自 {row.start_on}<small>{row.kind==='continuous_to_listing_end'?`${row.end_exclusive} 终止上市，不作复牌日`:row.kind==='start_only'?'区间持续状态待补证':row.kind==='one_day'?'明确停牌一日':`${row.end_exclusive} 复牌，已核对当日成交`}</small></td>
            <td>{row.interval_closed?`已解释 ${row.confirmed_missing_days} 日`:`待补证 ${row.unresolved_missing_days} 日`}<small>{row.window_days[0]} 至 {row.window_days.at(-1)}</small></td>
            <td>{row.proofs.map((proof,index)=><div key={index}><a href={proof.source_url} target="_blank" rel="noreferrer">{roles[proof.role]||proof.role} · 第 {proof.pages.join('、')} 页 ↗</a><small>发布 {proof.published_on}；取得 {time(proof.observed_at)}</small></div>)}</td>
          </tr>)}
        </tbody></table>
      </div>
      <details><summary>逐日查看已解释与待补证代码</summary><div className="learning-table-wrap" role="region" aria-label="可滚动的沪市每日缺日解释表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">收盘日</th><th scope="col">已解释为停牌</th><th scope="col">区间待补证</th></tr></thead><tbody>{data.days?.map(day=><tr key={day.date}><th scope="row">{day.date}</th><td>{day.confirmed_suspended.join('、')||'无'}</td><td>{day.unresolved.join('、')||'无'}</td></tr>)}</tbody></table></div></details>
      {data.materialized_at&&<p className="learning-footnote">本次核对生成于 {time(data.materialized_at)}（北京时间）；事后取得的依据不冒充历史当时已见。</p>}
    </>}
  </details>
}
