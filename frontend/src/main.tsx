import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { AuthProvider } from './context/AuthContext'
import { ActiveProjectProvider } from './context/ActiveProjectContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <ActiveProjectProvider>
        <App />
      </ActiveProjectProvider>
    </AuthProvider>
  </StrictMode>,
)
