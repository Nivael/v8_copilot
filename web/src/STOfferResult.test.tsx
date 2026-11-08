import {render,screen,fireEvent} from '@testing-library/react'
import {describe,it,expect} from 'vitest'
import {STOfferResult} from './STHaltStages'
import type {RegimeOfferResult} from './stRegimeTypes'
const result={planned_shares:91786000,accepted_shares:418699,accounts:42,price_per_share:'1.25',planned_reported_pct:'6.00',accepted_reported_pct:'0.0274',purpose:'不以取得公司控制权为目的',settlement_status:'arranged_not_confirmed',completion_receipt:null,planned_consideration:'114732500.00',accepted_price_consideration:'523373.75',accepted_to_planned_pct:.4561687,halt_on:'2026-08-27',resume_on:'2026-08-28',halt_market_days:1,all_halt_days_confirmed:true,resume_has_trade:true,facts:[{published_on:'2026-08-28',text:'清算过户将于近日办理',source:{title:'清算公告',url:'https://example.test',page:1,sha256:'a',announcement_id:'a'}}]} as RegimeOfferResult
describe('offer result',()=>{
 it('separates target, acceptance, control purpose and unconfirmed settlement',()=>{render(<STOfferResult result={result}/>);expect(screen.getByText(/418,699股/)).toBeVisible();expect(screen.getByText(/0.456%/)).toBeVisible();expect(screen.getByText(/本轮没有完成回执/)).toBeVisible();expect(screen.getByText(/控制权目标失败/)).toBeVisible();expect(screen.getByText(/523,373.75元/)).not.toBeVisible();fireEvent.click(screen.getByText('核结果、清算原件与计算'));expect(screen.getByText(/523,373.75元/)).toBeVisible();expect(screen.getByText(/不当作已付款/)).toBeVisible()})
})
