import { useEffect, useRef, useState } from 'react'
import { wsBase } from '../apiBase'

export function useJobWebSocket(jobId) {
  const [jobData, setJobData] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    if (!jobId) return

    const ws = new WebSocket(`${wsBase}/ws/jobs/${jobId}`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data)
        if (update?.type === 'job_update') {
          setJobData(update.data || update.job || null)
        }
      } catch (err) {
        console.error('Invalid WebSocket message:', err)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = () => {
      setConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [jobId])

  return { jobData, connected }
}
