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
import ClientsOverview from './ClientsOverview.jsx'
import ClientsNew from './ClientsNew.jsx'
import ClientDetailLayout from './ClientDetailLayout.jsx'
import ClientDashboardPage from './ClientDashboardPage.jsx'
import ClientIntegrations from './ClientIntegrations.jsx'
import Status from './Status.jsx'
import MyAccount from './MyAccount.jsx'
import HiringHall from './HiringHall.jsx'
import JobSplitView from './JobSplitView.jsx'
import NewJob from './NewJob.jsx'
import MissionControl from './MissionControl.jsx'
import HRDashboard from './HRDashboard.jsx'
import PersonalProjects from './PersonalProjects.jsx'
import WorkTeamOrg from './WorkTeamOrg.jsx'
import Study from './Study.jsx'
import ProductManagement from './ProductManagement.jsx'
import AgentInbox from './AgentInbox.jsx'
import EmailInbox from './EmailInbox.jsx'
import SEOTool from './SEOTool.jsx'
import SEOLanding from './SEOLanding.jsx'
import KnowledgeLibrary from './KnowledgeLibrary.jsx'
import KnowledgeDetail from './KnowledgeDetail.jsx'
import KnowledgeUpload from './KnowledgeUpload.jsx'
import SkillFactory from './SkillFactory.jsx'
import ClientIntelligence from './ClientIntelligence.jsx'
import KnowledgeGovernance from './KnowledgeGovernance.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { RouteErrorBoundary } from './components/RouteErrorBoundary.jsx'

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
    <ErrorBoundary>
      <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/seo" element={<SEOLanding />} />
        <Route element={<AuthenticatedLayout />}>
          <Route path="/" element={<App />} />
          <Route path="/dashboard" element={<App />} />
          <Route path="/job-center" element={<JobCenter />} />
          <Route path="/jobs" element={<JobCenter />} />
          <Route path="/mission-control" element={<MissionControl />} />
          <Route path="/jobs/new" element={<NewJob />} />
          <Route path="/jobs/:jobId" element={<RouteErrorBoundary paramKey="jobId"><JobSplitView /></RouteErrorBoundary>} />
          <Route path="/crew" element={<CrewManagement />} />
          <Route path="/crew/management" element={<CrewManagement />} />
          <Route path="/agents" element={<AgentsOverview />} />
          <Route path="/agents/new" element={<NewCrewMember />} />
          <Route path="/agents/:agentId" element={<RouteErrorBoundary paramKey="agentId"><AgentDetail /></RouteErrorBoundary>} />
          <Route path="/agents/:agentId/edit" element={<RouteErrorBoundary paramKey="agentId"><AgentDetail /></RouteErrorBoundary>} />
          <Route path="/training" element={<TrainingManagement />} />
          <Route path="/training/management" element={<TrainingManagement />} />
          <Route path="/skills-library" element={<Navigate to="/knowledge/skills" replace />} />
          <Route path="/skills" element={<Navigate to="/knowledge/skills" replace />} />
          {/* Knowledge: statische routes vóór dynamische :id */}
          <Route path="/knowledge/upload" element={<KnowledgeUpload />} />
          <Route path="/knowledge/new" element={<Navigate to="/knowledge/upload" replace />} />
          <Route path="/knowledge/skills" element={<SkillFactory />} />
          <Route path="/knowledge/clients" element={<ClientIntelligence />} />
          <Route path="/knowledge/clients/:client_slug" element={<RouteErrorBoundary paramKey="client_slug"><ClientIntelligence /></RouteErrorBoundary>} />
          <Route path="/knowledge/governance" element={<KnowledgeGovernance />} />
          <Route path="/knowledge/:id/edit" element={<KnowledgeUpload />} />
          <Route path="/knowledge/:id" element={<RouteErrorBoundary paramKey="id"><KnowledgeDetail /></RouteErrorBoundary>} />
          <Route path="/knowledge" element={<KnowledgeLibrary />} />
          <Route path="/approvals" element={<ApprovalDashboard />} />
          <Route path="/hr" element={<HRDashboard />} />
          <Route path="/hr-feedback" element={<HRDashboard />} />
          <Route path="/hr/improvements" element={<HRImprovements />} />
          <Route path="/explainer" element={<Navigate to="/explainer/how-it-works" replace />} />
          <Route path="/explainer/how-it-works" element={<ExplainerHowItWorks />} />
          <Route path="/explainer/persona" element={<ExplainerPersona />} />
          <Route path="/explainer/crew" element={<ExplainerCrew />} />
          <Route path="/personal-projects" element={<PersonalProjects />} />
          <Route path="/work-team" element={<WorkTeamOrg />} />
          <Route path="/study" element={<Study />} />
          <Route path="/product-management" element={<ProductManagement />} />
          {/* Inbox = email inbox; agent-inbox = agent messages */}
          <Route path="/inbox" element={<EmailInbox />} />
          <Route path="/agent-inbox" element={<AgentInbox />} />
          <Route path="/seo/tool" element={<SEOTool />} />
          <Route path="/devbot" element={<DevbotHome />} />
          <Route path="/hiring" element={<HiringHall onHire={() => {}} />} />
          <Route path="/newbies" element={<Newbies />} />
          <Route path="/newbies/:newbieId" element={<RouteErrorBoundary paramKey="newbieId"><NewbieDetail /></RouteErrorBoundary>} />
          <Route path="/talents" element={<Navigate to="/newbies" replace />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/settings/api-keys" element={<ApiKeys />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/clients" element={<ClientsOverview />} />
          <Route path="/clients/new" element={<ClientsNew />} />
          <Route path="/clients/:slug" element={<RouteErrorBoundary paramKey="slug"><ClientDetailLayout /></RouteErrorBoundary>}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<ClientDashboardPage />} />
            <Route path="integrations" element={<ClientIntegrations />} />
          </Route>
          <Route path="/status" element={<Status />} />
          <Route path="/my-account" element={<MyAccount />} />
          <Route path="/devbot/dave" element={<DaveDevConsole />} />
        </Route>
      </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
)
