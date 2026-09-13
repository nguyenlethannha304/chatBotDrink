import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './api'
import Login from './pages/Login'
import Chat from './pages/Chat'
import Profile from './pages/Profile'

function RequireAuth({ children }) {
  return getToken() ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/chat" element={<RequireAuth><Chat /></RequireAuth>} />
      <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
