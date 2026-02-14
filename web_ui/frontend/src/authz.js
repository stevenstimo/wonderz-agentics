export function extractRole(user) {
  const role =
    user?.app_metadata?.role ||
    user?.user_metadata?.role ||
    user?.user_metadata?.app_role ||
    'member'

  return String(role).toLowerCase()
}

export function isAdmin(role) {
  return role === 'admin' || role === 'super_admin'
}

export function isSuperAdmin(role) {
  return role === 'super_admin'
}
