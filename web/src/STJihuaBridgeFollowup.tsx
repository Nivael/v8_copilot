import type {JihuaBridgeFollowup} from './stRegimeTypes'
const yuan=(s:string)=>Number(s).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})+'元'
const names:Record<string,string>={revenue:'营业收入',parent_profit:'归母净利润',recurring_profit:'扣非净利润'}
export function STJihuaBridgeFollowup({data}:{data?:JihuaBridgeFollowup|null}){
 if(!data)return null
 return <section id="st-jihua-bridge-followup" aria-label="际华季度衔接续核" style={{scrollMarginTop:80}}>
  <h2>{data.title}</h2><p>{data.answer}</p>
  <h3>先看经营判断：归母为正，扣非仍亏</h3><p>{data.operating}</p>
  <h3>差额已找到线索，为什么还不算核清？</h3><p>{data.interpretation}</p>
  <p>归母差额38,852.53元，与报告披露的同控合并前利润数值一致；扣非差额38,952.53元则多100元。这是待解释的对应关系，完整调节仍未确认。</p>
  <details><summary>展开三项原数与衔接计算</summary>
   <table className="regime-table"><caption>单位：元。“累计减原半年”与直接单季分别列示</caption><thead><tr><th>指标</th><th>原半年</th><th>前三季累计</th><th>直接第三季度</th><th>累计减原半年</th><th>差额</th></tr></thead><tbody>{data.rows.map(r=><tr key={r.metric}><th>{names[r.metric]}</th><td>{yuan(r.h1_original)}</td><td>{yuan(r.nine_month_reported)}</td><td>{yuan(r.q3_direct)}</td><td>{yuan(r.nine_minus_original_h1)}</td><td>{yuan(r.difference)}</td></tr>)}</tbody></table>
   <p>差额＝前三季累计－原半年－直接第三季度。差额有待调节，不能用差额推算值替换报告直接披露的单季数。</p>
  </details>
  <details><summary>100元差异，怎样接回非经常性损益？</summary>
   <p>原半年非经常性损益{yuan(data.nonrec_bridge.h1_original)}，前三季{yuan(data.nonrec_bridge.nine_month_reported)}；相减得到{yuan(data.nonrec_bridge.derived_q3)}，比直接单季{yuan(data.nonrec_bridge.q3_direct)}少100元。</p>
   <p>这与归母、扣非两项衔接差额之差一致，属于同一组算术关系，不是另一次独立验证，也没有证明原因。</p>
  </details>
  <details><summary>倒推可比半年值：只能当核查线索</summary><p>{data.boundary}</p><ul>{data.rows.map(r=><li key={r.metric}>{names[r.metric]}：{yuan(r.implied_comparable_h1)}（前三季减直接单季所得，非披露值）</li>)}</ul></details>
  <h3>什么证据能关闭差异？</h3><ul>{data.watch.map(w=><li key={w}>{w}</li>)}</ul>
  <p><strong>可保留的核查方法：</strong>{data.experience}</p>
  <details><summary>查看两份原报告及页码</summary>{data.source_refs.map(s=><p key={s.announcement_id}>{s.title}：{s.selected_pages.map(n=><span key={n}><a href={`${s.url}#page=${n}`} target="_blank" rel="noreferrer">第{n}页</a>{' '}</span>)}</p>)}<p>本轮复用原件，核6个关键图像页；无新增行情，未将这次核查晋级为已验证通用经验。</p></details>
 </section>
}
