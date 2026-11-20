import {Link,useInRouterContext} from 'react-router-dom'
import update from './bailiReceiptUpdate.json'
export function STBailiReceiptUpdate(){
 const inRouter=useInRouterContext()
 const recordUrl='/runs#research-RUN-AF094ACF6809426B9E97B82B'
 return <aside className="regime-boundary" aria-label="百利赠与收款补证更正">
  <h5>补证更正：累计已收7500万元，旧稿漏选了11月3日公告</h5>
  <p><strong>公司披露，截至2026年10月30日，协议项下第一笔、第二笔赠与款合计7500万元；各赠与人已按期履行首期付款义务。</strong>原稿只列三季报3900万元，遗漏了这份已在保存目录中的后续公告，当前判断据此修正。</p>
  <p>协议总额1.3亿元，剩余算术差额改为5500万元，累计收款占协议额{update.received_ratio_pct}%。这是资本支持的进一步落实，不是全部款项付清、经营利润或法院已受理。该公告披露时仍未获法院裁定受理；其后司法状态另核。</p>
  <details><summary>新原件、旧口径与仍未关闭的缺口</summary>
   <p>3900万元是前三季报吸收投资现金流项目，7500万元是公司后续披露的协议累计收款。两者不能相加成1.14亿元，也不能仅用相减的3600万元拆成某一笔或精确归入10月新增收款。</p>
   <p>现在可以依据公司公告确认“首期按期履行”的披露，不再笼统写成首期尚未确认；但第一笔、第二笔各自金额、付款人和精确到账日仍未分列。5500万元也不直接认定为逾期欠款，后续须按协议及公司通知继续核收款。</p>
   <p>依据为公司2026-111号收款公告，不是独立银行流水验真。4页已全部看图，正式披露2026-11-03，事实截至2026-10-30，原件2026-11-20补取。保存目录原有41条、两页完整，漏的是选源环节，不能说接口此前未返回这份公告。</p>
   {[1,2,3,4].map(n=><p key={n}><a href={`${update.source.url}#page=${n}`} target="_blank" rel="noreferrer">{update.source.announcement_id} · 收款公告物理第{n}页 ↗</a></p>)}
   <p>保存SHA256：<code>{update.source.sha256}</code>。</p><p>{inRouter?<Link to={recordUrl}>查看本次补证研究与验证记录 →</Link>:<a href={recordUrl}>查看本次补证研究与验证记录 →</a>}</p>
  </details>
 </aside>
}
