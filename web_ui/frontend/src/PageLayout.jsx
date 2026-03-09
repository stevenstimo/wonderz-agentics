const SIZE_CLASS = {
  none: '',
  narrow: 'max-w-4xl mx-auto',
  medium: 'max-w-5xl mx-auto',
  wide: 'max-w-7xl mx-auto',
}

export default function PageLayout({
  children,
  variant = 'default',
  size = 'wide',
  padded = true,
  className = '',
}) {
  const sizeClass = size in SIZE_CLASS ? SIZE_CLASS[size] : SIZE_CLASS.wide
  const paddingClass = padded ? 'p-8' : ''
  const wrapperClass = [sizeClass, paddingClass, className].filter(Boolean).join(' ')

  return (
    <div className="min-h-full w-full">
      {wrapperClass ? (
        <div className={wrapperClass}>{children}</div>
      ) : (
        children
      )}
    </div>
  )
}
