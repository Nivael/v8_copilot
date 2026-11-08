import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {describe,it,expect,afterEach} from 'vitest'
import {STOfferResult} from './STHaltStages'
import type {RegimeOfferResult} from './stRegimeTypes'
const result={planned_shares:91786000,accepted_shares:418699,accounts:42,price_per_share:'1.25',planned_reported_pct:'6.00',accepted_reported_pct:'0.0274',purpose:'不以取得公司控制权为目的',settlement_status:'arranged_not_confirmed',completion_receipt:null,planned_consideration:'114732500.00',accepted_price_consideration:'523373.75',accepted_to_planned_pct:.4561687,halt_on:'2026-08-27',resume_on:'2026-08-28',halt_market_days:1,all_halt_days_confirmed:true,resume_has_trade:true,facts:[{published_on:'2026-08-28',text:'清算过户将于近日办理',source:{title:'清算公告',url:'https://example.test',page:1,sha256:'a',announcement_id:'a'}}]} as RegimeOfferResult
afterEach(cleanup)
describe('offer result',()=>{
 it('separates target, acceptance, control purpose and unconfirmed settlement',()=>{render(<STOfferResult result={result}/>);expect(screen.getByText(/418,699股/)).toBeVisible();expect(screen.getByText(/0.456%/)).toBeVisible();expect(screen.getByText(/本轮没有完成回执/)).toBeVisible();expect(screen.getByText(/控制权目标失败/)).toBeVisible();expect(screen.getByText(/523,373.75元/)).not.toBeVisible();fireEvent.click(screen.getByText('核结果、清算原件与计算'));expect(screen.getByText(/523,373.75元/)).toBeVisible();expect(screen.getByText(/不当作已付款/)).toBeVisible()})
})

it('updates confirmed completion while preserving the earlier evidence stage',()=>{
 const source={announcement_id:'new',title:'交割完成公告',page:1,url:'https://example.test/complete',sha256:'new'}
 const completed:RegimeOfferResult={...result,settlement_status:'confirmed_complete',completion_receipt:{published_on:'2026-09-02',completed_by:'2026-09-02',exact_completion_on:null,final_shares:418699,reported_pct:'0.0274',settlement_complete:true,control_changed:false,source},facts:[...result.facts,{published_on:'2026-09-02',text:'清算过户手续已办理完毕',source}],judgment_history:[{as_of:'2026-08-28',answer:'当时只见办理安排',what_changed:'',settlement_status:'arranged_not_confirmed',completion_receipt:null,scope:'不倒填当时'}]}
 render(<STOfferResult result={completed}/>);expect(screen.getByText(/截至披露日清算过户已办理完毕/)).toBeVisible();expect(screen.queryByText(/本轮没有完成回执/)).not.toBeInTheDocument();expect(screen.getByText(/后续2026-09-02公告已确认持有/)).toBeVisible();fireEvent.click(screen.getByText('核结果、清算原件与计算'));expect(screen.getByText(/当时只见办理安排/)).toBeVisible();expect(screen.getByText(/不倒填早期已知信息/)).toBeVisible()
})
