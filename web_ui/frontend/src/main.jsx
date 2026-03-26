import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      gcTime: 5 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

import RequireAuth from './RequireAuth.jsx'
import CommandCenter from './CommandCenter.jsx'
import LoginPage from './LoginPage.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { RouteErrorBoundary } from './components/RouteErrorBoundary.jsx'

import './index.css'

// Route-level lazy loading (LoginPage and RequireAuth stay eager per spec)
const App = lazy(() => import('./App.jsx'))
const HRImprovements = lazy(() => import('./HRImprovements.jsx'))
const CrewManagement = lazy(() => import('./CrewManagement.jsx'))
const TrainingManagement = lazy(() => import('./TrainingManagement.jsx'))
const ApprovalDashboard = lazy(() => import('./ApprovalDashboard.jsx'))
const JobCenter = lazy(() => import('./JobCenter.jsx'))
const AgentsOverview = lazy(() => import('./AgentsOverview.jsx'))
const AgentDetail = lazy(() => import('./AgentDetail.jsx'))
const NewCrewMember = lazy(() => import('./NewCrewMember.jsx'))
const ExplainerHowItWorks = lazy(() => import('./ExplainerHowItWorks.jsx'))
const ExplainerPersona = lazy(() => import('./ExplainerPersona.jsx'))
const ExplainerCrew = lazy(() => import('./ExplainerCrew.jsx'))
const DevbotHome = lazy(() => import('./DevbotHome.jsx'))
const DaveDevConsole = lazy(() => import('./DaveDevConsole.jsx'))
const Newbies = lazy(() => import('./Newbies.jsx'))
const NewbieDetail = lazy(() => import('./NewbieDetail.jsx'))
const Settings = lazy(() => import('./Settings.jsx'))
const ApiKeys = lazy(() => import('./ApiKeys.jsx'))
const Integrations = lazy(() => import('./Integrations.jsx'))
const ClientsOverview = lazy(() => import('./ClientsOverview.jsx'))
const ClientsNew = lazy(() => import('./ClientsNew.jsx'))
const ClientDetailLayout = lazy(() => import('./ClientDetailLayout.jsx'))
const Status = lazy(() => import('./Status.jsx'))
const SystemEventsPage = lazy(() => import('./pages/SystemEventsPage.jsx'))
const MyAccount = lazy(() => import('./MyAccount.jsx'))
const JobSplitView = lazy(() => import('./JobSplitView.jsx'))
const NewJob = lazy(() => import('./NewJob.jsx'))
const MissionControl = lazy(() => import('./MissionControl.jsx'))
const HRDashboard = lazy(() => import('./HRDashboard.jsx'))
const TrainingRequestsTabContent = lazy(() => import('./HRDashboard.jsx').then(m => ({ default: m.TrainingRequestsTabContent })))
const TrainingSuggestionsTabContent = lazy(() => import('./HRDashboard.jsx').then(m => ({ default: m.TrainingSuggestionsTabContent })))
const BlockedJobsTabContent = lazy(() => import('./HRDashboard.jsx').then(m => ({ default: m.BlockedJobsTabContent })))
const IssueDetail = lazy(() => import('./pages/IssueDetail.jsx'))
const HRApprovalPage = lazy(() => import('./pages/HRApprovalPage.jsx'))
const CFODashboard = lazy(() => import('./CFODashboard.jsx'))
const CAODashboard = lazy(() => import('./CAODashboard.jsx'))
const PersonalProjects = lazy(() => import('./PersonalProjects.jsx'))
const WorkTeamOrg = lazy(() => import('./WorkTeamOrg.jsx'))
const Study = lazy(() => import('./Study.jsx'))
const ProductManagement = lazy(() => import('./ProductManagement.jsx'))
const AgentInbox = lazy(() => import('./AgentInbox.jsx'))
const EmailInbox = lazy(() => import('./EmailInbox.jsx'))
const SEOTool = lazy(() => import('./SEOTool.jsx'))
const SEOLanding = lazy(() => import('./SEOLanding.jsx'))
const KnowledgeLibrary = lazy(() => import('./KnowledgeLibrary.jsx'))
const KnowledgeDetail = lazy(() => import('./KnowledgeDetail.jsx'))
const KnowledgeUpload = lazy(() => import('./KnowledgeUpload.jsx'))
const SkillFactory = lazy(() => import('./SkillFactory.jsx'))
const NewSkillForm = lazy(() => import('./pages/NewSkillForm.jsx'))
const ClientIntelligence = lazy(() => import('./ClientIntelligence.jsx'))
const KnowledgeGovernance = lazy(() => import('./KnowledgeGovernance.jsx'))
const UsersPage = lazy(() => import('./pages/UsersPage.jsx'))
const ClientDashboardPage = lazy(() => import('./ClientDashboardPage.jsx'))
const ClientIntegrations = lazy(() => import('./ClientIntegrations.jsx'))
const ClientKnowledge = lazy(() => import('./ClientKnowledge.jsx'))

