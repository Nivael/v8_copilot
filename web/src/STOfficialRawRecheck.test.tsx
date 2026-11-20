import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STOfficialRawRecheck} from './STOfficialRawRecheck'
import type {STRegimeData} from './stRegimeTypes'
import packet from './officialRawRecheck.json'
afterEach(cleanup)
const data={content_digest:packet.baseline_snapshot_digest,source_asset:packet.input_asset} as STRegimeData
it('keeps product differences, missing trades and float precision separate',()=>{
 render(<STOfficialRawRecheck data={data}/>);expect(screen.getByText(/原141家直接报价一致的范围不变/)).toBeVisible()
 fireEvent.click(screen.getByText('查看三家日期、缺行和精度边界'))
 expect(screen.getByRole('table')).toHaveTextContent('2026-10-19');expect(screen.getByRole('table')).toHaveTextContent('93日')
 expect(screen.getByText(/后段27点官方原价/)).toBeVisible()
 fireEvent.click(screen.getByText('官方来源与本轮未解决的问题'))
 expect(screen.getAllByRole('link',{name:/上交所原始日线接口/})).toHaveLength(3)
 expect(screen.getByText(/不能认证一字跌停与退出能力/)).toBeVisible()
})
it('rejects changed input identity instead of reusing old certification',()=>{
 const {rerender}=render(<STOfficialRawRecheck data={{...data,source_asset:'changed'}}/>);expect(screen.getByRole('status')).toBeVisible()
 rerender(<STOfficialRawRecheck data={{...data,content_digest:'changed'}}/>);expect(screen.queryByRole('heading')).not.toBeInTheDocument()
})
