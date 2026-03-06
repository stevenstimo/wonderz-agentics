import Sidebar from './Sidebar'

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
    <>
      <Sidebar />
      <main className="min-h-screen bg-slate-50 w-full ml-0 lg:ml-56">
        {wrapperClass ? (
          <div className={wrapperClass}>{children}</div>
        ) : (
          children
        )}
      </main>
    </>
  )
}
