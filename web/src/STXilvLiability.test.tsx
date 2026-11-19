import {cleanup,render,screen,fireEvent} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STXilvLiability} from './STXilvLiability'
import type {XilvLiability} from './STXilvLiability'
import {STXilvTimeline} from './STXilvTimeline'
import type {XilvTimeline} from './STXilvTimeline'
import fixture from './__fixtures__/xilv-liability.json'
import old from './__fixtures__/xilv-timeline.json'
afterEach(cleanup)
const data=fixture as XilvLiability
it('keeps quotas and signed rollover separate from received operating cash',()=>{
 render(<STXilvLiability data={data}/>);expect(screen.getByText(/不能相加当作新增现金/)).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'1亿元额度内的5000万元展期'}));expect(screen.getByText(/额度不是现金/)).toBeTruthy()
 fireEvent.change(screen.getByLabelText('沿披露顺序看批准或履约'),{target:{value:'2'}});expect(screen.getByRole('link',{name:/查看此步原件/}).getAttribute('href')).toContain('1225588596.PDF')
})
it('does not confuse shareholder approval of guarantee with approval of loan rollover',()=>{
 render(<STXilvLiability data={data}/>);fireEvent.click(screen.getByRole('button',{name:'子公司为购房人按揭提供担保'}));expect(screen.getByText(/为购房人按揭提供1000万元/)).toBeTruthy()
 fireEvent.change(screen.getByLabelText('沿披露顺序看批准或履约'),{target:{value:'1'}});expect(screen.getByRole('link',{name:/查看此步原件/}).getAttribute('href')).toContain('1225462269.PDF')
})
it('shows different lawsuit parties, total requests and mixed roles, preserving incomplete windows',()=>{
 render(<STXilvLiability data={data}/>);fireEvent.click(screen.getByRole('button',{name:'诉讼与执行'}));expect(screen.getByText(/不能写成上市公司新增同额损失/)).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'另一施工纠纷：仍处起诉阶段'}));expect(screen.getByText(/4514.77万元/)).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'累计1134万元：原被告方向不同'}));expect(screen.getByText(/不能全当现金流出/)).toBeTruthy()
 fireEvent.click(screen.getByText('这次披露附近，西旅与市场怎样走？'));expect(screen.getAllByText('未满窗口').length).toBe(3)
})
it('labels the original nine-document scope as a retained earlier coverage view',()=>{
 render(<STXilvTimeline data={old as XilvTimeline} followup={data}/>);expect(screen.getByText('原过程核验范围（补核前）')).toBeTruthy();expect(screen.getByText(/两轮共19\/32份、124页/)).toBeTruthy()
})
it('does not show a new supplement when absent',()=>{const {container}=render(<STXilvLiability/>);expect(container.firstChild).toBeNull()})
