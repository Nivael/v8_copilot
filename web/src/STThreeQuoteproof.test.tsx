import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STInitialThreeFollowup} from './STInitialThreeFollowup'
import type {InitialThreeFollowup,ThreeQuoteproof} from './STInitialThreeFollowup'
import data from './__fixtures__/initial-three-followup.json'
import proof from './__fixtures__/three-quoteproof.json'
afterEach(cleanup)
it('报价重放与新增采集分开，同日双公告去重后再计窗口',()=>{render(<STInitialThreeFollowup data={data as InitialThreeFollowup} quoteproof={proof as ThreeQuoteproof}/>);fireEvent.click(screen.getByText('这些公告窗口的价格，另一路报价核过吗？'));expect(screen.getByText(/本轮重放6份已有报价/)).toBeVisible();expect(screen.getByText(/42个观察窗口，35个可比、7个未满/)).toBeVisible();expect(screen.getByRole('table',{name:'三家公司报价重放覆盖'})).toHaveTextContent('126')})
it('显示原始响应定位和搜索范围，不把搜索无新结果当不存在',()=>{render(<STInitialThreeFollowup data={data as InitialThreeFollowup} quoteproof={proof as ThreeQuoteproof}/>);fireEvent.click(screen.getByText('这些公告窗口的价格，另一路报价核过吗？'));fireEvent.click(screen.getByText('报价原始响应与核对日期'));expect(screen.getAllByRole('link',{name:/腾讯.*收盘/})).toHaveLength(6);fireEvent.click(screen.getByText('正式节点为什么仍然待核？'));expect(screen.getByText(/检索不是全渠道穷尽/)).toBeVisible()})
it('有报价差异就显示差异而不是固定写全部一致',()=>{const q=structuredClone(proof)as ThreeQuoteproof;q.all_quotes_agree=false;q.all_windows_agree_to_2dp=false;q.companies[0].all_agree=false;q.companies[0].channels[1].differences=[{date:'2026-09-17',primary:5,checked:'0.01'}];render(<STInitialThreeFollowup data={data as InitialThreeFollowup} quoteproof={q}/>);fireEvent.click(screen.getByText('这些公告窗口的价格，另一路报价核过吗？'));expect(screen.getByText(/这组核对出现差异或缺口/)).toBeVisible();expect(screen.getByRole('table',{name:'三家公司报价重放覆盖'})).toHaveTextContent('2026-09-17原5 / 核0.01')})
