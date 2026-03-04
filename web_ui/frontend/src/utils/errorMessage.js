export const getErrorMessage = (err) => {
  if (!err) return ''
  if (typeof err === 'string') return err
  if (err.detail) {
    if (Array.isArray(err.detail)) return err.detail.map(e => e.msg || JSON.stringify(e)).join(', ')
    return String(err.detail)
  }
  if (err.message) return err.message
  return JSON.stringify(err)
}
