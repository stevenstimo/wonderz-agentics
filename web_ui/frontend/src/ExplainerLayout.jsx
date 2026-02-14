import { useEffect, useMemo, useState } from 'react'
import PageLayout from './PageLayout';

const apiBase = import.meta.env.VITE_API_URL || ''

const renderMarkdown = (text) => {
  if (!text) {
    return <p className="text-slate-700">No content</p>
  }

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
      blocks.push(
        <p key={`p-${blocks.length}`} className="text-base text-slate-700 leading-relaxed mb-3">
          {trimmed}
        </p>
      )
    } else if (blocks.length > 0) {
      // Add spacing between paragraphs
      blocks.push(
        <div key={`space-${blocks.length}`} className="h-2"></div>
      )
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

  useEffect(() => {
    let active = true

    const fetchSections = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${apiBase}/api/explainer/sections`)
        if (!res.ok) {
          throw new Error('Failed to load explainer content')
        }
        const data = await res.json()
        if (!active) {
          return
        }
        setSections(Array.isArray(data.sections) ? data.sections : [])
        setMeta(data.meta || null)
      } catch (err) {
        if (!active) {
          return
        }
        setError(err.message || 'Failed to load explainer content')
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    fetchSections()
    return () => {
      active = false
    }
  }, [slug])

  const section = useMemo(
    () => sections.find((item) => item.slug === slug),
    [sections, slug]
  )

  const updatedLabel = section?.updated_at
    ? new Date(section.updated_at).toLocaleString()
    : 'Unknown'

  return (
    <PageLayout size="wide" padded className="space-y-6">
          <div className="panel-card">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h2 className="page-title">{section?.title || fallbackTitle}</h2>
                <p className="page-subtitle">
                  Live content from the backend. Updated: {updatedLabel}.
                </p>
              </div>
              {meta && (
                <div className="text-xs text-slate-400">
                  <div>Env: {meta.deploy_env}</div>
                  <div>SHA: {meta.build_sha}</div>
                </div>
              )}
            </div>
          </div>

          <div className="panel-card space-y-4">
            {loading && <p className="text-sm text-slate-500">Loading content...</p>}
            {!loading && error && (
              <p className="text-sm text-red-500">{error}</p>
            )}
            {!loading && !error && section && renderMarkdown(section.body_markdown)}
            {!loading && !error && !section && (
              <p className="text-sm text-slate-500">No content found for this section.</p>
            )}
          </div>
      </PageLayout>
  )
}
