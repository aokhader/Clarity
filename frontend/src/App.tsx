import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { MatterPage } from '@/pages/firm/MatterPage'
import { ProviderPage } from '@/pages/provider/ProviderPage'

// Two route trees: the firm view (Track B) and the provider view (Track C).
const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/matters/:matterId', element: <MatterPage /> },
  { path: '/p/:token', element: <ProviderPage /> },
  { path: '*', element: <NotFoundPage /> },
])

export function App() {
  return <RouterProvider router={router} />
}
