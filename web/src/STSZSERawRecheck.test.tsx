import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STSZSERawRecheck} from './STSZSERawRecheck'
import type {STRegimeData} from './stRegimeTypes'
import packet from './szseRawRecheck.json'
afterEach(cleanup)
const data={content_digest:packet.baseline_snapshot_digest,source_asset:packet.input_asset} as STRegimeData
it('adds official raw coverage without eliminating adjusted-price differences',()=>{
 render(<STSZSERawRecheck data={data}/>);expect(screen.getByText(/五家共469个证券日/)).toBeVisible()
 fireEvent.click(screen.getByText('深市两家的来源、日期与剩余限制'))
 expect(screen.getByRole('table')).toHaveTextContent('2026-11-19')
 expect(screen.getByText(/本研究止于19日/)).toBeVisible()
 expect(screen.getByText(/没有被当作除权日实际参考涨跌幅或涨跌停价/)).toBeVisible()
 expect(screen.getAllByRole('link',{name:/深交所原始历史日线/})).toHaveLength(2)
})
it('refuses changed input identity',()=>{
 render(<STSZSERawRecheck data={{...data,source_asset:'changed'}}/>);expect(screen.queryByLabelText('深市两家原价补证')).not.toBeInTheDocument()
})
