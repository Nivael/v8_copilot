import { BarChart3, MessageSquareText } from 'lucide-react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { CopilotPage } from './CopilotPage'
import { DossierPage } from './DossierPage'

function Shell() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="ST Research Copilot 首页">
          <span className="brand-mark">ST</span>
          <span>Research Copilot</span>
        </Link>
        <nav aria-label="主导航">
          <NavLink to="/" end>
            <MessageSquareText size={16} aria-hidden="true" />
            研究问答
          </NavLink>
          <NavLink to="/stocks/603398">
            <BarChart3 size={16} aria-hidden="true" />
            个股证据
          </NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<CopilotPage />} />
          <Route path="/stocks/:symbol" element={<DossierPage />} />
        </Routes>
      </main>
    </div>
  )
}

export function App() {
  return <Shell />
}
