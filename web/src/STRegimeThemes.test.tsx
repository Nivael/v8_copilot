import initialOrigin from './__fixtures__/initial-warning-origin.json'
import initialDay from './__fixtures__/initial-day-corroboration.json'
import initialCoverage from './__fixtures__/initial-status-coverage.json'
import initialRuihe from './__fixtures__/ruihe-process.json'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {STRegimeThemes} from './STRegimeThemes'
import type {STRegimeData} from './stRegimeTypes'
import earnings from './__fixtures__/earnings-warning.json'
import strong from './__fixtures__/strong-removal-cases.json'
import execution from './__fixtures__/shenwu-execution.json'
import cohort from './__fixtures__/removal-cohort.json'
import followup from './__fixtures__/jinglan-removal-followup.json'
import {availableQuestions} from './stQuestionNavigation'
// Navigation needs real conditional-study packets, not another copy of the full market dataset.
function fixture():STRegimeData{
 const period={start:'2026-07-06',through:'2026-11-06',days:84,reference_change_pct:-10.93,market_change_pct:-20.13,conditions:[]}
 const comparison={key:'all',after:period,before:period,fixed_after:{total:150,covered:146,missing:4,median_pct:-12.2,positive_pct:23.97}}
 return {through:'2026-11-06',comparisons:[comparison],themes:{months:[],market_days:[],earnings_warning:earnings,strong_removal_cases:strong,shenwu_execution:execution,removal_cohort:cohort,removal_followup:followup}} as unknown as STRegimeData
}
function mount(data=fixture()){return render(<STRegimeThemes data={data} comparison={data.comparisons[0]} chart={<p>共同市场图</p>} onEvidence={vi.fn()}/>)}
function choose(key:string){fireEvent.change(screen.getByRole('combobox',{name:'按具体问题查阅'}),{target:{value:key}})}
beforeEach(()=>window.history.replaceState(null,'','/learning'))
afterEach(()=>{cleanup();window.history.replaceState(null,'','/learning')})
describe('按问题查阅已核研究',()=>{
 it('总览与经验不再同时堆入所有个案，默认答案仍有共同市场图',()=>{
  mount();expect(screen.getByText('共同市场图')).toBeVisible()
  expect(screen.queryByRole('region',{name:'盈利现金与监管条件对照'})).not.toBeInTheDocument()
  expect(screen.queryByRole('heading',{name:'摘帽后涨得强，经营就已经修复了吗？'})).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:/下次怎样看得更准/}))
  expect(screen.getByText('① 先确定比较对象')).toBeVisible()
  expect(screen.queryByRole('heading',{name:'盈利和现金都转好，为什么还在ST？'})).not.toBeInTheDocument()
 })
 it('从目录只打开所选真实专题，保留来源链接与固定窗口边界',()=>{
  const data=fixture(),before=JSON.stringify(data);mount(data);choose('earnings')
  expect(screen.getByRole('heading',{name:'盈利和现金都转好，为什么还在ST？'})).toBeVisible()
  expect(screen.getByText('-53.79%')).toBeVisible()
  fireEvent.click(screen.getByText('为什么“调查办理终结”也不等于可以立刻撤销？'))
  expect(screen.getAllByRole('link',{name:/第159页/})[0]).toHaveAttribute('href',earnings.rule.url+'#page=159')
  choose('cohort');expect(screen.getByRole('heading',{name:'摘帽后，股价是否普遍继续上涨？'})).toBeVisible()
  expect(screen.queryByRole('heading',{name:'盈利和现金都转好，为什么还在ST？'})).not.toBeInTheDocument()
  expect(JSON.stringify(data)).toBe(before)
 })
 it('神雾执行单列，强势案例不再夹入另一套长表',()=>{
  mount();choose('strong');expect(screen.getByRole('heading',{name:'摘帽后涨得强，经营就已经修复了吗？'})).toBeVisible()
  expect(screen.queryByRole('heading',{name:'过户、签约，距离现金到账还有多远？'})).not.toBeInTheDocument()
  choose('execution');expect(screen.getByRole('heading',{name:'过户、签约，距离现金到账还有多远？'})).toBeVisible()
  expect(screen.queryByRole('heading',{name:'摘帽后涨得强，经营就已经修复了吗？'})).not.toBeInTheDocument()
 })
 it.each(['st-earnings-warning','st-strong-removal-cases','st-shenwu-execution'])('已有锚点 %s 刷新后自动恢复对应专题',hash=>{
  window.history.replaceState(null,'','/learning#'+hash);const view=mount()
  expect(view.container.querySelector('#'+hash)).toBeVisible()
  expect(screen.getByRole('link',{name:'此问题的固定链接'})).toHaveAttribute('href','#'+hash)
 })
 it('浏览器前后导航恢复问题，返回总览也可追溯',()=>{
  mount();choose('earnings');choose('execution')
  act(()=>{window.history.replaceState(null,'','/learning#st-earnings-warning');window.dispatchEvent(new PopStateEvent('popstate'))})
  expect(screen.getByRole('heading',{name:'盈利和现金都转好，为什么还在ST？'})).toBeVisible()
  act(()=>{window.history.replaceState(null,'','/learning#st-shenwu-execution');window.dispatchEvent(new HashChangeEvent('hashchange'))})
  expect(screen.getByRole('heading',{name:'过户、签约，距离现金到账还有多远？'})).toBeVisible()
  fireEvent.click(screen.getByRole('button',{name:'返回整批行情总览 →'}));expect(screen.getByText('共同市场图')).toBeVisible()
 })
 it('旧快照缺专题不提供空入口，锚点不强造不存在的资料',()=>{
  const data=fixture();data.themes={months:[],market_days:[]};window.history.replaceState(null,'','/learning#st-earnings-warning')
  mount(data);expect(screen.queryByRole('combobox',{name:'按具体问题查阅'})).not.toBeInTheDocument();expect(screen.getByText('共同市场图')).toBeVisible()
 })
 it('最新快捷入口与目录用同一路径，旧公司专题仍可查阅',()=>{
  mount();fireEvent.click(screen.getByRole('button',{name:/本轮新核/}));expect(window.location.hash).toBe('#st-earnings-warning')
  choose('followup');expect(screen.getByRole('region',{name:'京蓝摘帽后续复盘'})).toBeVisible()
  expect(within(screen.getByRole('combobox',{name:'按具体问题查阅'})).getAllByRole('option')).toHaveLength(6)
  expect(availableQuestions(fixture()).map(q=>q.key)).toEqual(['earnings','cohort','strong','execution','followup'])
 })
})

it('固定入口接通警示依据包，实际专题不能只停留旧原件覆盖',()=>{
 window.history.replaceState(null,'','/learning#st-initial-status-coverage')
 const data=fixture();data.themes={...data.themes,initial_status_coverage:initialCoverage,ruihe_process:initialRuihe,initial_day_corroboration:initialDay,initial_warning_origin:initialOrigin} as unknown as STRegimeData['themes']
 mount(data);expect(screen.getByRole('region',{name:'期初警示依据补全'})).toBeVisible();expect(screen.getByText('六家警示依据已补；同样异动，背后的约束不同')).toBeVisible()
})
