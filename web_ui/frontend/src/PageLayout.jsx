import Sidebar from './Sidebar'

const SIZE_CLASS = {
  none: '',
  narrow: 'max-w-4xl mx-auto',
  medium: 'max-w-5xl mx-auto',
  wide: 'max-w-6xl mx-auto',
}

export default function PageLayout({
  children,
  variant = 'default',
  size = 'none',
  padded = false,
  className = '',
}) {
  const classes = []

  if (variant === 'inner') {
    classes.push('main-content', 'inner-container')
  }

  if (size in SIZE_CLASS && SIZE_CLASS[size]) {
    classes.push(SIZE_CLASS[size])
  }

  if (padded) {
    classes.push('px-4', 'py-8')
  }

  if (className) {
    classes.push(className)
  }

  const wrapperClassName = classes.join(' ').trim()

  return (
    <div className="dashboard-container">
      <Sidebar />
      <main className="content-area">
        {wrapperClassName ? <div className={wrapperClassName}>{children}</div> : children}
      </main>
    </div>
  )
}
