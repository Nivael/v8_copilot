import {render,screen,fireEvent,cleanup,within} from '@testing-library/react'
import {it,expect,afterEach} from 'vitest'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import type {WarningBasisFollowup} from './STWarningBasisFollowup'
import initial from './__fixtures__/initial-status-coverage.json'
import followup from './__fixtures__/warning-basis-followup.json'
afterEach(cleanup)
const renderUpdate=()=>render(<STInitialStatusCoverage data={initial as InitialStatusCoverage} update={followup as WarningBasisFollowup}/> )
it('先给修正后的判断，保留7月事实而不继续声称初始原因仍缺',()=>{renderUpdate();expect(screen.getByRole('region',{name:'南置与西王判断更新'})).toBeVisible();expect(screen.getByRole('heading',{name:'西王清了占款，内控风险仍在；南置报表改善，审批另看'})).toBeVisible();expect(screen.getByText(/再回到7月3日/)).toBeVisible();expect(screen.queryByText('本件可证明当时仍受双重警示，但没有完整列明最初触发原因，原因原件另待补。')).toBeNull();expect(screen.getByRole('region',{name:'原判断与后续证据'})).toHaveTextContent('不是完成过户');expect(screen.getByText(/上一轮补入6份/)).toBeVisible();expect(screen.getByText(/同窗5日再看价格：流拍公告后/)).toHaveTextContent('个股+20.00%，大盘-1.48%、ST参考+1.54%');expect(screen.getByText(/同窗5日再看价格：流拍公告后/)).toHaveTextContent('个股-4.12%，同期大盘+3.29%、ST参考+4.32%')})
it('分开抵债资产与现金，重申不变第二次清偿',()=>{renderUpdate();fireEvent.click(screen.getByText('西王1.3亿元如何归还？不要全算现金'));expect(screen.getByText(/6,800.00万元抵债资产全部交割/)).toBeVisible();expect(screen.getByText(/6,200.00万元占款本金以现金偿还/)).toBeVisible();expect(screen.getByText(/不是第二次清偿/)).toBeVisible();expect(screen.getByText(/首次ST的直接依据是2025年度内控审计否定意见/)).toBeVisible()})
it('利润现金与审批分开，金额单位和未审计比较期不丢失',()=>{renderUpdate();fireEvent.click(screen.getByText('南置：为什么净资产转正、盈利，也不能直接叫摘帽？'));expect(screen.getByText(/归母净利润2,548.62万元/)).toBeVisible();expect(screen.getByText(/经营现金流-2,886.33万元/)).toBeVisible();expect(screen.getByText(/季报未经审计/)).toBeVisible();expect(within(screen.getByText('南置：为什么净资产转正、盈利，也不能直接叫摘帽？').closest('details')!).getByText(/不计入作出有关决定的期限/)).toBeVisible();expect(screen.getByRole('link',{name:/深交所名单原接口/})).toHaveAttribute('href',followup.nanzhi_endpoint.sources[0].url)})
