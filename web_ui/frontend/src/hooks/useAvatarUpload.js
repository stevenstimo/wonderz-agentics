import { useState, useCallback } from 'react'
import { supabase } from '../supabase'

const MAX_SIZE_BYTES = 2 * 1024 * 1024 // 2MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

function getExtension(file) {
  const match = file.name?.match(/\.([a-z0-9]+)$/i)
  if (match) return match[1].toLowerCase()
  const fromMime = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
  }
  return fromMime[file.type] || 'jpg'
}

/**
 * Validates file: max 2MB, must be image type.
 * @returns {{ ok: false, error: string } | { ok: true }}
 */
export function validateAvatarFile(file) {
  if (!file) return { ok: false, error: 'Geen bestand geselecteerd.' }
  if (!ALLOWED_TYPES.includes(file.type)) {
    return { ok: false, error: 'Alleen afbeeldingen (JPEG, PNG, GIF, WebP) zijn toegestaan.' }
  }
  if (file.size > MAX_SIZE_BYTES) {
    return { ok: false, error: 'Bestand mag maximaal 2 MB zijn.' }
  }
  return { ok: true }
}

/**
 * @returns {{ uploadAvatar: (file: File, userId: string) => Promise<string>, isUploading: boolean }}
 */
export function useAvatarUpload() {
  const [isUploading, setIsUploading] = useState(false)

  const uploadAvatar = useCallback(async (file, userId) => {
    const validation = validateAvatarFile(file)
    if (!validation.ok) {
      throw new Error(validation.error)
    }

    setIsUploading(true)
    try {
      const ext = getExtension(file)
      const path = `${userId}/avatar.${ext}`

      const { error: uploadError } = await supabase.storage
        .from('avatars')
        .upload(path, file, { upsert: true })

      if (uploadError) throw new Error(uploadError.message)

      const { data: urlData } = supabase.storage.from('avatars').getPublicUrl(path)
      const publicUrl = urlData?.publicUrl ?? ''

      const { error: upsertError } = await supabase.from('profiles').upsert(
        {
          id: userId,
          avatar_url: publicUrl,
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'id' }
      )

      if (upsertError) throw new Error(upsertError.message)

      await supabase.auth.updateUser({
        data: { avatar_url: publicUrl },
      })

      return publicUrl
    } finally {
      setIsUploading(false)
    }
  }, [])

  return { uploadAvatar, isUploading }
}
