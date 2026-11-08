import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STJueweiAdjustment} from './STJueweiAdjustment'
import {STRemovalCohort} from './STRemovalCohort'
import patch from './__fixtures__/juewei-reconciliation.json'
import previous from './__fixtures__/removal-cohort.json'
afterEach(cleanup)
it('explains opposite raw and reference moves while keeping example dates, precision and source pages',()=>{
 render(<STJueweiAdjustment data={patch.adjustment} oldCount={11} newCount={12}/>)
 expect(screen.getByText(/5日配对由旧严格匹配组11只更新为同口径12只/)).toBeVisible()
 fireEvent.click(screen.getByText('为什么除息日原价下跌，复权读数却上涨？'))
 expect(screen.getByText(/裸收盘变化-1.94%/)).toBeVisible()
 expect(screen.getByText(/相对参考价变化\+0.50%/)).toBeVisible()
 expect(screen.getByText(/125个成交日回算与面板原值相符/)).toBeVisible()
 fireEvent.click(screen.getByText('分红总额、摊薄精度与原件页码'))
 expect(screen.getByText(/0.246487元/)).toBeVisible()
 expect(screen.getByText(/2026-09-24的11.43元作示例/)).toBeVisible()
 expect(screen.getByRole('link',{name:/专项核查意见 · 物理第4页/})).toHaveAttribute('href',patch.adjustment.facts[4].source.url)
})
it('adds the reconstructed issuer without hiding the old strict count or direct price differences',()=>{
 const data={...previous,adjustment_reconciliation:patch.adjustment,strict_quote_summaries:previous.summaries,summaries:{...previous.summaries,'5':patch.summary5},rows:previous.rows.map(r=>r.symbol==='603517'?patch.row:r)}
 render(<STRemovalCohort data={data}/>)
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'5'}})
 expect(screen.getByRole('img',{name:'后5日：4涨、8跌、0平'})).toBeVisible();expect(screen.queryByText(/另0只仍列在表里/)).not.toBeInTheDocument()
 fireEvent.click(screen.getByText('展开12只对照、缺窗与日期依据'))
 expect(screen.getByRole('cell',{name:'同一因子法重建后纳入'})).toBeVisible()
 fireEvent.click(screen.getByText('核报价覆盖、绝味复权差异与其他退出样本'))
 expect(screen.getByText(/100个历史日期的直接前复权数值差异/)).toBeVisible()
 expect(screen.getByText(/旧严格匹配11只的统计保留/)).toBeVisible()
})
it('does not certify reconstruction when its evidence conditions fail',()=>{
 render(<STJueweiAdjustment data={{...patch.adjustment,comparison_reconstruction_supported:false,status:'unresolved',answer:'重建条件未通过。'}} oldCount={11} newCount={11}/>)
 expect(screen.queryByText(/5日配对由旧严格匹配组/)).not.toBeInTheDocument()
 fireEvent.click(screen.getByText('为什么除息日原价下跌，复权读数却上涨？'))
 expect(screen.getByText('回算条件未全部通过，暂不认证')).toBeVisible()
})
it('does not invent the new explanation in an old snapshot',()=>{const {container}=render(<STJueweiAdjustment data={null} newCount={11}/>);expect(container).toBeEmptyDOMElement()})
