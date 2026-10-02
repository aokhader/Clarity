import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

import './index.css'

// Data changes only when a sync or digest runs, so cached responses stay fresh for a while.
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '*', element: <NotFoundPage /> },
])

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element in index.html')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
