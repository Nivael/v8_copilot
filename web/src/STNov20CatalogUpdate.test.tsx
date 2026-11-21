import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen,fireEvent,within} from '@testing-library/react'
import {STNov20CatalogUpdate} from './STNov20CatalogUpdate'
import update from './catalogNov20Fixed.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
it('shows effective-date, cash and obligation boundaries before opening sources',()=>{
 render(<STNov20CatalogUpdate data={{content_digest:update.baseline_snapshot_digest} as STRegimeData}/>)
 fireEvent.change(screen.getByRole('combobox',{name:'公告补核阅读范围'}),{target:{value:'all'}})
 const r=screen.getByRole('complementary',{name:'11月20日固定样本公告更新'})
 expect(r).toHaveTextContent('10份待筛审')
 expect(r).toHaveTextContent('不可将23日拟生效状态倒填为20日已摘帽')
 expect(r).toHaveTextContent('未披露本次实收')
 expect(r).toHaveTextContent('4000万元未实缴出资义务')
 expect(r).toHaveTextContent('已获豁免1426.52万元')
 expect(r).toHaveTextContent('3951.75万元不是当前已获金额')
 expect(r).toHaveTextContent('尚无买家和成交价格')
 expect(r).toHaveTextContent('一拍流拍')
 expect(r).toHaveTextContent('不等于本期新损失')
 expect(r).toHaveTextContent('不是上市公司已进入重整')
 fireEvent.click(screen.getByText('查看公告依据 · 1225679819'))
 expect(within(r).getAllByRole('link',{name:'原件第2页 ↗'}).some(link=>link.getAttribute('href')?.includes('1225679819.PDF#page=2'))).toBe(true)
})
it('withholds updates for a different frozen baseline',()=>{
 render(<STNov20CatalogUpdate data={{content_digest:'changed'} as STRegimeData}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示更新')
 expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
})
it('starts with the latest phase and lets readers select a company',()=>{
 render(<STNov20CatalogUpdate data={{content_digest:update.baseline_snapshot_digest} as STRegimeData}/>);
 expect(screen.getByRole('complementary')).toHaveTextContent('不是结果公告')
 expect(screen.queryByText(/公司及子公司作为被告的八项既有诉讼/)).not.toBeInTheDocument()
 fireEvent.change(screen.getByRole('combobox',{name:'公告补核阅读范围'}),{target:{value:'002514'}})
 expect(screen.getByRole('complementary')).toHaveTextContent('一拍流拍')
 expect(screen.queryByText(/本文为计划，未证明已经买入/)).not.toBeInTheDocument()
})
