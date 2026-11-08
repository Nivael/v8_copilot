import type {RegimeComparison,STRegimeData} from './stRegimeTypes'

export type StorySection={id:string;heading:string;paragraphs:string[];evidence:'规则前后'|'大盘联动'|'整批个股';sourceIndices:number[]}
export type RegimeStory={title:string;deck:string;period:string;lead:string[];sections:StorySection[];ending:string;coverage:string}
const change=(value:number|null)=>value==null?'尚无法计算':`${value>=0?'上涨':'下跌'}${Math.abs(value).toFixed(2)}%`
const approx=(value:number|null)=>value==null?'尚无法计算':`${value>=0?'上涨':'下跌'}约${Math.abs(value).toFixed(1)}%`
const dateLabel=(value:string)=>{const [,month,day]=value.split('-');return `${Number(month)}月${Number(day)}日`}

/** An editorial projection of the same verified snapshot, never fresh reporting. */
export function buildRegimeStory(data:STRegimeData,comparison:RegimeComparison):RegimeStory{
  const {before,after,fixed_after:fixed}=comparison
  const advances=fixed.rows.filter(row=>row.return_pct!=null&&row.return_pct>0).length
  const nonAdvances=fixed.covered-advances
  const flat=after.reference_change_pct!=null&&Math.abs(after.reference_change_pct)<=2
  const falling=after.reference_change_pct!=null&&after.reference_change_pct< -2
  const minority=fixed.positive_pct!=null&&fixed.positive_pct<50
  const title=falling?'涨跌幅放开，ST仍未走出下跌':flat&&minority?'ST回到原点，多数样本仍未上涨':flat?'ST接近持平，个股之间仍有明显差距':'ST整体参考上涨，个股的表现如何？'
  const deck=falling?'交易空间扩大之后，市场并未迎来一轮普涨。把ST放回同期大盘，再逐只检视，才能分清整批行情与个股处境。':flat?'整批行情接近持平，个股的表现却相去甚远。大盘的压力、规则的变化与公司的进展，需要放在一起读。':'整批参考的方向只是故事的一部分。上涨覆盖多少股票、市场环境怎样变化，决定了这轮行情该如何理解。'
  const lead=[
    `${dateLabel(after.through)}收盘时，主板ST等权参考较新规生效前的7月3日${change(after.reference_change_pct)}。${flat?'单看这一结果，这段行情已接近回到起点。':falling?'更大的单日涨跌空间，没有伴随这一观察窗口内的普遍上涨。':'这一结果显示观察窗口内的整批参考走高。'}`,
    fixed.covered>0?`${falling?'逐只查看7月3日的固定名单，调整的覆盖面也很清楚。':'但把7月3日的名单固定下来，故事就有了另一面。'}在能比较起止价格的${fixed.covered}只股票中，${advances}只上涨，${nonAdvances}只没有上涨。另有${fixed.missing}只缺价或复权待核，不能据此判断其结果。${minority?'这组可比样本中，上涨仍未覆盖多数股票。':'整批参考与个股表现仍须分别衡量，不能由平均数推断每家公司的处境。'}`:'固定名单目前缺少可比端点，暂时不能判断有多少股票跟上了整批行情。',
  ]
  const chronology=[`7月6日，沪深主板ST和*ST股票的日涨跌幅限制由5%放宽至10%。这项安排已在4月24日公布。它改变了单日价格能够到达的范围，公司的经营和重整进展仍需另查。`,
    `${before.reference_change_pct!=null&&before.reference_change_pct<0?'调整在新规生效前就已出现。':'先看新规生效前的行情。'}此前${before.days}个交易日，主板ST等权参考${change(before.reference_change_pct)}，同期中证全指${change(before.market_change_pct)}。${before.reference_change_pct!=null&&before.market_change_pct!=null&&before.reference_change_pct<0&&before.reference_change_pct<before.market_change_pct?'ST当时的跌幅已经大于大盘，不能把整段压力都归到规则落地之后。':'规则落地之前的市场环境，也应计入这段行情的背景。'}`]
  const first20=data.comparisons.find(c=>c.key==='20')
  if(first20&&after.days>20&&first20.after.start===after.start&&first20.after.through<=after.through){
    chronology.push(`${first20.after.reference_change_pct!=null&&first20.after.reference_change_pct<0?'开局仍偏弱。':'先看开局这一段。'}新规生效后的前20个交易日，截至${dateLabel(first20.after.through)}，ST等权参考${change(first20.after.reference_change_pct)}。到${dateLabel(after.through)}，累计变化变为${change(after.reference_change_pct)}。${after.reference_change_pct!=null&&first20.after.reference_change_pct!=null&&after.reference_change_pct>first20.after.reference_change_pct?(first20.after.reference_change_pct<0?'其间出现了修复，但修复后的整体位置，并不能说明个股都已收复失地。':'后段表现好于开局，但整批参考的变化，不能说明每只股票的表现。'):'后段走势仍要与开局分别观察，不能只用一个终点概括过程。'}`)
  }else chronology.push(`到${dateLabel(after.through)}，这一${after.days}个交易日窗口内，ST等权参考${change(after.reference_change_pct)}，同期中证全指${change(after.market_change_pct)}，代表小盘风格的中证2000${change(after.small_cap_change_pct)}。比较窗口相同，才能看清ST究竟是跟随市场，还是走出了相对不同的路径。`)
  const up=after.conditions.find(c=>c.key==='up'),down=after.conditions.find(c=>c.key==='down')
  const market=[`同期大盘${change(after.market_change_pct)}，而ST等权参考${change(after.reference_change_pct)}。${after.reference_change_pct!=null&&after.market_change_pct!=null&&after.reference_change_pct>after.market_change_pct?(after.market_change_pct<0?'相对大盘，ST这段时间更抗跌；但“跌得更少”与“多数股票上涨”是两件需要分别验证的事。':'ST的同窗表现好于大盘，但整批参考和个股上涨覆盖面仍需分别观察。'):'两条路径的差异说明，市场背景和ST自身表现需要同时保留，不能互相替代。'}`]
  if(up&&down)market.push(`把每天拆开看：大盘上涨的${up.days}天里，ST等权参考日均${approx(up.st_mean_pct)}；大盘下跌的${down.days}天里，ST日均${approx(down.st_mean_pct)}。这让市场环境的影响更容易看见，但只能说明同日联动，尚不能算出“大盘造成了多少跌幅”。`)
  market.push('公司公告、摘帽与退出名单、小盘风格变化，都可能同时影响价格。要解释某只股票的表现，还需要把它自己的事件接回来。')
  const distribution=fixed.covered===0?['固定名单目前没有可比的起止价格，收益中位数和分布仍待核验。']: [`固定名单里，可比股票的区间收益中位数为${fixed.median_pct==null?'待核':`${fixed.median_pct>=0?'+':''}${fixed.median_pct.toFixed(2)}%`}，也就是把这组股票按涨跌排列后，排在中间的位置。较弱一端${approx(fixed.p10_pct)}，较强一端${approx(fixed.p90_pct)}，这里分别取收益分布的10%和90%位置。`]
  const cases=['603398','002514'].map(symbol=>fixed.rows.find(row=>row.symbol===symbol&&row.return_pct!=null)).filter(row=>row!=null)
  if(cases.length)distribution.push(`例如，同一窗口内，${cases.map(row=>`${row.name}${change(row.return_pct)}`).join('，')}。这些个案不能定义整个ST群体，却具体说明了平均数会遮住怎样的差异。`)
  distribution.push(`这也留下一个重要边界：固定名单共有${fixed.total}只，本篇能比较${fixed.covered}只。缺失者仍在明细中，名单移出也不直接当作摘帽成功。把这一部分补齐后，关于上涨覆盖面和分布的判断还要再检验。`)
  const lessons=['这次复盘更值得保留的，是一套看行情的顺序：先看整批走势，再问有多少股票跟上，最后把个股的公司进展与市场环境对照。板块走强，不能替代对某家公司的判断。',
    '新旧规则之间，也要用实际涨跌幅说话。单日价格范围放宽后，同样的“一个跌停”意味着不同的跌幅，旧有连板经验需要重新检验。整批路径起伏更大，也不自动意味着股票之间的差距同步扩大。']
  const sections:StorySection[]=[{id:'chronology',heading:'调整先于新规，修复出现在后段',paragraphs:chronology,evidence:'规则前后',sourceIndices:[0,2]},
    {id:'market',heading:'大盘是背景，个股还要找自己的解释',paragraphs:market,evidence:'大盘联动',sourceIndices:[5]},
    {id:'distribution',heading:'平均数之外，还有没有跟上的股票',paragraphs:distribution,evidence:'整批个股',sourceIndices:[3,4]},
    {id:'learning',heading:'把行情的判断，带回下一次研究',paragraphs:lessons,evidence:'规则前后',sourceIndices:[]}]
  // A declining/new snapshot must not inherit a recovery headline from the old data.
  if(!first20||after.days<=20||after.reference_change_pct==null||first20.after.reference_change_pct==null||after.reference_change_pct<=first20.after.reference_change_pct)sections[0].heading=before.reference_change_pct!=null&&before.reference_change_pct<0?'规则落地之前，调整已经开始':'新规前后，市场经历了什么'
  else if(before.reference_change_pct!=null&&before.reference_change_pct>=0)sections[0].heading='新规落地之后，行情怎样演变'
  if(first20?.after.reference_change_pct!=null&&first20.after.reference_change_pct>=0)sections[0].heading='从开局到后段，市场怎样走到这里'
  return {title,deck,period:`${dateLabel(after.start)}至${dateLabel(after.through)} · 规则后${after.days}个交易日`,lead,sections,
    ending:`本篇只讨论已经覆盖的历史窗口。完整逐日ST资料截至${data.through}，不代表截至今天的行情；后续数据和退出样本补齐后，判断仍可能改变。`,
    coverage:`历史观察 · 完整逐日资料截至 ${data.through}`}
}
