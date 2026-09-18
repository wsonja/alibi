/**
 * Routes (PLAN §10.1):
 *   /                      NewCase
 *   /game/:id/briefing     Briefing
 *   /game/:id              Investigation   (lazy — the Investigation lane's bundle is the heaviest)
 *   /game/:id/debrief      Debrief         (lazy — React Flow)
 *   /archive               Archive         (lazy)
 */
import { lazy } from 'react'
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import App from './App'
import Briefing from './screens/Briefing'
import NewCase from './screens/NewCase'

const Investigation = lazy(() => import('./screens/Investigation'))
const Debrief = lazy(() => import('./screens/Debrief'))
const Archive = lazy(() => import('./screens/Archive'))

function NotFound() {
  return (
    <div className="screen">
      <section className="parchment" style={{ maxWidth: 560, margin: '40px auto' }}>
        <h1 className="display ink" style={{ fontSize: 18, marginTop: 0 }}>
          No such room
        </h1>
        <p>That door leads nowhere. The house has a front hall, a briefing, an investigation and an archive.</p>
        <a href="/" className="btn btn-red">
          Back to the front hall
        </a>
      </section>
    </div>
  )
}

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <NewCase /> },
      { path: 'game/:id/briefing', element: <Briefing /> },
      { path: 'game/:id', element: <Investigation /> },
      { path: 'game/:id/debrief', element: <Debrief /> },
      { path: 'archive', element: <Archive /> },
      { path: 'new', element: <Navigate to="/" replace /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]

export const router = createBrowserRouter(routes)

export default router
