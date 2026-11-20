import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STLimitCohorts} from './STLimitCohorts'
afterEach(cleanup)
it('keeps daily cohort denominators and distinct closing/touch/single-price facts',()=>{
 render(<STLimitCohorts/>);fireEvent.click(screen.getByText('把限价核到整个样本后，压力怎样变化？'))
 expect(screen.getByRole('table')).toHaveTextContent('141／142')
 expect(screen.getByRole('table')).toHaveTextContent('10只7.1%')
 expect(screen.getByText(/各列不能相加/)).toBeVisible()
 fireEvent.click(screen.getByText('全天同价记录、缺价与原件范围'))
 expect(screen.getByText(/2026-11-18 · \*ST启环/)).toBeVisible()
 expect(screen.getByText(/未配对股票/)).toHaveTextContent('002717.SZ')
})
it('preserves exited and missing companies when switching to fixed 150',()=>{
 render(<STLimitCohorts/>);fireEvent.click(screen.getByText('把限价核到整个样本后，压力怎样变化？'))
 fireEvent.click(screen.getByRole('button',{name:'固定150只原始样本'}))
 expect(screen.getByRole('table')).toHaveTextContent('147／150')
 expect(screen.getByRole('table')).toHaveTextContent('7只4.8%')
 expect(screen.getByText(/不能把整组称为当日ST/)).toBeVisible()
 fireEvent.click(screen.getByText('全天同价记录、缺价与原件范围'))
 expect(screen.getByText(/未配对股票/)).toHaveTextContent('000016.SZ、002717.SZ、002731.SZ')
})
