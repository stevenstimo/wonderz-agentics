import TopHeader from './TopHeader.jsx'
import DebugChat from './DebugChat.jsx'

export default function CommandCenter({ children }) {
  return (
    <>
      <TopHeader />
      <div className="app-shell command-center-shell">{children}</div>
      <DebugChat />
    </>
  )
}
