import {lazy,Suspense} from 'react'
import {Link, Navigate, NavLink, Route, Routes} from 'react-router-dom'
import {MarketOverview} from './MarketOverview'
import {ExperienceHub} from './ExperienceHub'

const Copilot=lazy(()=>import('./Copilot').then(module=>({default:module.Copilot})))
const DossierPage=lazy(()=>import('./DossierPage').then(module=>({default:module.DossierPage})))
const ExperienceCenter=lazy(()=>import('./ExperienceCenter').then(module=>({default:module.ExperienceCenter})))
const RunAudit=lazy(()=>import('./RunAudit').then(module=>({default:module.RunAudit})))
const DailyIntelligencePage=lazy(()=>import('./DailyIntelligencePage').then(module=>({default:module.DailyIntelligencePage})))
const LearningPage=lazy(()=>import('./LearningPage').then(module=>({default:module.LearningPage})))
const MarketRiskPage=lazy(()=>import('./MarketRiskPage').then(module=>({default:module.MarketRiskPage})))

export function App() {
  return (
    <div className="shell">
      <header className="top">
        <Link className="brand" to="/market"><span>ST</span>研究台</Link>
        <nav>
          <NavLink to="/market">市场判断</NavLink>
          <NavLink to="/learning">跟踪与经验</NavLink>
        </nav>
      </header>
      <main>
        <Suspense fallback={<p className="reading-page" role="status">正在打开…</p>}><Routes>
          <Route path="/market" element={<MarketOverview/>}/>
          <Route path="/learning" element={<ExperienceHub/>}/>
          <Route path="/" element={<Navigate to="/market" replace/>}/>
          <Route path="/market/evidence" element={<MarketRiskPage/>}/>
          <Route path="/methods" element={<ExperienceCenter/>}/>
          <Route path="/system" element={<LearningPage/>}/>
          <Route path="/legacy" element={<Copilot/>}/>
          <Route path="/stocks/:symbol" element={<DossierPage/>}/>
          <Route path="/runs" element={<RunAudit/>}/>
          <Route path="/daily" element={<DailyIntelligencePage/>}/>
          <Route path="*" element={<div className="reading-page"><h1>这个页面已调整</h1><Link to="/market">回到市场判断 →</Link></div>}/>
        </Routes></Suspense>
      </main>
    </div>
  )
}
