import type {NodeMarketInputAudit} from './types'
import {NodePublicationDates} from './NodePublicationDates'

const reasons:Record<string,string>={publication_date_hint_conflict:'公告日期与归档日期线索待核',one_source_price_keys_incomplete:'单一复权来源的完整窗口键缺失',primary_source_not_bound:'原链接未对齐官方原始来源',parent_fact_missing:'原事实链未匹配',parent_metadata_conflict:'原事实字段冲突',prior_evidence_metadata_missing:'原证据摘要或摘录标记缺失',available_before_source_publication:'可得日期早于原披露日期',historical_membership_missing:'历史成员日期缺失',not_in_source_historical_st_membership:'未在该日历史ST成员表内',market_warmup_keys_incomplete:'市场回看日期键不足',node_definition_not_admitted:'节点定义或等级未进入主样本'}

export function NodeMarketAudit({data}:{data:NodeMarketInputAudit}){
  return <section className="learning-freshness" aria-label="节点市场对照输入核对">
    <header className="learning-section-head"><div><p className="eyebrow">独立对照 / 来源与时间</p><h2>节点与市场：先核对对照样本</h2></div><span>效果尚未测量</span></header>
    {data.availability!=='observed'?<p>{data.availability==='source_changed'?'来源已变化，旧盘点失配，需重新执行；尚不显示旧样本数。':'尚无通过当前来源与版本核对的输入盘点，不能比较效果。'}</p>:<>
      <p>已执行输入盘点。时间留出段仅 {data.test_capacity_events} 条、{data.test_capacity_companies} 家公司通过来源、日期及窗口键初筛；预定最低 {data.plan.minimum_test_events} 条、{data.plan.minimum_test_companies} 家。尚未读取价格值、计算结果或拟合模型，日期键齐全不代表数值和效果已验证。</p>
      <details className="market-source-notes"><summary>查看样本来源、时间核对与预定对照</summary>
        {data.observed_at&&<p>本次输入盘点：{new Date(data.observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）。这是盘点时间，来源数据各自的截止日另列。</p>}
        <p>{data.notice}</p>
        <p>本轮P6运行绑定 {data.active_run_linked_events} 条节点，其中原事实链 {data.source_kind_counts?.p6a_verified_fact??'—'} 条、精确标题来源 {data.source_kind_counts?.official_title_exact??'—'} 条。历史表共 {data.event_table_rows} 条，另有 {data.unbound_table_rows} 条未绑定本轮；未绑定不直接判作错误，也不混入本轮。运行元数据另报 {data.p6_run?.verified_event_count} 条，是不同分母。</p>
        <p>最新P8运行的“确定性核对”标签共 {data.latest_deterministic_events} 条：{data.deterministic_lineage_counts?.active_prior_fact??0} 条连到本轮既有事实链、{data.deterministic_lineage_counts?.active_title??0} 条连到标题来源、{data.deterministic_lineage_counts?.not_bound_to_active_run??0} 条未对齐本轮来源和节点字段。这个标签不等于正文已核证，不当作效果样本数。</p>
        <p>主时间范围内原事实链候选 {data.main_window_nominations} 条。下列缺口可同时命中同一记录，不相加作剔除总数：</p><ul>{Object.entries(data.issues??{}).map(([key,count])=><li key={key}>{reasons[key]||'其他待核输入'}：{count} 条</li>)}</ul>
        {data.source_pool_ceiling_events!=null&&<p>当前主范围来源池即使补齐全部缺口，事件数量上限仍仅 {data.source_pool_ceiling_events} 条、{data.source_pool_ceiling_companies} 家公司；{data.source_pool_can_reach_test_minimum?'数量上限可容纳原门槛，实际通过仍另核':'仅修补日期仍无法达到测试门槛，需要增加经核实的公司和事件来源'}。</p>}
        <p>已核 {data.date_reviews?.filter(row=>row.availability==='observed').length??0} 份公告落款；{data.conservative_date_shifts} 条候选采用原日期、已核落款及可用官方目录日期中的较晚日期。事件发生日保留，未恢复精确发布时间，也不回填为本次之前已抓取。</p>
        <NodePublicationDates data={data.publication_metadata}/>
        <p>落款核对须匹配证券代码、公司和董事会签署。附件中的律师签署或计划文本日期仍需单独核查；落款早于归档日期线索时，披露时间冲突继续保留。</p>
        <p className="learning-footnote market-recheck-scroll-hint">左右滑动下方表格可查看公告来源和各年样本数量。</p>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的节点日期核对表" tabIndex={0}><table className="learning-table market-node-date-table"><thead><tr><th scope="col">原始公告</th><th scope="col">核对的落款日</th><th scope="col">本次核对状态</th></tr></thead><tbody>{data.date_reviews?.map(review=><tr key={review.document_id}><th scope="row">{review.company}<small>{review.symbol}</small></th><td>{review.availability==='observed'?<>{review.signed_on}{review.signature_date_text&&/[〇○零一二三四五六七八九十]/.test(review.signature_date_text)&&<small>原文：{review.signature_date_text}</small>}</>:'待核'}</td><td>{review.availability==='observed'?<a href={`${review.source_url}#page=${review.signature_page}`} target="_blank" rel="noreferrer">原始PDF第{review.signature_page}页 ↗</a>:'归档未通过核对，未用于日期调整'}</td></tr>)}</tbody></table></div>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的时间留出容量表" tabIndex={0}><table className="learning-table market-node-date-table"><thead><tr><th scope="col">测试年</th><th scope="col">之前训练段 / 公司</th><th scope="col">测试段 / 公司</th></tr></thead><tbody>{data.folds?.map(fold=><tr key={fold.test_year}><th scope="row">{fold.test_year}</th><td>{fold.train_events} 条 / {fold.train_companies} 家<small>{fold.train_capacity_pass?'数量条件通过，数值尚待核查':'训练数量不足'}</small></td><td>{fold.test_events} 条 / {fold.test_companies} 家</td></tr>)}</tbody></table></div>
        <p>预定比较节点信息与“节点＋市场趋势/回撤”，观察窗 {data.plan.horizon_sessions} 个基准交易日；锚点范围 {data.plan.anchor_start} 至 {data.plan.anchor_end}。测试年份和最低样本不按结果调整；本轮未检验ETF申赎因子，也未测量方法效果。</p>
        <p>本对照底座的市场日期键、历史成员表止于 {data.source_dates?.benchmark_keys_through}、{data.source_dates?.historical_membership_through}；节点信息止于 {data.source_dates?.node_information_through}。个股内核价格键止于 {data.source_dates?.price_keys_through.base_qfq_complete_window}，独立回填价格键止于 {data.source_dates?.price_keys_through.p8_qfq_complete_window}；尚不能覆盖最近两个月压力案例。</p>
      </details>
    </>}
  </section>
}
