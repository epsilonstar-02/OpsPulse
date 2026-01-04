import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Note: StrictMode removed to prevent WebSocket double-mounting issues
// In production, React doesn't have this behavior
createRoot(document.getElementById('root')).render(
  <App />,
)
