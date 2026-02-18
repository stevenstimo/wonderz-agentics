import { apiBase } from './apiBase'
import { useEffect, useMemo, useState } from 'react'
import PageLayout from './PageLayout'
import { buildAuthHeaders, getCurrentUserRole, isSuperAdmin } from './authz'


const renderMarkdown = (text) => {
  if (!text) return <p className="text-slate-700">No content</p>

  const lines = text.split('\n')
  const blocks = []
  let listItems = []

  const flushList = () => {
    if (listItems.length > 0) {
      blocks.push(
        <ul key={`list-${blocks.length}`} className="list-disc pl-6 space-y-1">
          {listItems.map((item, idx) => (
            <li key={`item-${idx}`} className="text-sm text-slate-700">{item}</li>
          ))}
        </ul>
      )
      listItems = []
    }
  }

  lines.forEach((line) => {
    const trimmed = line.trim()
    if (trimmed.startsWith('- ')) {
      listItems.push(trimmed.slice(2))
      return
    }

    flushList()

    if (trimmed.length > 0) {
      blocks.push(<p key={`p-${blocks.length}`} className="text-base text-slate-700 leading-relaxed mb-3">{trimmed}</p>)
    } else if (blocks.length > 0) {
      blocks.push(<div key={`space-${blocks.length}`} className="h-2" />)
    }
  })

  flushList()
  return blocks.length > 0 ? blocks : <p className="text-slate-700">No content</p>
}

export default function ExplainerLayout({ slug, fallbackTitle }) {
  const [sections, setSections] = useState([])
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [role, setRole] = useState('member')
  const [showEditor, setShowEditor] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [saving, setSaving] = useState(false)

  const fetchSections = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/explainer/sections`)
      if (!res.ok) throw new Error('Failed to load explainer content')
      const data = await res.json()
      setSections(Array.isArray(data.sections) ? data.sections : [])
      setMeta(data.meta || null)
    } catch (err) {
      setError(err.message || 'Failed to load explainer content')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    ;(async () => {
      try {
        const ctx = await getCurrentUserRole()
        setRole(ctx.role || 'member')
      } catch {
        setRole('member')
      }
      fetchSections()
    })()
  }, [slug])

  const section = useMemo(() => sections.find((item) => item.slug === slug), [sections, slug])
  const canEdit = isSuperAdmin(role)

  const openEditor = () => {
    setDraftTitle(section?.title || fallbackTitle)
    setDraftBody(section?.body_markdown || '')
    setShowEditor(true)
  }

  const saveSection = async () => {
    if (!canEdit) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/explainer/sections/${slug}`, {
        method: 'PUT',
        headers: await buildAuthHeaders(),
        body: JSON.stringify({ title: draftTitle, body_markdown: draftBody }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Failed to update section (${res.status})`)
      }
      setShowEditor(false)
      await fetchSections()
    } catch (err) {
      setError(err.message || 'Failed to update section')
    } finally {
      setSaving(false)
    }
  }

  const updatedLabel = section?.updated_at ? new Date(section.updated_at).toLocaleString() : 'Unknown'

  return (
    <PageLayout size="wide" padded className="space-y-6">
      <div className="panel-card">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="page-title">{section?.title || fallbackTitle}</h2>
            <p className="page-subtitle">Live content from the backend. Updated: {updatedLabel}.</p>
          </div>
          <div className="flex items-start gap-3">
            {meta && (
              <div className="text-xs text-slate-400">
                <div>Env: {meta.deploy_env}</div>
                <div>SHA: {meta.build_sha}</div>
              </div>
            )}
            {canEdit && (
              <button type="button" onClick={openEditor} className="btn-manage">Update informatie</button>
            )}
          </div>
        </div>
      </div>

      <div className="panel-card space-y-4">
        {loading && <p className="text-sm text-slate-500">Loading content...</p>}
        {!loading && error && <p className="text-sm text-red-500">{error}</p>}
        {!loading && !error && section && renderMarkdown(section.body_markdown)}
        {!loading && !error && !section && <p className="text-sm text-slate-500">No content found for this section.</p>}
      </div>

      {showEditor && (
        <div className="modal-overlay">
          <div className="modal-card space-y-3">
            <h3 className="text-xl font-bold">Update informatie</h3>
            <input className="w-full px-3 py-2 border rounded-lg" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} placeholder="Title" />
            <textarea className="w-full px-3 py-2 border rounded-lg min-h-[280px]" value={draftBody} onChange={(e) => setDraftBody(e.target.value)} placeholder="Markdown content" />
            <div className="flex gap-2">
              <button type="button" className="flex-1 px-4 py-2 border rounded-lg" onClick={() => setShowEditor(false)}>Cancel</button>
              <button type="button" className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50" onClick={saveSection} disabled={saving}>{saving ? 'Saving...' : 'Opslaan'}</button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
