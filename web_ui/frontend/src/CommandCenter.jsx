import TopHeader from './TopHeader.jsx'

export default function CommandCenter({ children }) {
  return (
    <>
      <TopHeader />
      <div className="app-shell command-center-shell">{children}</div>
    </>
  )
}
