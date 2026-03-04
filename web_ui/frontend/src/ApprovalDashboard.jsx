import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Clock, RefreshCw, Loader } from 'lucide-react'
import PageLayout from './PageLayout';
import { ToastContainer, useToast } from './Toast'

export default function ApprovalDashboard() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(false)
  const [decisionLoading, setDecisionLoading] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('pending')
  const [notes, setNotes] = useState({})
  const toast = useToast()

  const fetchApprovals = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/ceo/approvals`)
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to fetch approvals')
      }
      const data = await res.json()
      setApprovals(Array.isArray(data) ? data : [])
    } catch (err) {
      const errorMsg = err.message || 'Failed to load approvals'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
  }, [])

  const handleDecision = async (approval_id, approved) => {
    setDecisionLoading(approval_id)
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/ceo/approval/${approval_id}/decide?approved=${approved}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note: notes[approval_id] || '' })
        }
      )
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to process decision')
      }
      
      const action = approved ? 'approved' : 'rejected'
      toast.success(`Request ${action} successfully`)
      setNotes(prev => ({ ...prev, [approval_id]: '' }))
      setError(null)
      fetchApprovals()
    } catch (err) {
      const errorMsg = err.message || 'Failed to process decision'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setDecisionLoading(null)
    }
  }

  const filtered = approvals.filter(a => filter === 'all' || a.status === filter)

  const getIcon = (status) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="w-5 h-5 text-green-600" />
      case 'rejected':
        return <XCircle className="w-5 h-5 text-red-600" />
      default:
        return <Clock className="w-5 h-5 text-yellow-600" />
    }
  }

  const getTypeLabel = (type) => {
    switch (type) {
      case 'training':
        return 'Training Request'
      case 'resource':
        return 'Resource Request'
      case 'promotion':
        return 'Promotion'
      case 'critical_action':
        return 'Critical Action'
      default:
        return type
    }
  }

  const formatCompletion = (approval) => {
    const completedAt = approval.details?.training_completed_at
    if (!completedAt) {
      return null
    }
    const dateLabel = new Date(completedAt).toLocaleDateString()
    return `Training completed: ${dateLabel}`
  }

  return (
    <PageLayout size="wide" padded>
          <div className="panel-card mb-8">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <h2 className="page-title">Safety Gate</h2>
                <p className="page-subtitle">Approve high-impact changes and training requests.</p>
              </div>
              <button
                onClick={fetchApprovals}
                className="btn-manage gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            <div className="mt-6 flex gap-2">
              {['pending', 'approved', 'rejected', 'completed', 'all'].map(status => (
                <button
                  key={status}
                  onClick={() => setFilter(status)}
                  className={`px-3 py-1 text-xs font-medium rounded-full transition ${
                    filter === status
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                  {status !== 'all' && ` (${approvals.filter(a => a.status === status).length})`}
                </button>
              ))}
            </div>
          </div>

          <div className="panel-card">
            <h3 className="text-lg font-semibold mb-6 text-gray-800">
              Pending Approvals ({filtered.length})
            </h3>

            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader className="w-5 h-5 animate-spin text-indigo-600 mr-2" />
                <span className="text-sm text-gray-500">Loading approvals...</span>
              </div>
            )}
            {!loading && filtered.length === 0 && (
              <div className="text-sm text-gray-500">
                {filter === 'pending' 
                  ? 'No pending approvals at the moment.' 
                  : `No ${filter} approvals found.`}
              </div>
            )}

            <div className="space-y-3">
              {filtered.map(approval => (
                <div
                  key={approval.id}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      {getIcon(approval.status)}
                      <div className="flex-1">
                        <div className="font-semibold text-gray-800">
                          {getTypeLabel(approval.request_type)}
                        </div>
                        {approval.details && (
                          <div className="text-sm text-gray-600 mt-1">
                            {approval.details.agent && `Agent: ${approval.details.agent}`}
                            {approval.details.url && `\nURL: ${approval.details.url}`}
                            {approval.details.session_id && `\nSession: ${approval.details.session_id}`}
                          </div>
                        )}
                        {approval.details?.decision_note && (
                          <div className="mt-2 text-xs text-gray-500">
                            Note: {approval.details.decision_note}
                          </div>
                        )}
                        {approval.status === 'completed' && formatCompletion(approval) && (
                          <div className="mt-2 text-xs text-green-700">
                            {formatCompletion(approval)}
                          </div>
                        )}
                        <div className="text-xs text-gray-400 mt-2">
                          {approval.requested_at 
                            ? `Requested: ${new Date(approval.requested_at).toLocaleDateString()}`
                            : 'No date'}
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <span
                        className={
                          approval.status === 'pending'
                            ? 'badge-approval'
                            : `text-xs font-semibold px-2 py-1 rounded-full ${
                                approval.status === 'approved'
                                  ? 'bg-green-100 text-green-800'
                                  : approval.status === 'completed'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-red-100 text-red-800'
                              }`
                        }
                      >
                        {approval.status}
                      </span>
                      {approval.status === 'pending' && (
                        <div className="flex gap-1">
                          <input
                            type="text"
                            value={notes[approval.id] || ''}
                            onChange={(e) => setNotes(prev => ({ ...prev, [approval.id]: e.target.value }))}
                            placeholder="Optional note"
                            className="px-2 py-1 text-xs border rounded w-40"
                          />
                          <button
                            onClick={() => handleDecision(approval.id, true)}
                            disabled={decisionLoading !== null}
                            className="flex items-center gap-1 px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {decisionLoading === approval.id ? (
                              <Loader className="w-3 h-3 animate-spin" />
                            ) : (
                              <CheckCircle className="w-3 h-3" />
                            )}
                            Approve
                          </button>
                          <button
                            onClick={() => handleDecision(approval.id, false)}
                            disabled={decisionLoading !== null}
                            className="flex items-center gap-1 px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {decisionLoading === approval.id ? (
                              <Loader className="w-3 h-3 animate-spin" />
                            ) : (
                              <XCircle className="w-3 h-3" />
                            )}
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
      <ToastContainer toasts={toast.toasts} onRemove={toast.removeToast} />
    </PageLayout>
  )
}
