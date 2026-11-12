import type {ETFFundScopeRules as Rules} from './types'

const targets:Record<string,string>={iopv:'份额参考净值（IOPV）',off_exchange_subscribed_shares:'场外申购确认份额',off_exchange_subscription_fee:'场外申购费用',
  off_exchange_redemption_payment_and_fee:'场外赎回金额及费用',unit_NAV:'基金单位净值',distribution_per_share:'每份分红金额'}
const units:Record<string,string>={CNY_per_share:'元/份',fund_share:'份',CNY:'元'}
const cutoffLabels:Record<string,string>={general_content:'一般内容',financial:'财务数据',NAV_performance:'净值表现',personnel:'主要人员'}
const time=(value:string|undefined)=>value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'

export function ETFFundScopeRules({data}:{data:Rules}){
  const ready=data.availability==='scoped_rules_reviewed'&&data.review_scope==='one_prospectus_version_business_roles_only'
    &&data.document?.code==='510310.SH'&&data.reviewed_documents===1&&data.rounding_rules?.length===6&&data.transfer?.conditional
  const doc=data.document
  const source=(page:number)=>`${doc?.response_url}#page=${page}`
  return <div aria-label="ETF全基金范围与业务角色核对">
    <h3>为什么只核对折算还不够</h3>
    <p>净申赎估算同时需要全窗份额事件、全基金日份额范围、源端精度和最终修订的核实。各项核实完成后计算份额名义估算。</p>
    {!ready?<p>510310的原文业务条款当前不可用，不展示上次的具体解释或舍入规则。</p>:<>
      <p>510310这一说明书版本分别规定场内、场外登记，并允许在制定和发布相关规则等条件满足时，将场外份额转为场内份额。据此，单一登记范围的份额可能改变，基金总份额并不随这类转托管增加。本窗实际办理量仍未知，不据此校正任何一天的数据。 <a href={source(48)} target="_blank" rel="noreferrer">登记与条件 · 原PDF第48页 ↗</a></p>
      <details className="market-source-notes"><summary>查看510310的登记、对价和舍入对象</summary>
        <p>仅核对 {doc?.published_on} 发布的这一份说明书，{data.reviewed_passages} 个指定段落、原PDF {doc?.page_count} 页。业务开放状态按观察窗继续核对。</p>
        <p>场内相关登记由 {data.registrars?.exchange} 办理，场外申购赎回登记由 {data.registrars?.off_exchange} 办理。 <a href={source(9)} target="_blank" rel="noreferrer">原PDF第9页 ↗</a></p>
        <p>场内申购、赎回均按份额申请，对价包含证券、现金替代、现金差额及其他对价；场外按金额申购、份额赎回，对价为现金。 <a href={source(35)} target="_blank" rel="noreferrer">业务对象 · 原PDF第35页 ↗</a></p>
        <p>场外转场内附带条件；反方向须另行公告。本项未确认当前业务可办理，也未确认日表完整涵盖哪个登记范围。 <a href={source(32)} target="_blank" rel="noreferrer">上市前转托管 · 原PDF第32页 ↗</a></p>
        <p>以下六条属于不同计算对象，均不作为交易所日份额字段的舍入规则。表格可左右滑动查看原文页。</p>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的ETF舍入对象表" tabIndex={0}><table className="learning-table market-scope-rule-table"><thead><tr><th scope="col">计算对象</th><th scope="col">单位及版本所述规则</th><th scope="col">物理页依据</th></tr></thead><tbody>{data.rounding_rules?.map(row=><tr key={row.target}>
          <th scope="row">{targets[row.target]||row.target}</th><td>{units[row.unit]||row.unit}；{row.fractional_digits===0?'保留整数':`保留${row.fractional_digits}位小数`}；{row.method==='half_up'?'四舍五入':'下一位舍去'}</td><td><a href={source(row.proof_page)} target="_blank" rel="noreferrer">原PDF第{row.proof_page}页 ↗</a></td>
        </tr>)}</tbody></table></div>
        <p>该版本规定场内外均采用现金分红；这是分配方式条款，不证明观察窗内实际发生了分红。 <a href={source(data.distribution_mode_proof_page||74)} target="_blank" rel="noreferrer">原PDF第74页 ↗</a></p>
        <p>内容截止分别为：{Object.entries(data.cutoffs||{}).map(([key,value])=>`${cutoffLabels[key]||key} ${value}`).join('；')}。四类日期分别保留，不统一改为发布日期。财务数据未经审计。 <a href={source(4)} target="_blank" rel="noreferrer">截止日 · 原PDF第4页 ↗</a></p>
        <p>{data.note}</p><p>原件取得 {time(doc?.observed_at)}；本次核对生成 {time(data.materialized_at)}（北京时间），不回填为历史当时可见。</p>
        <p>来源摘要 <code>{data.content_digest}</code></p>
      </details>
    </>}
  </div>
}
