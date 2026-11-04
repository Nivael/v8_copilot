import {Activity, BarChart3, BookOpenCheck, FileClock, MessageSquareText, RefreshCw} from 'lucide-react'
import {Link, NavLink, Route, Routes} from 'react-router-dom'
import {Copilot} from './Copilot'
import {DossierPage} from './DossierPage'
import {ExperienceCenter} from './ExperienceCenter'
import {RunAudit} from './RunAudit'
import {DailyIntelligencePage} from './DailyIntelligencePage'
import {LearningPage} from './LearningPage'
import {MarketRiskBanner,MarketRiskPage} from './MarketRiskPage'

export function App() {
  return (
    <div className="shell">
      <header className="top">
        <Link className="brand" to="/"><span>ST</span>Research Workbench</Link>
        <nav>
          <NavLink to="/market"><Activity size={16}/>大盘环境</NavLink>
          <NavLink to="/learning"><RefreshCw size={16}/>更新与复盘</NavLink>
          <NavLink to="/" end><BookOpenCheck size={16}/>经验中心</NavLink>
          <NavLink to="/legacy"><MessageSquareText size={16}/>研究问答（兼容）</NavLink>
          <NavLink to="/stocks/603398"><BarChart3 size={16}/>个股证据</NavLink>
          <NavLink to="/runs"><FileClock size={16}/>运行审计</NavLink>
          <NavLink to="/daily"><Activity size={16}/>每日观察</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/market" element={<MarketRiskPage/>}/>
          <Route path="/learning" element={<LearningPage/>}/>
          <Route path="/" element={<ExperienceCenter/>}/>
          <Route path="/legacy" element={<Copilot/>}/>
          <Route path="/stocks/:symbol" element={<><MarketRiskBanner/><DossierPage/></>}/>
          <Route path="/runs" element={<RunAudit/>}/>
          <Route path="/daily" element={<><MarketRiskBanner/><DailyIntelligencePage/></>}/>
        </Routes>
      </main>
    </div>
  )
}
