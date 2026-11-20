import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen,within} from '@testing-library/react'
import {STRemovalMatureWindows} from './STRemovalMatureWindows'
import data from './__fixtures__/removal-mature-windows.json'
afterEach(cleanup)
it('distinguishes matured windows from verified values and preserves the conflicting case',()=>{
 render(<STRemovalMatureWindows data={data}/>);const table=screen.getByRole('table',{name:'摘帽首日收盘之后20个市场交易日，不含首日跳变'});expect(within(table).getAllByRole('row')).toHaveLength(13);const juewei=within(table).getByRole('row',{name:/603517/});expect(juewei).toHaveTextContent('不认证');expect(juewei).toHaveTextContent('报价差异保留');expect(table).toHaveTextContent('2026-11-17');expect(screen.getByText(/这不是全12家的已核结果/)).toBeVisible()
})
