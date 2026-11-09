import {afterEach,it,expect} from 'vitest'
import {render,screen,cleanup,fireEvent} from '@testing-library/react'
import {STHukeDateProof} from './STHukeDateProof'
import type {HukeDateProof} from './STHukeDateProof'
import fixture from './__fixtures__/huke-date-proof.json'
const data=fixture as HukeDateProof
afterEach(cleanup)
it('separates prior arrangement from first-day notice and preserves unknown first-public time',()=>{render(<STHukeDateProof data={data}/>);expect(screen.getByRole('heading',{name:'6月8日是实施日；5月30日是提前披露的安排'})).toBeVisible();expect(screen.getByText(/5月30日的045号是整理交易安排/)).toBeVisible();expect(screen.getAllByRole('link')).toHaveLength(3);fireEvent.click(screen.getByText('修正了什么，还有什么不能确定？'));expect(screen.getByText(/最早实际公开日及分钟/)).toBeVisible()})
it('shows both window bases without filling an untraded endpoint',()=>{render(<STHukeDateProof data={data}/>);fireEvent.click(screen.getByText('日期基准更正后，行情比较有什么变化？'));expect(screen.getByRole('region',{name:'沪科日期基准窗口比较'})).toBeVisible();expect(screen.getAllByText(/个股-10.00%/)).toHaveLength(2);expect(screen.getByText(/20日终点无实际成交，继续不可算/)).toBeVisible()})
it('does not manufacture evidence for old snapshots',()=>{const {container}=render(<STHukeDateProof/>);expect(container).toBeEmptyDOMElement()})
