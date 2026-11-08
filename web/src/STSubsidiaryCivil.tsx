import type {RegimeSubsidiaryCivil} from './stRegimeTypes'
const pct=(n:number|null)=>n==null?'待核':`${n>0?'+':''}${n.toFixed(2)}%`
export function STSubsidiaryCivil({data:s}:{data:RegimeSubsidiaryCivil}){
 return <section aria-label="英腾另案保全更新">
  <p><strong>子公司另案，现已核到哪一步？</strong>{s.answer}</p>
  <details><summary>分案看解除范围、收件日期与原告请求</summary>
   <p>{s.what_changed}</p>
   <div className="regime-scroll"><table className="regime-table"><thead><tr><th>主体与法院</th><th>案号</th><th>目录披露限制</th><th>收到解除文件</th><th>目录披露解除</th></tr></thead><tbody>{s.procedure_rows.map(r=><tr key={r.case_id}><th>{r.entity}<small>{r.court}</small></th><td>{r.case_id}<small>{r.stage}</small></td><td>{r.first_published_on}</td><td>{r.release_received_on}</td><td>{r.release_published_on}</td></tr>)}</tbody></table></div>
   <p>表中披露日按官方目录，收件日另列，不认证精确最早披露时刻。两案均只核到相应保全措施解除，未由此取得基础纠纷实体判决或个人刑事结果。首次收件日及实际受限持续期未完整核到，不拿公开日间隔代替。</p>
   <h5>请求与法院裁定，分别列</h5>
   <div className="regime-scroll"><table className="regime-table"><thead><tr><th>原告申请</th><th>摘录裁定是否单列</th></tr></thead><tbody>{s.requests.map(r=><tr key={r.key}><th>{r.text}</th><td>{s.order_items.some(x=>x.key===r.key)?'有对应裁定项':'未单独列出；不据此判断获准召开'}</td></tr>)}</tbody></table></div>
   <p>{s.request_order_note}</p><p>{s.first_published_on}原件说将提交复议，不当作已提交；“复议期间不停止执行”另保留。该原件当时未开庭、无实体判决，不外推到11月仍未审结。</p><p>{s.source_wording_note}</p>
   {s.price_comparison&&<><h5>价格反应，不能只按公告好坏解释</h5>{s.price_comparison.observations.map(o=><p key={o.published_on}>{o.published_on}公告后{s.price_comparison?.window_days}日，{o.anchor} → {o.through}：个股{pct(o.stock_pct)}，大盘{pct(o.market_pct)}，ST参考{pct(o.st_pct)}。</p>)}<p>两个20日窗口重叠{s.price_comparison.overlap_market_days}个交易日，不是两次独立验证。完整{s.price_comparison.full_window.market_days}日窗口（{s.price_comparison.full_window.anchor} → {s.price_comparison.full_window.through}）股价仍为{pct(s.price_comparison.full_window.stock_pct)}；短期反弹与全段回撤并存，不能由此认定公告净贡献。</p></>}
   {s.facts.map((f,n)=><div key={`${f.source.announcement_id}-${n}`}><p>{f.published_on}公开：{f.text}</p><a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title} · 第{f.source.page}页 ↗</a></div>)}
   <p className="reading-caption">{s.boundary}</p>
  </details>
 </section>
}
