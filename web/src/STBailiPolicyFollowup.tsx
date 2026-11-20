import type {BailiPolicyFollowup} from './stRegimeTypes'
export function STBailiPolicyFollowup({data}:{data?:BailiPolicyFollowup|null}){
 if(!data)return null
 return <section aria-label="百利政策与更正续核">
  <h3>{data.title}</h3><p>{data.answer}</p>
  <details><summary>按日期看：政策、半年报与更正</summary>
   <table><caption>政策落款、网页发布、批准报送、报告披露与生效日期分别看</caption><thead><tr><th>日期</th><th>事项及依据</th></tr></thead><tbody>{data.timeline.map(t=>{const source=data.source_refs.find(s=>s.key===t.source);return <tr key={t.date}><td>{t.date}</td><td>{t.event}{source&&<> · <a href={source.url+(t.page?`#page=${t.page}`:'')} target="_blank" rel="noreferrer">{t.page?`原件第${t.page}页`:'官方原文'}</a></>}</td></tr>})}</tbody></table>
   <p><strong>仍需解释：</strong>{data.conflict}</p>
  </details>
  <details><summary>消费税与递延所得税资产，怎样联系起来？</summary><p>{data.mechanism}</p><p>{data.accounting}</p><p>这次调整不是当期已缴税款或现金流出的证明，也不能仅凭准则原文判定公司的会计处理恰当或违规。</p><ul>{data.source_refs.filter(s=>s.key==='cas18'||s.key==='cas28').map(s=><li key={s.key}><a href={s.url} target="_blank" rel="noreferrer">{s.key==='cas18'?'所得税准则：第十五、二十条':'政策、估计变更与差错更正准则：第八、十一条'}</a></li>)}</ul></details>
  <p><strong>接下来真正需要的材料：</strong></p><ul>{data.watch.map(w=><li key={w}>{w}</li>)}</ul>
 </section>
}
