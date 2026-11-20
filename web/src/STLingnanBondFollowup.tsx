import audit from './lingnanBondFollowup.json'
import type {LingnanExitFollowup} from './STLingnanExitFollowup'
export function STLingnanBondFollowup({data}:{data?:LingnanExitFollowup|null}){
 if(!data)return null
 const bound=audit.sources.every(s=>data.source_refs.some(r=>r.announcement_id===s.announcement_id&&r.url===s.url&&r.published_on===s.announcement_date))
 if(!bound)return <p role="status">债券补核尚未与当前证据包对应，暂不显示结论。</p>
 const source=(id:string)=>audit.sources.find(s=>s.announcement_id===id)!
 return <section id="st-lingnan-bond-followup" className="regime-topic-body" aria-label="岭南债券判决与质押补核">
  <p className="reading-kicker">已保存原件补核 · 事实以2026年11月3日报告披露时为准</p>
  <h3>有判决、有质押，就能当作已经兑付吗？</h3>
  <p><strong>还不能。报告当时一审尚未生效，质押变现和共管安排也有未完成事项。</strong>这是债券持有人追偿事项，不能当上市公司收到回款或现金已经付清的证明。</p>
  <p>9月10日是一审第二次庭审，10月23日是受托管理人收到判决书，11月3日是这份季度受托报告的披露日，不当作判决作出日或最早公开日。季度报告包含期后进展，不能把10月判决倒填为9月末已知。</p>
  {audit.observations.map(o=><article key={o.title}><h4>{o.title}</h4><p>{o.fact}</p><p><strong>怎样更新判断：</strong>{o.meaning}</p><details><summary>核对这项原件依据</summary><p>{source(o.source).title} · 披露{audit.report_date}</p>{o.pages.map(n=><p key={n}><a href={source(o.source).url+'#page='+n} target="_blank" rel="noreferrer">PDF物理第{n}页 ↗</a></p>)}</details></article>)}
  <details><summary>本轮补上什么，哪些仍未核实？</summary><p>两份已保存报告共{audit.total_pages}页，本轮核对{audit.reviewed_pages}个关键图像页，文件摘要及逐页提取与旧存件一致；新下载{audit.new_downloads}份。受托报告是受托管理人的披露，不是法院判决原件；其重要声明也说明未对引述内容独立验证。</p><p>能补上报告时的一审阶段、担保价值重叠与未完成安排。判决具体金额及判项、后来生效或上诉结果、实际执行和兑付仍需对应原件；不能把报告时状态当11月19日或今天的完整司法状态，也不改变股票最终退出仍未核的缺口。</p><p>两份报告同属一家发行人，部分重述旧事实，不增加独立案例或方法验证次数。</p>{audit.sources.map(s=><p key={s.announcement_id}>{s.announcement_id} · 保存SHA256：<code>{s.sha256}</code></p>)}</details>
 </section>
}
