import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'

import App from './App.jsx'
import RequireAuth from './RequireAuth.jsx'
import CommandCenter from './CommandCenter.jsx'
import LoginPage from './LoginPage.jsx'
import HRImprovements from './HRImprovements.jsx'
import CrewManagement from './CrewManagement.jsx'
import TrainingManagement from './TrainingManagement.jsx'
import ApprovalDashboard from './ApprovalDashboard.jsx'
import JobCenter from './JobCenter.jsx'
import AgentsOverview from './AgentsOverview.jsx'
import AgentDetail from './AgentDetail.jsx'
import NewCrewMember from './NewCrewMember.jsx'
import ExplainerHowItWorks from './ExplainerHowItWorks.jsx'
import ExplainerPersona from './ExplainerPersona.jsx'
import ExplainerCrew from './ExplainerCrew.jsx'
import DeveloperBot from './DeveloperBot.jsx'
import DevbotHome from './DevbotHome.jsx'
import DaveDevConsole from './DaveDevConsole.jsx'
import Newbies from './Newbies.jsx'
import NewbieDetail from './NewbieDetail.jsx'
import Settings from './Settings.jsx'
import ApiKeys from './ApiKeys.jsx'
import Integrations from './Integrations.jsx'
import Status from './Status.jsx'
import MyAccount from './MyAccount.jsx'
import HiringHall from './HiringHall.jsx'
import JobSplitView from './JobSplitView.jsx'
import NewJob from './NewJob.jsx'
import SkillsLibrary from './SkillsLibrary.jsx'
import MissionControl from './MissionControl.jsx'
import HRFeedback from './HRFeedback.jsx'
import PersonalProjects from './PersonalProjects.jsx'
import WorkTeamOrg from './WorkTeamOrg.jsx'
import Study from './Study.jsx'
import ProductManagement from './ProductManagement.jsx'
import AgentInbox from './AgentInbox.jsx'
import SEOTool from './SEOTool.jsx'

import './index.css'

function AuthenticatedLayout() {
  return (
    <RequireAuth>
      <CommandCenter>
        <Outlet />
      </CommandCenter>
    </RequireAuth>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AuthenticatedLayout />}>
          <Route path="/" element={<App />} />
          <Route path="/dashboard" element={<App />} />
          <Route path="/job-center" element={<JobCenter />} />
          <Route path="/mission-control" element={<MissionControl />} />
          <Route path="/jobs/new" element={<NewJob />} />
          <Route path="/jobs/:jobId" element={<JobSplitView />} />
          <Route path="/crew" element={<CrewManagement />} />
          <Route path="/crew/management" element={<CrewManagement />} />
          <Route path="/agents" element={<AgentsOverview />} />
          <Route path="/agents/new" element={<NewCrewMember />} />
          <Route path="/agents/:agentId" element={<AgentDetail />} />
          <Route path="/agents/:agentId/edit" element={<AgentDetail />} />
          <Route path="/training" element={<TrainingManagement />} />
          <Route path="/training/management" element={<TrainingManagement />} />
          <Route path="/skills-library" element={<SkillsLibrary />} />
          <Route path="/approvals" element={<ApprovalDashboard />} />
          <Route path="/hr-feedback" element={<HRFeedback />} />
          <Route path="/hr/improvements" element={<HRImprovements />} />
          <Route path="/explainer" element={<Navigate to="/explainer/how-it-works" replace />} />
          <Route path="/explainer/how-it-works" element={<ExplainerHowItWorks />} />
          <Route path="/explainer/persona" element={<ExplainerPersona />} />
          <Route path="/explainer/crew" element={<ExplainerCrew />} />
          <Route path="/personal-projects" element={<PersonalProjects />} />
          <Route path="/work-team" element={<WorkTeamOrg />} />
          <Route path="/study" element={<Study />} />
          <Route path="/product-management" element={<ProductManagement />} />
          <Route path="/inbox" element={<AgentInbox />} />
          <Route path="/seo" element={<SEOTool />} />
          <Route path="/devbot" element={<DevbotHome />} />
          <Route path="/hiring" element={<HiringHall onHire={() => {}} />} />
          <Route path="/newbies" element={<Newbies />} />
          <Route path="/newbies/:newbieId" element={<NewbieDetail />} />
          <Route path="/talents" element={<Navigate to="/newbies" replace />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/settings/api-keys" element={<ApiKeys />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/status" element={<Status />} />
          <Route path="/my-account" element={<MyAccount />} />
          <Route path="/devbot/dave" element={<DaveDevConsole />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
