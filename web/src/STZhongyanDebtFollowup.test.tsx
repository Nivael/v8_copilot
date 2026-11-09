import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STZhongyanDebtFollowup} from './STZhongyanDebtFollowup'
import type {ZhongyanDebtFollowup} from './STZhongyanDebtFollowup'
import {STInitialThreeFollowup} from './STInitialThreeFollowup'
import type {InitialThreeFollowup} from './STInitialThreeFollowup'
import debt from './__fixtures__/zhongyan-debt-followup.json'
import data from './__fixtures__/initial-three-followup.json'
afterEach(cleanup)
it('更新默认公司与已通过待办，不再显示旧的待核段落',()=>{render(<STInitialThreeFollowup data={data as InitialThreeFollowup} debt={debt as ZhongyanDebtFollowup}/>);expect(screen.getByLabelText('三家后续公司')).toHaveValue('002542');expect(screen.getByRole('region',{name:'中岩代偿与股东债权更新'})).toBeVisible();expect(screen.getByText(/旧的“股东会审议另待核”可以关闭/)).toBeVisible();expect(screen.queryByText(/后续股东会与每笔履约不由这份董事会公告自动认证/)).toBeNull();fireEvent.change(screen.getByLabelText('三家后续公司'),{target:{value:'000909'}});expect(screen.queryByRole('region',{name:'中岩代偿与股东债权更新'})).toBeNull()})
it('已支付的中票、批准上限与期末余额分别呈现',()=>{render(<STZhongyanDebtFollowup data={debt as ZhongyanDebtFollowup}/>);expect(screen.getByRole('table',{name:'中岩代偿金额层次'})).toHaveTextContent('不是另一笔实付，不与5.185亿元相加');expect(screen.getByText(/不能累计为三笔还款/)).toBeVisible()})
it('同口径显示短借减少、其他应付款增加与总负债真实下降',()=>{render(<STZhongyanDebtFollowup data={debt as ZhongyanDebtFollowup}/>);fireEvent.click(screen.getByText('短借减少75.80%，为什么不能只说债务压力消失？'));const t=screen.getByRole('table',{name:'中岩同口径负债与权益'});expect(t).toHaveTextContent('95,301.12');expect(t).toHaveTextContent('-30,683.14');expect(screen.getByText(/负债合计确实减少约3.07亿元/)).toBeVisible()})
it('与西王占款清偿比较机制，原件指向对应页码',()=>{render(<STZhongyanDebtFollowup data={debt as ZhongyanDebtFollowup}/>);fireEvent.click(screen.getByText('和西王的“占款清偿”，为什么不能混成同一种改善？'));expect(screen.getByText(/前者核的是公司收回被占用资源/)).toBeVisible();expect(screen.getByRole('link',{name:'西王占款清偿原件 ↗'}).getAttribute('href')).toMatch(/#page=1$/)})
it('新增两节点窗口单独核对，不冒充上轮35窗口范围',()=>{render(<STZhongyanDebtFollowup data={debt as ZhongyanDebtFollowup}/>);fireEvent.click(screen.getByText('兑付与股东会节点后，同窗行情怎样走？'));expect(screen.getByRole('table',{name:'中岩代偿节点同窗行情'})).toHaveTextContent('2026-09-18');fireEvent.change(screen.getByLabelText('中岩代偿观察窗口'),{target:{value:'20'}});expect(screen.getByText(/本轮两节点的6个窗口另用已存腾讯前复权核端点/)).toBeVisible()})
