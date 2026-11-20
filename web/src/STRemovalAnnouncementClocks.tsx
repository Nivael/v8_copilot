import {removalAnnouncementClocks,type RemovalClocksInput} from './removalAnnouncementClocks'
const pct=(n:number|null)=>n===null?'报价待核，不认证':`${n.toFixed(2)}%`
export function STRemovalAnnouncementClocks({input}:{input:RemovalClocksInput|null}){
 const board=input?removalAnnouncementClocks(input):null
 if(!board)return <p role="status">窗口与公告依据尚未齐备，暂不连接这组判断。</p>
 const sitong=board.cases[0].windows
 const md=(date:string)=>`${Number(date.slice(5,7))}月${Number(date.slice(8,10))}日`
 const source=(id:string)=>board.sources.find(s=>s.announcement_id===id)!
 const link=(id:string)=>{const s=source(id);return <a href={s.url} target="_blank" rel="noreferrer">{s.published_on} · {s.title}</a>}
 return <section id="st-removal-announcement-clocks" aria-label="摘帽、公告与不同价格窗口" style={{scrollMarginTop:80}}><h2>四通20日上涨，为什么最新又是下跌？</h2><p>两个答案使用了不同的终点：从10月20日收盘到第20个交易日{md(sitong[0].through)}，四通变化{pct(sitong[0].certified)}；延长到{md(board.through)}，同一起点变为{pct(sitong[1].certified)}。若从10月27日收盘、按正式披露日向前取一个交易日收盘为锚点，到{md(board.through)}则为{pct(sitong[2].certified)}。它们可以同时成立，不能互相替代。</p><p>四通与绝味同在10月20日摘帽，但窗口内公告不同，绝味起点还有报价差异。先核窗口和当时已知信息，再讨论解释。</p>
 <table className="regime-table"><caption>同日摘帽，两家公司与三个观察窗口</caption><thead><tr><th>公司</th><th>窗口</th><th>日期</th><th>已核个股变化</th><th>同期大盘</th></tr></thead><tbody>{board.cases.flatMap(c=>c.windows.map(w=><tr key={c.symbol+w.label}><th>{c.name}</th><td>{w.label}{w.observed!==null?`（已观察${w.observed}日，${w.observed<20?'20日未满':'20日已满'}）`:''}</td><td>{w.anchor} → {w.through}</td><td>{pct(w.certified)}</td><td>{pct(w.market)}</td></tr>))}</tbody></table>
 <h3>这些窗口里，分别发生了什么？</h3><article><h4>四通：先摘帽，后更正；更正不等新增收入</h4><ol><li>{link('1225608268')}：公告安排10月20日起撤销警示。</li><li>{link('1225629182')}：更正历史比较数，当期半年收入没有因此增加；它晚于摘帽，不能倒过来解释摘帽决定。</li><li>{link('1225629255')}：同日还有三季报，不能将整段价格变化只归给一份更正公告。</li></ol></article>
 <article><h4>绝味：同窗公告重合，后来消息不能倒填</h4><ol><li>{link('1225609996')}，同日另有{link('1225610029')}。撤销警示与权益分派需分开看。</li><li>{link('1225630481')}：季报经营期间是7至9月，不能称为10月摘帽后的经营效果。</li><li>{link('1225676244')}：这份交易终止公告晚于11月17日的20日窗口终点，不能把这份后来披露的公告当成此前已知的新信息；若主张提前反应，仍需更早的公开证据。截至{md(board.through)}的观察才包含这个新信息。</li></ol></article>
 <p>日期采用已核正式披露日，未认证首次公开分钟。这里保留的是时间顺序与同期价格，不识别单项公告净影响。同日摘帽不代表同一风险机制，两个重叠时段案例也不算两次独立制度试验。</p><details><summary>核对窗口原值与剩余限制</summary>{board.cases.map(c=><article key={c.symbol}><h4>{c.name} · {c.symbol}</h4>{c.windows.map(w=><p key={w.label}>{w.anchor} → {w.through}：主源{pct(w.primary)}，跨源{pct(w.cross)}；{w.certified===null?'两种数值都保留，不能择一认证。':'端点已核。'}</p>)}</article>)}<p>未满的观察窗不当作完整20日；40日窗口单独核验。公告链接、原观察时间和文件摘要沿用既有复盘，不新增独立验证或方法晋级。</p></details></section>
}
