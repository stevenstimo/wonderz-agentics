import HiringHall from './HiringHall.jsx';
import DaveDevConsole from './DaveDevConsole.jsx';
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

import App from './App.jsx'
import HRImprovements from './HRImprovements.jsx'
import CrewManagement from './CrewManagement.jsx'
import TrainingManagement from './TrainingManagement.jsx'
import ApprovalDashboard from './ApprovalDashboard.jsx'
import JobCenter from './JobCenter.jsx'
import ExplainerHowItWorks from './ExplainerHowItWorks.jsx'
import ExplainerPersona from './ExplainerPersona.jsx'
import ExplainerCrew from './ExplainerCrew.jsx'
import DeveloperBot from './DeveloperBot.jsx'
import DevbotHome from './DevbotHome.jsx'
import TalentOverview from './TalentOverview.jsx'
import Settings from './Settings.jsx'
import SherlockWidget from './SherlockWidget.jsx'
import StatusIntelligence from './StatusIntelligence.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/job-center" element={<JobCenter />} />
        <Route path="/crew/management" element={<CrewManagement />} />
        <Route path="/training/management" element={<TrainingManagement />} />
        <Route path="/approvals" element={<ApprovalDashboard />} />
        <Route path="/hr/improvements" element={<HRImprovements />} />
        <Route path="/explainer/how-it-works" element={<ExplainerHowItWorks />} />
        <Route path="/explainer/persona" element={<ExplainerPersona />} />
        <Route path="/explainer/crew" element={<ExplainerCrew />} />
        <Route path="/devbot" element={<DevbotHome />} />
        <Route path="/hiring" element={<HiringHall onHire={() => {}} />} />
        <Route path="/talents" element={<TalentOverview />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/status" element={<StatusIntelligence />} />
        <Route path="/the-brains" element={<StatusIntelligence />} />
        <Route path="/devbot/dave" element={<DaveDevConsole />} />
      </Routes>
      <SherlockWidget />
    </BrowserRouter>
  </React.StrictMode>,
)
