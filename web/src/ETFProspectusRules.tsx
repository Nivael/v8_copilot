import {ETFName} from './ETFName'
import type {ETFProspectusRules as Rules} from './types'
import {formatShareCount as exact} from './numbers'

const rounding:Record<string,string>={nearest_whole_share:'该版本述份额四舍五入至整数',floor_to_whole_share:'该版本述份额截去小数部分'}

export function ETFProspectusRules({data}:{data:Rules}){
  return <section className="learning-freshness" aria-label="ETF招募说明书条款核对">
    <header className="learning-section-head"><div><p className="eyebrow">规则版本 / 示例 / 历史复述</p><h2>申赎规则与实际事件分开</h2></div><span>条款核对 {data.reviewed_versions}/{data.selected_prospectus_versions??'—'} 份筛选版本</span></header>
    <p>{data.note}</p>
    {data.versions.length===0?<p>所列版本尚未通过原文与日期核对，暂不展示规则或历史比例。</p>:<>
      <p>口径解释：所列版本的申赎对价包含组合证券及现金项目，份额×净值不能直接等同现金进出；规则文本也不能代替实际事件记录。未列出的ETF规则不由这些文件证明。</p>
      <details className="market-source-notes"><summary>查看已核对条款（{data.versions.length}份版本）</summary>
        <div className="learning-table-wrap"><table className="learning-table market-prospectus-table"><thead><tr><th scope="col">ETF / 版本与日期</th><th scope="col">本版本所述每笔业务单位</th><th scope="col">对价与分红规则</th><th scope="col">假设示例与历史事项复述</th></tr></thead><tbody>{data.versions.map(version=>{
          const history=version.historical_restatement
          return <tr key={`${version.code}-${version.publication_date}`}>
            <th scope="row"><ETFName code={version.code}/><small>发布于 {version.publication_date}</small><small>主要内容截止 {version.content_asof}</small><small>财务及表现数据截止 {version.financial_data_asof}</small>{version.cutoff_exception&&<small>{version.cutoff_exception}</small>}<small>财务数据未经审计</small>
              <details><summary>原文页码与取得时间</summary><p>所列条款涉及 {version.reviewed_pages.length} 页；原文共 {version.source_page_count} 页，未声称逐页完整核对。</p>{version.reviewed_pages.map(page=><small key={page}><a href={`${version.pdf_url}#page=${page}`} target="_blank" rel="noreferrer">所列条款 · PDF第{page}页 ↗</a></small>)}<small>本次取得 {new Date(version.document_observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）</small></details>
            </th>
            <td>{version.minimum_units.map(unit=><div key={unit.route}><p>{unit.label}：{exact(unit.stated_unit_shares)} 份</p><small><a href={`${version.pdf_url}#page=${unit.table_page}`} target="_blank" rel="noreferrer">业务单位条款 · 第{unit.table_page}页 ↗</a></small></div>)}<small>每笔单位，不是基金总份额的折算倍数</small><small>当前市场目标日是否仍有效：尚未核对</small></td>
            <td><p>对价含 {version.consideration_components.join('、')}。</p><p>所列分配方式：现金分红；规则上限每年 {version.max_annual_distributions_as_stated} 次。</p><small>观察窗实际分红次数：尚未核对</small><small>上限不代表已经分红，现金分红不自动填入申赎金额</small><details><summary>本版本分红条件</summary><p>{version.distribution_condition_as_stated}</p></details></td>
            <td>{version.illustration&&<div><p>假设示例：{exact(version.illustration.before_shares)} 份 × {version.illustration.stated_ratio} → {exact(version.illustration.after_shares)} 份。</p><small>仅为文中假设，不登记为实际折算事件</small></div>}
              <p>文中历史复述：{history.event_on} 折算，比例 {history.stated_ratio}；变更登记 {history.registered_on}。</p><small>{rounding[history.rounding_in_this_version]||'该版本舍入方式待核对'}</small>
              {history.pages.map(page=><small key={page}><a href={`${version.pdf_url}#page=${page}`} target="_blank" rel="noreferrer">历史复述 · 第{page}页 ↗</a></small>)}
              <small>这份后续版本不能回填为历史当时已知，未用于当前曲线校正</small>
            </td>
          </tr>
        })}</tbody></table></div>
      </details>
    </>}
  </section>
}
