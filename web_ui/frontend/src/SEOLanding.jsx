/**
 * SEOLanding.jsx — publieke route /seo
 * Tailwind-versie van het originele ontwerp.
 * Vereist: react-router-dom
 * Font: DM Sans in index.html
 */

import { useNavigate } from 'react-router-dom'

const FEATURES = [
  {
    icon: '↑',
    title: 'Upload je keyword CSV',
    desc: 'Exporteer direct vanuit Semrush, Ahrefs of Google Search Console. Elke kolomstructuur wordt herkend.',
  },
  {
    icon: '◈',
    title: 'AI clustert & prioriteert',
    desc: 'De agent groepeert keywords op intent, zoekvolume en concurrentie. Geen handmatig sorteren meer.',
  },
  {
    icon: '↓',
    title: 'Ontvang een volledig Excel-plan',
    desc: 'Per cluster: aanbevolen URL-structuur, primair keyword, ondersteunende termen en prioriteit-score.',
  },
]

const STATS = [
  { value: '10x', label: 'sneller dan handmatig' },
  { value: '< 2 min', label: 'van CSV naar plan' },
  { value: '100%', label: 'exporteerbaar als Excel' },
]

export default function SEOLanding() {
  const navigate = useNavigate()

  return (
    <div
      className="min-h-screen relative overflow-hidden"
      style={{ background: '#0d0f14', color: '#e8eaf0', fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* Grid background */}
      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(#1e2330 1px, transparent 1px), linear-gradient(90deg, #1e2330 1px, transparent 1px)',
          backgroundSize: '40px 40px',
          opacity: 0.45,
          zIndex: 0,
        }}
      />

      {/* Header */}
      <header
        className="relative flex items-center justify-between px-10 py-4 border-b"
        style={{ borderColor: '#1e2330', background: 'rgba(13,15,20,0.85)', backdropFilter: 'blur(8px)', zIndex: 10 }}
      >
        <span className="flex items-center gap-2 text-sm font-semibold tracking-wide" style={{ color: '#e8eaf0' }}>
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ background: '#3ecf8e', boxShadow: '0 0 8px #3ecf8e' }}
          />
          AI Content Bureau
        </span>
        <button
          onClick={() => navigate('/login')}
          className="text-sm px-4 py-1.5 rounded-lg transition-colors"
          style={{ border: '1px solid #252c3d', color: '#6b7494', background: 'transparent', cursor: 'pointer' }}
        >
          Sign in
        </button>
      </header>

      {/* Main */}
      <main
        className="relative flex flex-col gap-14 mx-auto px-6 pb-20"
        style={{ maxWidth: 760, paddingTop: 80, zIndex: 10 }}
      >
        {/* Hero */}
        <section className="flex flex-col gap-5">
          {/* Badge */}
          <span className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase" style={{ color: '#6b7494' }}>
            <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: '#4f8ef7' }} />
            SEO Tool · Operations
          </span>

          <h1
            className="font-bold leading-tight m-0"
            style={{ fontSize: 'clamp(36px, 6vw, 64px)', letterSpacing: '-0.03em', color: '#e8eaf0' }}
          >
            SEO Keyword Plan
            <br />
            <span style={{ color: '#4f8ef7' }}>Generator</span>
          </h1>

          <p className="m-0 leading-relaxed" style={{ fontSize: 17, color: '#6b7494', maxWidth: 540 }}>
            Upload een keyword CSV uit Semrush of Ahrefs en ontvang binnen twee minuten een volledig,
            gestructureerd SEO-plan als Excel. Aangedreven door een gespecialiseerde AI-agent.
          </p>

          <div className="flex gap-3 flex-wrap mt-2">
            <button
              onClick={() => navigate('/seo/tool')}
              className="px-7 py-3 rounded-xl text-sm font-semibold text-white transition-opacity hover:opacity-90"
              style={{
                background: '#4f8ef7',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 0 24px rgba(79,142,247,0.2)',
                letterSpacing: '-0.01em',
              }}
            >
              Start gratis →
            </button>
            <button
              onClick={() => navigate('/login')}
              className="px-7 py-3 rounded-xl text-sm font-medium transition-colors"
              style={{ border: '1px solid #252c3d', color: '#e8eaf0', background: 'transparent', cursor: 'pointer' }}
            >
              Inloggen
            </button>
          </div>
        </section>

        {/* Stats strip */}
        <div className="flex" style={{ borderTop: '1px solid #1e2330', borderBottom: '1px solid #1e2330', padding: '28px 0' }}>
          {STATS.map((s, i) => (
            <div
              key={i}
              className="flex flex-col gap-1 flex-1 pl-6"
              style={{ borderLeft: '1px solid #1e2330' }}
            >
              <span className="font-bold" style={{ fontSize: 28, letterSpacing: '-0.03em', color: '#e8eaf0' }}>
                {s.value}
              </span>
              <span className="text-xs uppercase tracking-widest" style={{ color: '#6b7494' }}>
                {s.label}
              </span>
            </div>
          ))}
        </div>

        {/* Features */}
        <section className="flex flex-col gap-0.5">
          {FEATURES.map((f, i) => (
            <div
              key={i}
              className="flex gap-5 items-start rounded-xl mb-0.5"
              style={{
                padding: '24px 28px',
                background: '#151820',
                border: '1px solid #1e2330',
              }}
            >
              <span className="text-xl mt-0.5 min-w-7" style={{ color: '#4f8ef7' }}>
                {f.icon}
              </span>
              <div>
                <h3 className="m-0 mb-1.5 font-semibold" style={{ fontSize: 15, letterSpacing: '-0.01em', color: '#e8eaf0' }}>
                  {f.title}
                </h3>
                <p className="m-0 leading-relaxed text-sm" style={{ color: '#6b7494' }}>
                  {f.desc}
                </p>
              </div>
            </div>
          ))}
        </section>

        {/* Bottom CTA */}
        <section className="flex flex-col items-center gap-4 text-center pt-6 pb-4">
          <p className="m-0 text-sm" style={{ color: '#6b7494' }}>
            Onderdeel van het Crew Intelligent platform.
          </p>
          <button
            onClick={() => navigate('/seo/tool')}
            className="px-7 py-3 rounded-xl text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{
              background: '#4f8ef7',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 0 24px rgba(79,142,247,0.2)',
            }}
          >
            Toegang aanvragen →
          </button>
        </section>
      </main>
    </div>
  )
}
