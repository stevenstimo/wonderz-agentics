import TopHeader from './TopHeader.jsx'
import Sidebar from './Sidebar.jsx'
import DebugChat from './DebugChat.jsx'

export default function CommandCenter({ children }) {
  return (
    <>
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar — full height on desktop; on mobile: overlay via Sidebar's fixed positioning */}
        <aside className="w-0 flex-shrink-0 overflow-visible lg:w-56 lg:overflow-y-auto lg:overflow-x-hidden h-full lg:h-full z-30">
          <Sidebar />
        </aside>
        {/* Right column — topbar + content */}
        <div className="flex flex-col flex-1 overflow-hidden min-w-0">
          <header className="h-14 flex-shrink-0 border-b border-slate-200 bg-white flex items-center z-20">
            <TopHeader />
          </header>
          <main className="flex-1 overflow-y-auto bg-slate-50 min-h-0">
            {children}
          </main>
        </div>
      </div>
      <DebugChat />
    </>
  )
}
