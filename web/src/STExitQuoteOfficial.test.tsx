import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STExitQuoteOfficial} from './STExitQuoteOfficial'
import type {STRegimeData} from './stRegimeTypes'
import packet from './exitQuoteOfficial.json'
afterEach(cleanup)
const data={content_digest:packet.baseline_snapshot_digest,source_asset:packet.input_asset} as STRegimeData
it('keeps official failures, old closes and missing anchors distinct',()=>{
 render(<STExitQuoteOfficial data={data}/>);fireEvent.click(screen.getByText('四家缺价再查官方行情，哪些仍不能补？'))
 expect(screen.getByRole('table')).toHaveTextContent('66个旧成交日')
 expect(screen.getByRole('table')).toHaveTextContent('后来有成交不倒填7月3日起点')
 expect(screen.getByText(/相同错误字节/)).toBeVisible()
 expect(screen.getByText(/有聚合盘口，未返回实际涨跌停价/)).toBeVisible()
 fireEvent.click(screen.getByText('原始返回、观察时刻与剩余资料'))
 expect(screen.getAllByRole('link',{name:/对应官方行情请求/})).toHaveLength(4)
})
it('hides a changed source identity',()=>{
 render(<STExitQuoteOfficial data={{...data,source_asset:'changed'}}/>);expect(screen.queryByText(/四家缺价再查/)).not.toBeInTheDocument()
})
