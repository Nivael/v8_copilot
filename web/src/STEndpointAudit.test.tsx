import {render,screen,fireEvent} from '@testing-library/react'
import {describe,it,expect} from 'vitest'
import {STEndpointAudit} from './STEndpointAudit'
import type {RegimeComparison} from './stRegimeTypes'
const c={fixed_after:{anchor:'2026-07-03',through:'2026-11-06',covered:146,total:150,missing:4,positive_pct:35/146*100,median_pct:-12.2,p10_pct:-30,p90_pct:11,reference_summary:{covered:148,missing:2,positive_pct:36/148*100,median_pct:-12.2,p10_pct:-31,p90_pct:12},rows:[{symbol:'002717',name:'*ST岭南',return_pct:null,reference_return_pct:-57.94,gap:'期末有参考价但无实际成交',endpoint_trade_states:{anchor:{status:'traded',reason:'有成交证据'},endpoint:{status:'not_traded',reason:'无实际成交'}}}]},fixed_before:{rows:[]},paired:{count:146,before_median_pct:-12.2,after_median_pct:-12.2},reference_paired:{count:148,before_median_pct:-12.24,after_median_pct:-12.2}} as unknown as RegimeComparison
describe('traded endpoint revision',()=>{
 it('shows old and revised denominators and retains suspended reference as secondary',()=>{render(<STEndpointAudit comparison={c}/>);expect(screen.getByText('146只')).toBeVisible();expect(screen.getByText('148只')).toBeVisible();expect(screen.getByText(/原提供方参考价变化-57.94%/)).not.toBeVisible();fireEvent.click(screen.getByText('哪些端点改变了统计？'));expect(screen.getByText(/原提供方参考价变化-57.94%/)).toBeVisible();expect(screen.getByText(/主口径保留空值/)).toBeVisible();expect(screen.getByText(/每日ST等权参考、指数路径与公告窗口/)).toBeVisible()})
 it('does not claim a revision for old snapshots',()=>{const {container}=render(<STEndpointAudit comparison={{...c,fixed_after:{...c.fixed_after,reference_summary:undefined}}}/>);expect(container).toBeEmptyDOMElement()})
})
