import { useEffect, useState } from 'react'

export function InlineEditField({ value, onSave, label }) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!isEditing) {
      setEditValue(value || '')
    }
  }, [value, isEditing])

  async function handleSave() {
    if (editValue.trim() === value) {
      setIsEditing(false)
      return
    }
    try {
      setSaving(true)
      setError(null)
      await onSave(editValue.trim())
      setIsEditing(false)
    } catch (err) {
      setError(err.message || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (isEditing) {
    return (
      <div className="flex flex-col gap-2">
        {error && <div className="text-xs text-red-600">{error}</div>}
        <div className="flex items-center gap-2">
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSave()
            if (e.key === 'Escape') setIsEditing(false)
          }}
          className="border rounded px-2 py-1 text-sm"
          autoFocus
        />
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="text-green-600 hover:text-green-800 text-sm font-medium disabled:opacity-50"
        >
          Save
        </button>
        <button
          type="button"
          onClick={() => setIsEditing(false)}
          className="text-red-600 hover:text-red-800 text-sm font-medium"
        >
          Cancel
        </button>
        </div>
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={() => setIsEditing(true)}
      className="cursor-pointer hover:bg-gray-50 px-2 py-1 rounded inline-flex items-center gap-2"
    >
      <span className="text-sm text-gray-500">{label}:</span>
      <span className="font-medium text-gray-900">{value}</span>
      <span className="text-gray-400 text-xs">edit</span>
    </button>
  )
}
