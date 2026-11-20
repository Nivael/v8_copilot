import type {JingjiDividendFollowup} from './stRegimeTypes'
export function STJingjiDividendFollowup({data}:{data?:JingjiDividendFollowup|null}){
 if(!data)return null
 const c=data.calculation
 return <section id="st-jingji-dividend-followup" aria-label="京机公式与精度续核" style={{scrollMarginTop:80}}>
  <h2>{data.title}</h2><p>{data.answer}</p>
  <h3>最终价格相同，原输入却不同</h3>
  <table className="regime-table"><caption>换股价从14.50元起算，均按两位小数四舍五入</caption><thead><tr><th>用于演示的每股金额</th><th>取整前换股价</th><th>取整后换股价</th></tr></thead><tbody><tr><th>公告总股本参考额 {c.reported_per_share}元</th><td>{c.eb_using_reported_reference_exact}元</td><td>{c.eb_using_reported_reference_rounded}元</td></tr><tr><th>实派每股现金 {c.eligible_per_share_cash}元</th><td>{c.eb_using_eligible_cash_exact}元</td><td>{c.eb_using_eligible_cash_rounded}元</td></tr></tbody></table>
  <p>第二行是本轮敏感性对照，不是公司另行公布的换股公式。两条路径取整相同，说明最终两位价格无法区分这两个输入。</p>
  <h3>新增公告改变了什么？</h3><p>{data.what_changed}</p><p>{data.interpretation}</p>
  <details><summary>展开原式分母、总股本与截取精度</summary>
   <table className="regime-table"><caption>同用公告印刷现金总额20,348,617.67元，分别代入两种分母</caption><thead><tr><th>核查对象</th><th>分母</th><th>计算／截取结果</th><th>与公告结果关系</th></tr></thead><tbody><tr><th>原印刷每10股公式</th><td>616,624,778股</td><td>{c.printed_ten_truncated_6}元（6位截取）</td><td>不等于{c.reported_ten}元</td></tr><tr><th>用总股本计算每10股</th><td>622,874,778股</td><td>{c.total_ten_truncated_6}元（6位截取）</td><td>对应公告结果，未替原式改分母</td></tr><tr><th>总股本折算每股参考额</th><td>622,874,778股</td><td>{c.total_per_share_truncated_7}元（7位截取）</td><td>对应公告另一处每股参考额</td></tr></tbody></table><p>{data.precision_boundary}</p>
  </details>
  <h3>什么证据能关闭冲突？</h3><ul>{data.watch.map(w=><li key={w}>{w}</li>)}</ul>
  <details><summary>查看两份发行人原件与页码</summary>{data.sources.map(s=><p key={s.announcement_id}>{s.title}：{s.selected_pages.map(n=><span key={n}><a href={`${s.url}#page=${n}`} target="_blank" rel="noreferrer">第{n}页</a>{' '}</span>)}</p>)}<p>本轮新增1份4页、复用1份6页，核3个关键图像页，无新行情请求。后续引用是同一事项重述，不计为新的独立验证，也不认证持有人实际换股。</p></details>
 </section>
}
