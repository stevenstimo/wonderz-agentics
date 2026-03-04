import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export function TokenUsageChart({ data, labelKey = 'label' }) {
  const safeData = Array.isArray(data) ? data : []
  const xKey = safeData.some((item) => Object.prototype.hasOwnProperty.call(item, labelKey))
    ? labelKey
    : 'agent'

  if (safeData.length === 0) {
    return (
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Token Usage</h3>
        <div className="text-sm text-gray-500">No token usage data available yet.</div>
      </div>
    )
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h3 className="text-lg font-semibold mb-4">Token Usage</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={safeData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis tickFormatter={(value) => `${(value / 1000).toFixed(0)}K`} />
          <Tooltip formatter={(value) => `${Number(value).toLocaleString()} tokens`} />
          <Bar dataKey="tokens" fill="#3b82f6" name="Tokens Used" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
