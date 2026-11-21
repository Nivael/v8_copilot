import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {BreadthWaitComparison} from './BreadthWaitComparison'
afterEach(cleanup)
it('keeps latest mature first-day result separate from immature later waits',()=>{
 render(<BreadthWaitComparison/>);fireEvent.click(screen.getByText('更早看一两天，会多看到什么、错过什么？'));fireEvent.click(screen.getByRole('button',{name:'各自后5日：保留原观察'}))
 expect(screen.getByText(/15段可观察/)).toHaveTextContent('12段不足三日')
 const rows=screen.getAllByRole('row')
 expect(rows[1]).toHaveTextContent('完整5日，至2026-11-19')
 expect(rows[2]).toHaveTextContent('仅4日')
 expect(rows[3]).toHaveTextContent('仅3日')
 expect(rows[3]).toHaveTextContent('-5.59%')
 expect(screen.getByRole('table')).toHaveTextContent('完整5日留空')
})
it('retains short spells, unknown left boundary and a reversal across observation dates',()=>{
 render(<BreadthWaitComparison/>);fireEvent.click(screen.getByText('更早看一两天，会多看到什么、错过什么？'));fireEvent.click(screen.getByRole('button',{name:'各自后5日：保留原观察'}))
 const select=screen.getByRole('combobox',{name:'选择偏弱片段'})
 fireEvent.change(select,{target:{value:'2026-09-04'}})
 expect(screen.getByText(/这只是覆盖窗口内首日/)).toBeVisible()
 expect(screen.getAllByText('未形成')).toHaveLength(2)
 fireEvent.change(select,{target:{value:'2026-09-09'}})
 const rows=screen.getAllByRole('row')
 expect(rows[1]).toHaveTextContent('-1.72%')
 expect(rows[3]).toHaveTextContent('+1.61%')
 expect(screen.getByText(/后窗起点不同/)).toBeVisible()
 expect(screen.getByText(/不能计为独立案例/)).toBeVisible()
})

it('defaults to one endpoint and keeps both observation modes when switching spells',()=>{
 render(<BreadthWaitComparison/>);fireEvent.click(screen.getByText('更早看一两天，会多看到什么、错过什么？'))
 const table=screen.getByRole('table',{name:'统一至2026-11-19；各行剩余天数不同'})
 expect(table).toHaveTextContent('5个交易日');expect(table).toHaveTextContent('4个交易日');expect(table).toHaveTextContent('3个交易日')
 expect(table).toHaveTextContent('-5.88%')
 expect(screen.getByText(/每行此前与此后复合/)).toHaveTextContent('不能直接相加')
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'2026-09-09'}})
 expect(screen.getByRole('table',{name:'统一至2026-09-16；各行剩余天数不同'})).toHaveTextContent('+0.49%')
 fireEvent.click(screen.getByRole('button',{name:'各自后5日：保留原观察'}))
 expect(screen.getByRole('table')).toHaveTextContent('+1.61%')
})
