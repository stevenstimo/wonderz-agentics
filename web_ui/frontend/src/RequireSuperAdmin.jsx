import { useEffect, useState } from 'react'
import PageLayout from './PageLayout'
import { getCurrentUserRole, isSuperAdmin } from './authz'

export default function RequireSuperAdmin({ children }) {
  const [loading, setLoading] = useState(true)
  const [allowed, setAllowed] = useState(false)

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const { role } = await getCurrentUserRole()
        if (!active) {
          return
        }
        setAllowed(isSuperAdmin(role))
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    })()

    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card">Toegang controleren...</div>
      </PageLayout>
    )
  }

  if (!allowed) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card">
          <h1 className="page-title">Geen toegang</h1>
          <p className="page-subtitle">Deze pagina is alleen beschikbaar voor super admins.</p>
        </div>
      </PageLayout>
    )
  }

  return children
}
