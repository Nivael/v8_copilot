import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-ninth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('distinguishes an uncollectible claim from recovered inventory auction proceeds',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/债权基本确定无法收回、已全额计提/, {selector:'section > p'})).toBeVisible();expect(screen.getByText(/6月29日子公司已收齐2504.02万元/, {selector:'section > p'})).toBeVisible();expect(screen.getByText(/74 → 78\/150家/)).toBeVisible()
})
it('retains the opposing observed paths without claiming a removal premium',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText('+37.66%')).toBeVisible();expect(screen.getByText('-44.96%')).toBeVisible();expect(screen.getByText(/期间催化仍需另核/)).toBeVisible()
})
it('lets readers inspect the original scanned audit and separate cash evidence',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/原提取全空，未以OCR替换原文/)).toBeVisible();expect(screen.getByText(/普通债权基本确定无法收回及全额计提/)).toBeVisible();expect(screen.getByText(/连同已收1500万元/)).toBeVisible()
})
