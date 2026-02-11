import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App.jsx'
import HRImprovements from './HRImprovements.jsx'
import CrewManagement from './CrewManagement.jsx'
import TrainingManagement from './TrainingManagement.jsx'
import ApprovalDashboard from './ApprovalDashboard.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/crew/management" element={<CrewManagement />} />
        <Route path="/training/management" element={<TrainingManagement />} />
        <Route path="/approvals" element={<ApprovalDashboard />} />
        <Route path="/hr/improvements" element={<HRImprovements />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
