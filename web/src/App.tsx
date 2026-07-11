import {BarChart3, MessageSquareText} from 'lucide-react'
import {Link, NavLink, Route, Routes} from 'react-router-dom'
import {Copilot} from './Copilot'
import {DossierPage} from './DossierPage'

export function App() {
  return (
    <div className="shell">
      <header className="top">
        <Link className="brand" to="/"><span>ST</span>Research Copilot</Link>
        <nav>
          <NavLink to="/" end><MessageSquareText size={16}/>研究问答</NavLink>
          <NavLink to="/stocks/603398"><BarChart3 size={16}/>个股证据</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Copilot/>}/>
          <Route path="/stocks/:symbol" element={<DossierPage/>}/>
        </Routes>
      </main>
    </div>
  )
}
