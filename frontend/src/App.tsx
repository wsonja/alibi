/**
 * App — the layout every route renders inside: room backdrop, skip link, the screen (<Outlet/>), toasts,
 * and the aria-live region that receives every dialogue line and event (DESIGN §8).
 * The a11y <html data-*> attributes are applied by the UI store at module load and on every change.
 */
import { Component, Suspense, type ErrorInfo, type ReactNode } from 'react'
import { Outlet, ScrollRestoration } from 'react-router-dom'
import { RoomBackdrop } from '@/components/common/RoomBackdrop'
import { Toaster } from '@/components/common/Toast'
import { useGame } from '@/store/game'
import { useUI } from '@/store/ui'

class ScreenErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[screen] render error', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="screen">
          <section className="parchment" role="alert" style={{ maxWidth: 640, margin: '40px auto' }}>
            <h1 className="display ink" style={{ fontSize: 18, marginTop: 0 }}>
              The lamp went out
            </h1>
            <p>Something in this screen failed to render. Reload the page to relight it.</p>
            <pre className="mono ink-soft" style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
              {this.state.error.message}
            </pre>
            <button type="button" className="btn btn-red" onClick={() => window.location.reload()}>
              Reload
            </button>
          </section>
        </div>
      )
    }
    return this.props.children
  }
}

function LiveRegion() {
  const message = useGame((s) => s.liveMessage)
  const verbose = useUI((s) => s.a11y.screenReader)
  return (
    <div className="sr-only" aria-live={verbose ? 'assertive' : 'polite'} aria-atomic="true" role="status" id="live-region">
      {message}
    </div>
  )
}

function ScreenFallback() {
  return (
    <div className="screen" aria-busy="true">
      <div className="lacquer mono muted" style={{ maxWidth: 420, margin: '60px auto', textAlign: 'center' }}>
        Lighting the lamps…
      </div>
    </div>
  )
}

export function App() {
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <RoomBackdrop />
      <main id="main" tabIndex={-1}>
        <ScreenErrorBoundary>
          <Suspense fallback={<ScreenFallback />}>
            <Outlet />
          </Suspense>
        </ScreenErrorBoundary>
      </main>
      <Toaster />
      <LiveRegion />
      <ScrollRestoration />
    </>
  )
}

export default App
