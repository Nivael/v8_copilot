import type {MethodReading} from './readingTypes'
const titles:Record<string,string>={
  'EXP-D891F04538BD671515FF':'招募结束后没消息，先查进度卡在哪',
  'EXP-E6A0A3C110D74FE7A6DF':'按官方进展确认阶段，按条件观察下一步',
  'EXP-3EF25D62ECE7A4453211':'比较ST时，用当时的名单和同一截止日',
  'EXP-6035511EF7BD09AED0B3':'谁受了处分、发生在何时，要分别看',
  'EXP-EF92B88B66DCC4ECCB68':'统计成功、失败和未完成的案例',
  'EXP-74E679332AEE94ADC122':'同一天的关联公告，要连起来看',
  'EXP-F0A962407D4FF75D3ACE':'比较公司前，先统一对象和问题',
  'EXP-9192C8C1A3DBE188C75F':'看事件先例时，接上当时的逐日股价',
  'EXP-0C78ABF99736BAB325B2':'查公司公告，也查管理人与重整平台',
  'EXP-D9A1B99AA6A1DF488296':'先给判断，依据展开再看',
}
export function methodTitle(method:MethodReading){return titles[method.id]||method.title}

const summaries:Record<string,string>={
  'EXP-9700CBEDEC49302CAE87':'并列同主体、同指标、同单位和同期间的报表数值及来源，复算比较栏与同比。发现差异后追查原因，解释清楚再做精确估值。',
  'EXP-D595709437D5371F7028':'从个案提炼机制变化：按发生日、披露日、主体和程序阶段追踪新增事实，再对照同期大盘、ST和个股价格。同一事实的重复披露合并观察。',
  'EXP-67506A572D4A105A5776':'核对交易规则的适用市场、板块、投资者和生效时间，再查单笔申报、当日累计、账户合并与例外条款。价格原因和企稳判断另查市场证据。',
  'EXP-D891F04538BD671515FF':'招募截止后，逐项追踪资格审查、保证金、尽调、方案提交、财务更正、遴选确认和投资协议。按公开期限及实际进度判断卡点。',
  'EXP-E6A0A3C110D74FE7A6DF':'用已发生的官方节点确认当前阶段；对下一节点列出达成条件、阻力和待观察事项。',
  'EXP-3EF25D62ECE7A4453211':'按当时ST状态构造成员名单，把公告、价格和市值统一到共同截止日后比较。',
  'EXP-6035511EF7BD09AED0B3':'分别核对处分类型、受罚主体和发生时间，再追踪处分之后的资本运作。',
  'EXP-EF92B88B66DCC4ECCB68':'统计先例时保留成功、失败、未完成和退市四类结果，并记录各案例的观察截止日。',
  'EXP-74E679332AEE94ADC122':'按回复对象、前置问题和结论关系，把同日公告及附件连成一组依据。',
  'EXP-F0A962407D4FF75D3ACE':'先确认上市公司与关联主体，列明共同截止日及各自最新日期，再比较程序阶段等具体维度。',
  'EXP-9192C8C1A3DBE188C75F':'研究节点前的连续价格状态时，连接事件截止日、主体范围、ST区间与逐交易日价格。',
  'EXP-0C78ABF99736BAB325B2':'公司公告缺少记录时，继续查管理人、破产重整平台及其他披露渠道。',
  'EXP-D9A1B99AA6A1DF488296':'先给当前判断和实质差异，再展开事实、逻辑与证据；日期、比例及计算口径放在对应依据中。',
}
export function methodSummary(method:MethodReading){return summaries[method.id]||method.summary}
