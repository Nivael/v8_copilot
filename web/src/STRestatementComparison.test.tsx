import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STRestatementComparison} from './STRestatementComparison'
import {availableQuestions,useQuestionNavigation} from './stQuestionNavigation'
import type {STRegimeData} from './stRegimeTypes'
import data from './__fixtures__/restatement-comparison.json'
afterEach(()=>{cleanup();window.history.replaceState(null,'','/');})
it('distinguishes growth bases and links each original source',()=>{
 render(<STRestatementComparison data={data}/>);
 const growth=screen.getByText(/按更正基数重算为/);expect(growth).toHaveTextContent('17.68%');expect(growth).toHaveTextContent('28.24%');expect(growth).toHaveTextContent('当期收入没有增加');
 const links=screen.getAllByRole('link',{hidden:true});expect(links).toHaveLength(10);
 for(const link of links)expect(data.source_refs.some(s=>s.url===link.getAttribute('href'))).toBe(true);
 expect(screen.getByText(/同一个披露日/)).toBeInTheDocument();
})
it('keeps suspended returns null and the 20-day horizon unfinished',()=>{
 render(<STRestatementComparison data={data}/>);fireEvent.change(screen.getByRole('combobox'),{target:{value:'20'}});
 const rows=within(screen.getByRole('table')).getAllByRole('row');expect(rows[1]).toHaveTextContent('-20.24%');expect(rows[2]).toHaveTextContent('2.23%');expect(rows[3]).toHaveTextContent('—（无共同成交端点）');
 for(const row of rows.slice(1))expect(row).toHaveTextContent('17日，窗口未满');
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}});expect(rows[1]).toHaveTextContent('1.34%');expect(rows[1]).toHaveTextContent('1.55%');
})
it('opens the new deep link only when data exists',()=>{
 const d={themes:{restatement_comparison:data}} as unknown as STRegimeData;
 expect(availableQuestions({themes:{}} as unknown as STRegimeData).some(q=>q.key==='restatement')).toBe(false);
 function Harness(){const nav=useQuestionNavigation(d);return <><button onClick={()=>nav.select('restatement')}>打开比较</button><output>{nav.topic}</output></>}
 render(<Harness/>);fireEvent.click(screen.getByRole('button',{name:'打开比较'}));expect(window.location.hash).toBe('#st-restatement-comparison');expect(screen.getByRole('status')).toHaveTextContent('restatement');
})
