import type {ETFAssetIdentity as Identity} from './types'
import {formatShareCount as exact} from './numbers'

const time=(s:string)=>new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})

export function ETFAssetIdentity({data}:{data?:Identity}){
  const ready=data?.availability==='arithmetic_compared'&&data.compared_points===1&&data.reviewed_code==='510310.SH'
    &&data.asset?.scope==='site_states_whole_fund_net_assets'&&data.asset.asset_asof===data.date&&data.NAV_source?.date===data.date&&data.share_source?.date===data.date
  return <div aria-label="资产公布值一致性核对">
    <h3>资产披露与日表的单点核对</h3>
    {!ready?<p>资产披露单点的同日对照当前不齐，不展示旧计算结果；也不把缺失当作零。</p>:<>
      <p>510310归档的 {data.date} 披露点：产品页资产净值与“日表份额 × 同日公布单位净值”{data.relation==='equal_as_published'?'算术上相等':'算术上不同'}。这只核对三个公布值，尚未核实来源独立性。</p>
      <p>不能由相等推定场外份额为零或全基金日份额已验收；差额也不是净申赎，不反推实际份额，不校正任何一天的数据。</p>
      <details className="market-source-notes"><summary>查看这一个披露时点的数值与来源</summary>
        {!data.matches_market_target&&<p>这一时点与当前市场目标不同，不作为目标日覆盖。</p>}
        <p>发行人页面把“基金规模”解释为整个基金层面的资产净值。这里只保留该说明及原始披露值；它不是一张独立的全基金日份额表，资产金额的源端舍入规则也未核实。</p>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的资产公布值对照表" tabIndex={0}><table className="learning-table market-asset-identity-table"><thead><tr><th scope="col">同日输入</th><th scope="col">公布值与单位</th><th scope="col">来源入口及首次取得</th></tr></thead><tbody>
          <tr><th scope="row">产品页资产净值<small>所属 {data.asset!.asset_asof}</small></th><td>{exact(data.asset!.asset_yuan)} 元</td><td><a href={data.asset!.source_url+'#baseinfoAsset'} target="_blank" rel="noreferrer">基金公司资产披露 ↗</a><small>{time(data.asset!.observed_at)}（北京时间）</small></td></tr>
          <tr><th scope="row">日表份额<small>按公布的万份算术换算为份</small></th><td>{exact(data.published_shares)} 份</td><td><a href={data.share_source!.source_url} target="_blank" rel="noreferrer">交易所原响应 ↗</a><small>{time(data.share_source!.observed_at)}（北京时间）</small></td></tr>
          <tr><th scope="row">同日单位净值<small>使用同日历史记录，未套用页面最新日期</small></th><td>{exact(data.unit_nav)} 元/份</td><td><a href={data.NAV_source!.source_url} target="_blank" rel="noreferrer">单位净值原响应 ↗</a><small>{time(data.NAV_source!.observed_at)}（北京时间）</small></td></tr>
        </tbody></table></div>
        <p>日表份额 × 同日单位净值 = {exact(data.shares_times_unit_nav_yuan)} 元（算术乘积）。<br/>资产公布值减去该乘积 = {exact(data.difference_yuan)} 元。这是公布值差，不是资金流。</p>
        <p>{data.note} 季报中的场外份额仍保留其原报告日期，本次核对不改写该披露。</p>
        <p>链接打开当前源页，可能已更新；以上数值和首次取得时间来自已归档原件。</p>
        <details><summary>查看三个原件的对应标识</summary><p>资产原件 <code>{data.asset!.response_sha256}</code></p><p>日份额原件 <code>{data.share_source!.response_sha256}</code></p><p>单位净值原件 <code>{data.NAV_source!.response_sha256}</code></p><p>本次算术核对 <code>{data.comparison_digest}</code></p></details>
      </details>
    </>}
  </div>
}
