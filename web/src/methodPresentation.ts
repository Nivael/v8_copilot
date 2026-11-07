import type {MethodReading} from './readingTypes'
const titles:Record<string,string>={
  'EXP-D891F04538BD671515FF':'招募结束后没消息，先查进度卡在哪',
  'EXP-E6A0A3C110D74FE7A6DF':'已经确认的进展，和下一步预测要分开',
  'EXP-3EF25D62ECE7A4453211':'比较ST时，用当时的名单和同一截止日',
  'EXP-6035511EF7BD09AED0B3':'谁受了处分、发生在何时，要分别看',
  'EXP-EF92B88B66DCC4ECCB68':'统计先例时，别只看已经成功的公司',
  'EXP-74E679332AEE94ADC122':'同一天的关联公告，要连起来看',
  'EXP-F0A962407D4FF75D3ACE':'比较公司前，先统一对象和问题',
  'EXP-9192C8C1A3DBE188C75F':'看事件先例时，接上当时的逐日股价',
  'EXP-0C78ABF99736BAB325B2':'没查到，不能直接当成没有',
  'EXP-D9A1B99AA6A1DF488296':'先给判断，依据展开再看',
}
export function methodTitle(method:MethodReading){return titles[method.id]||method.title}
