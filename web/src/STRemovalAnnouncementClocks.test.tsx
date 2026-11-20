import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STRemovalAnnouncementClocks} from './STRemovalAnnouncementClocks'
import {removalAnnouncementClocks} from './removalAnnouncementClocks'
import input from './__fixtures__/removal-announcement-clocks-input.json'
import expected from './__fixtures__/removal-announcement-clocks-expected.json'
afterEach(cleanup)
it('matches independent raw endpoint calculations while withholding Juewei exact values',()=>{
 const r=removalAnnouncementClocks(input)!
 for(const company of r.cases)for(const w of company.windows){const e=expected.windows.find(e=>e.symbol===company.symbol&&e.label===w.label)!;if(e.certified_pct===null)expect(w.certified).toBeNull();else expect(w.certified).toBeCloseTo(Number(e.certified_pct),10);expect(w.market).toBeCloseTo(Number(e.market_pct),10)}
})
it('refuses an uncertified event window or missing chronological source',()=>{
 const changed=structuredClone(input);changed.event_reviews=changed.event_reviews.filter(r=>r.aid!=='1225629182');expect(removalAnnouncementClocks(changed)).toBeNull()
 const missing=structuredClone(input);missing.sources=missing.sources.filter(r=>r.announcement_id!=='1225676244');expect(removalAnnouncementClocks(missing)).toBeNull()
})
it('shows distinct cutoffs and keeps later announcements out of the earlier window',()=>{
 render(<STRemovalAnnouncementClocks input={input}/>);const table=screen.getByRole('table',{name:'同日摘帽，两家公司与三个观察窗口'});expect(within(table).getAllByRole('row')).toHaveLength(7);expect(table).toHaveTextContent('6.23%');expect(table).toHaveTextContent('-6.89%');expect(table).toHaveTextContent('-20.24%');expect(table).toHaveTextContent('已观察17日，20日未满');expect(screen.getByText(/晚于11月17日的20日窗口终点/)).toBeVisible();fireEvent.click(screen.getByText('核对窗口原值与剩余限制'));expect(screen.getAllByText(/两种数值都保留/)).toHaveLength(2)
})
