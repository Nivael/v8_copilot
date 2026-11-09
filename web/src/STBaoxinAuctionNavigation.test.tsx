import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {STRegimeThemes} from './STRegimeThemes'
import {availableQuestions} from './stQuestionNavigation'
import type {STRegimeData} from './stRegimeTypes'
import lots from './__fixtures__/baoxin-auction-links.json'
import chains from './__fixtures__/disclosure-chains.json'
function fixture():STRegimeData{
 const period={start:'2026-07-06',through:'2026-11-06',days:84,reference_change_pct:-10.93,market_change_pct:-20.13,conditions:[]}
 return {through:'2026-11-06',comparisons:[{key:'all',after:period,before:period,fixed_after:{total:150,covered:146,missing:4,median_pct:-12.2,positive_pct:23.97}}],themes:{months:[],market_days:[],baoxin_auction_links:lots,disclosure_chains:chains,announcements:{companies:1,catalog_rows:10,catalog_pages:1,verified_events:lots.observations,verified_companies:1,verified_documents:10,body_reads_this_refresh:0,boundary:'fixture'}}} as unknown as STRegimeData
}
const mount=()=>{const d=fixture();return render(<STRegimeThemes data={d} comparison={d.comparisons[0]} chart={null} onEvidence={vi.fn()}/>)}
afterEach(()=>{cleanup();window.history.replaceState(null,'','/learning')})
it('直接链接选择宝馨及公告入口，重建页面仍可读',()=>{window.history.replaceState(null,'','/learning#st-baoxin-auction-links');const mounted=mount();expect(screen.getByRole('region',{name:'宝馨竞拍与过户配对'})).toBeVisible();expect(screen.getByRole('button',{name:/公告到底改变了什么/})).toHaveAttribute('aria-pressed','true');mounted.unmount();mount();expect(screen.getByRole('heading',{name:'后来过户的，到底是哪一笔竞拍？'})).toBeVisible()})
it('入口按钮与返回三链不增加专题，历史导航恢复选择',()=>{window.history.replaceState(null,'','/learning');const d=fixture();const base={...d,themes:{...d.themes,baoxin_auction_links:undefined}} as STRegimeData;expect(availableQuestions(d).length).toBe(availableQuestions(base).length);mount();fireEvent.click(screen.getByRole('button',{name:'宝馨：过户对应哪笔竞拍？核分笔股份 →'}));expect(window.location.hash).toBe('#st-baoxin-auction-links');expect(screen.getByRole('region',{name:'宝馨竞拍与过户配对'})).toBeVisible();fireEvent.click(screen.getByRole('button',{name:'回看威领、龙元、沐邦的阶段对照 →'}));expect(screen.getByRole('region',{name:'公告文件与阶段关系'})).toBeVisible();expect(screen.queryByRole('region',{name:'宝馨竞拍与过户配对'})).not.toBeInTheDocument();act(()=>{window.history.replaceState(null,'','/learning#st-baoxin-auction-links');window.dispatchEvent(new PopStateEvent('popstate'))});expect(screen.getByRole('region',{name:'宝馨竞拍与过户配对'})).toBeVisible()})
