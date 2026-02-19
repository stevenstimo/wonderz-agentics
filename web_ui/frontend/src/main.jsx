import HiringHall from './HiringHall.jsx';
import DaveDevConsole from './DaveDevConsole.jsx';
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

import App from './App.jsx'
import Dashboard from './Dashboard.jsx'
import HRImprovements from './HRImprovements.jsx'
import HRDashboard from './HRDashboard.jsx'
import CrewManagement from './CrewManagement.jsx'
import TrainingManagement from './TrainingManagement.jsx'
import TrainingHub from './TrainingHub.jsx'
import ApprovalDashboard from './ApprovalDashboard.jsx'
import JobCenter from './JobCenter.jsx'
import AgentsOverview from './AgentsOverview.jsx'
import NewCrewMember from './NewCrewMember.jsx'
import ExplainerHowItWorks from './ExplainerHowItWorks.jsx'
import ExplainerPersona from './ExplainerPersona.jsx'
import ExplainerCrew from './ExplainerCrew.jsx'
import DeveloperBot from './DeveloperBot.jsx'
import DevbotHome from './DevbotHome.jsx'
import TalentOverview from './TalentOverview.jsx'
import Settings from './Settings.jsx'
import Status from './Status.jsx'
import MyAccount from './MyAccount.jsx'
import CommandCenter from './CommandCenter.jsx'
import JobFlow from './JobFlow.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <CommandCenter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/generator" element={<App />} />
          <Route path="/job-center" element={<JobCenter />} />
          <Route path="/jobs/new" element={<JobFlow />} />
          <Route path="/crew" element={<CrewManagement />} />
          <Route path="/crew/management" element={<CrewManagement />} />
          <Route path="/agents" element={<AgentsOverview />} />
          <Route path="/agents/new" element={<NewCrewMember />} />
          <Route path="/training" element={<TrainingHub />} />
          <Route path="/training/management" element={<TrainingManagement />} />
          <Route path="/approvals" element={<ApprovalDashboard />} />
          <Route path="/hr" element={<HRDashboard />} />
          <Route path="/hr/improvements" element={<HRImprovements />} />
          <Route path="/explainer/how-it-works" element={<ExplainerHowItWorks />} />
          <Route path="/explainer/persona" element={<ExplainerPersona />} />
          <Route path="/explainer/crew" element={<ExplainerCrew />} />
          <Route path="/devbot" element={<DevbotHome />} />
          <Route path="/hiring" element={<HiringHall onHire={() => {}} />} />
          <Route path="/talents" element={<TalentOverview />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/status" element={<Status />} />
          <Route path="/my-account" element={<MyAccount />} />
          <Route path="/devbot/dave" element={<DaveDevConsole />} />
        </Routes>
      </CommandCenter>
    </BrowserRouter>
  </React.StrictMode>,
)
