import type {MarketCloseDistance, MarketCloseReference as Reference} from './types'

export function CloseDistanceLabel({data,prefix='已取得数据的末日'}:{data?:MarketCloseDistance;prefix?:string}){
  if(!data)return null
  const valid=data.availability==='compared'&&Number.isInteger(data.minimum_sessions)&&Number.isInteger(data.maximum_sessions)
    &&data.minimum_sessions!>=0&&data.maximum_sessions!>=data.minimum_sessions!&&data.series_compared>0
  return <small className="market-close-distance">{valid?`${prefix}距参照 ${data.minimum_sessions===data.maximum_sessions?data.minimum_sessions:`${data.minimum_sessions}～${data.maximum_sessions}`} 个收盘日`:
    data.reason==='data_after_reference'?'数据日期晚于日历参照，未计算日差':`${prefix}的收盘日差暂无法核对`}</small>
}

export function MarketCloseReference({data,distance}:{data?:Reference;distance?:MarketCloseDistance}){
  if(!data)return null
  const ready=data.version==='market_close_distance_v1'&&data.availability==='calendar_computed'&&!!data.latest_scheduled_close
  return <div className="market-close-reference" role="group" aria-label="快照日期与收盘日历参照">
    <p>{ready?`按已核交易日历，最近计划收盘日为 ${data.latest_scheduled_close}，${data.reference_time}（北京时间）。`:'交易日历参照暂不可用，不能判断快照日期距最近收盘日有多远。'}</p>
    {ready&&distance&&<CloseDistanceLabel data={distance} prefix="当前快照目标"/>}
    <p>日差按交易日历计算，数据截止日和修订状态见各来源。</p>
    <details><summary>日历参照依据</summary><p>按观察时刻和15:00参照线计算；盘中不把当天算作已收盘，周末及所列休市日跳过。采用2026休市日历及2026-07-06起的交易时段版本。</p><p><a href={data.calendar_source} target="_blank" rel="noreferrer">交易所2026休市安排 ↗</a> · <a href={data.hours_source} target="_blank" rel="noreferrer">交易时段版本 ↗</a></p><p>日历 {data.calendar_version}；计算观察 {new Date(data.observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）。</p><code>{data.calendar_rule_digest||'无可用参照摘要'}</code></details>
  </div>
}
