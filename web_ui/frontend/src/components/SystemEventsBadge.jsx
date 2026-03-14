import { useEffect, useState } from 'react'
import { apiFetch } from '../apiClient'

export default function SystemEventsBadge() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const res = await apiFetch('/api/system-events?unresolved_only=true&limit=50')
        if (!res.ok) return
        const data = await res.json()
        setCount(data.count ?? 0)
      } catch {
        setCount(0)
      }
    }

    fetchCount()
    const interval = setInterval(fetchCount, 30000)
    return () => clearInterval(interval)
  }, [])

  if (count === 0) return null

  return (
    <span
      className="flex-shrink-0 min-w-[1.25rem] h-5 px-1.5 rounded-full text-white text-xs font-medium flex items-center justify-center bg-amber-500"
      title={`${count} openstaande platform-issues`}
    >
      {count > 99 ? '99+' : count}
    </span>
  )
}
