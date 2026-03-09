import HiringHall from './HiringHall.jsx';
import DaveDevConsole from './DaveDevConsole.jsx';
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

import App from './App.jsx'
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
import TalentOverview from './TalentOverview.jsx'
import Settings from './Settings.jsx'
import Status from './Status.jsx'
import MyAccount from './MyAccount.jsx'
import LoginPage from './LoginPage.jsx'
import CommandCenter from './CommandCenter.jsx'
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
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <CommandCenter>
        <Routes>
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
          <Route path="/devbot" element={<DevbotHome />} />
          <Route path="/hiring" element={<HiringHall onHire={() => {}} />} />
          <Route path="/talents" element={<TalentOverview />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/status" element={<Status />} />
          <Route path="/my-account" element={<MyAccount />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/devbot/dave" element={<DaveDevConsole />} />
        </Routes>
      </CommandCenter>
    </BrowserRouter>
  </React.StrictMode>,
)
