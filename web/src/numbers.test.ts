import {describe,expect,it} from 'vitest'
import {formatShareCount} from './numbers'

describe('exact share display',()=>{
  it.each([
    ['48100.8947756500','48,100.8947756500'],
    ['0.7525043100','0.7525043100'],
    ['-72900000.00','-72,900,000.00'],
    ['9007199254740993.000000000001','9,007,199,254,740,993.000000000001'],
    ['0','0'],
    ['1000000','1,000,000'],
    [null,'—'],
    [undefined,'—'],
  ])('preserves the source value and precision (%s)',(source,expected)=>{
    expect(formatShareCount(source)).toBe(expected)
  })
})