function AuthenticatedLayout() {
  return (
    <RequireAuth>
      <CommandCenter>
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </CommandCenter>
    </RequireAuth>
  )
}

const RouteFallback = () => (
  <div className="flex items-center justify-center min-h-[200px] text-sm text-gray-500">
    Laden…
  </div>
)

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/seo" element={<Suspense fallback={<RouteFallback />}><SEOLanding /></Suspense>} />
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
              <Route path="/knowledge/upload" element={<KnowledgeUpload />} />
              <Route path="/knowledge/new" element={<Navigate to="/knowledge/upload" replace />} />
              <Route path="/knowledge/skills" element={<SkillFactory />} />
              <Route path="/knowledge/skills/new" element={<NewSkillForm />} />
              <Route path="/knowledge/clients" element={<ClientIntelligence />} />
              <Route path="/knowledge/clients/:client_slug" element={<RouteErrorBoundary paramKey="client_slug"><ClientIntelligence /></RouteErrorBoundary>} />
              <Route path="/knowledge/governance" element={<KnowledgeGovernance />} />
              <Route path="/knowledge/:id/edit" element={<KnowledgeUpload />} />
              <Route path="/knowledge/:id" element={<RouteErrorBoundary paramKey="id"><KnowledgeDetail /></RouteErrorBoundary>} />
              <Route path="/knowledge" element={<KnowledgeLibrary />} />
              <Route path="/approvals" element={<ApprovalDashboard />} />
              <Route path="/hr" element={<HRDashboard />}>
                <Route path="training-requests" element={<TrainingRequestsTabContent />} />
                <Route path="training-suggestions" element={<TrainingSuggestionsTabContent />} />
                <Route path="blocked-jobs" element={<BlockedJobsTabContent />} />
                <Route path="improvements" element={<HRImprovements />} />
              </Route>
              <Route path="/hr/approval" element={<HRApprovalPage />} />
              <Route path="/cfo" element={<CFODashboard />} />
              <Route path="/cao" element={<CAODashboard />} />
              <Route path="/hr/issues/:pointId" element={<IssueDetail />} />
              <Route path="/improvements" element={<Navigate to="/hr/improvements" replace />} />
              <Route path="/explainer" element={<Navigate to="/explainer/how-it-works" replace />} />
              <Route path="/explainer/how-it-works" element={<ExplainerHowItWorks />} />
              <Route path="/explainer/persona" element={<ExplainerPersona />} />
              <Route path="/explainer/crew" element={<ExplainerCrew />} />
              <Route path="/personal-projects" element={<PersonalProjects />} />
              <Route path="/work-team" element={<WorkTeamOrg />} />
              <Route path="/study" element={<Study />} />
              <Route path="/product-management" element={<ProductManagement />} />
              <Route path="/inbox" element={<EmailInbox />} />
              <Route path="/agent-inbox" element={<AgentInbox />} />
              <Route path="/seo/tool" element={<SEOTool />} />
              <Route path="/devbot" element={<DevbotHome />} />
              <Route path="/newbies" element={<Newbies />} />
              <Route path="/newbies/:newbieId" element={<RouteErrorBoundary paramKey="newbieId"><NewbieDetail /></RouteErrorBoundary>} />
              <Route path="/talents" element={<Navigate to="/newbies" replace />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/settings/users" element={<UsersPage />} />
              <Route path="/settings/api-keys" element={<ApiKeys />} />
              <Route path="/integrations" element={<Integrations />} />
              <Route path="/clients" element={<ClientsOverview />} />
              <Route path="/clients/new" element={<ClientsNew />} />
              <Route path="/clients/:slug" element={<RouteErrorBoundary paramKey="slug"><ClientDetailLayout /></RouteErrorBoundary>}>
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<ClientDashboardPage />} />
                <Route path="integrations" element={<ClientIntegrations />} />
                <Route path="knowledge" element={<ClientKnowledge />} />
              </Route>
              <Route path="/status" element={<Status />} />
              <Route path="/system-events" element={<SystemEventsPage />} />
              <Route path="/my-account" element={<MyAccount />} />
              <Route path="/devbot/dave" element={<DaveDevConsole />} />
            </Route>
        </Routes>
      </BrowserRouter>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
