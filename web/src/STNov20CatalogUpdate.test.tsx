import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen,fireEvent,within} from '@testing-library/react'
import {STNov20CatalogUpdate} from './STNov20CatalogUpdate'
import update from './catalogNov20Fixed.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
it('shows effective-date, cash and obligation boundaries before opening sources',()=>{
 render(<STNov20CatalogUpdate data={{content_digest:update.baseline_snapshot_digest} as STRegimeData}/>)
 const r=screen.getByRole('complementary',{name:'11月20日固定样本公告更新'})
 expect(r).toHaveTextContent('34份待筛审')
 expect(r).toHaveTextContent('不可将23日拟生效状态倒填为20日已摘帽')
 expect(r).toHaveTextContent('未披露本次实收')
 expect(r).toHaveTextContent('4000万元未实缴出资义务')
 expect(r).toHaveTextContent('已获豁免1426.52万元')
 expect(r).toHaveTextContent('3951.75万元不是当前已获金额')
 expect(r).toHaveTextContent('尚无买家和成交价格')
 fireEvent.click(screen.getByText('查看公告依据 · 1225679819'))
 expect(within(r).getAllByRole('link',{name:'原件第2页 ↗'}).some(link=>link.getAttribute('href')?.includes('1225679819.PDF#page=2'))).toBe(true)
})
it('withholds updates for a different frozen baseline',()=>{
 render(<STNov20CatalogUpdate data={{content_digest:'changed'} as STRegimeData}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示更新')
 expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
})
