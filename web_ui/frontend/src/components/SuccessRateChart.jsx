import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export function SuccessRateChart({ data }) {
  const safeData = Array.isArray(data) ? data : []

  if (safeData.length === 0) {
    return (
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Success Rate Trend</h3>
        <div className="text-sm text-gray-500">No trend data available yet.</div>
      </div>
    )
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h3 className="text-lg font-semibold mb-4">Success Rate Trend</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={safeData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis domain={[0, 1]} tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} />
          <Tooltip formatter={(value) => `${(value * 100).toFixed(1)}%`} />
          <Line
            type="monotone"
            dataKey="success_rate"
            stroke="#10b981"
            strokeWidth={2}
            name="Success Rate"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
