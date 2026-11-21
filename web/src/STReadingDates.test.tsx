import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {STReadingDates} from './STReadingDates'
import update from './catalogNov20Fixed.json'
afterEach(cleanup)
it('keeps original price windows and partial announcement coverage separate',()=>{
 render(<STReadingDates snapshot={update.baseline_snapshot_digest} baselineThrough="2026-11-06" comparisonThrough="2026-11-19"/>);
 const r=screen.getByLabelText('本页资料日期与覆盖')
 expect(r).toHaveTextContent('原同窗复盘截至2026-11-19')
 expect(r).toHaveTextContent('10份正文已核，31份待核')
 expect(r).toHaveTextContent('原制度比较窗口截至2026-11-06')
 expect(r).toHaveTextContent('不是150家公司最新全部事项均已核完')
})
it('does not announce old partial coverage against a different snapshot',()=>{
 render(<STReadingDates snapshot="changed" baselineThrough="2026-11-23"/>);
 expect(screen.getByLabelText('本页资料日期与覆盖')).toHaveTextContent('尚未与当前快照对应')
 expect(screen.getByLabelText('本页资料日期与覆盖')).not.toHaveTextContent('10份正文已核')
})
