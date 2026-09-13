import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../api'

export default function Login() {
  const [mode, setMode] = useState('login')
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = mode === 'login'
        ? await api.login(phone)
        : await api.register(phone, name, address)
      setToken(res.access_token)
      navigate('/chat')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 to-orange-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <h1 className="text-3xl font-bold text-amber-800 mb-1">🍹 Drink Bot</h1>
        <p className="text-gray-500 mb-6">Your personal drink recommender</p>

        <div className="flex mb-6 rounded-lg bg-gray-100 p-1">
          {['login', 'register'].map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError('') }}
              className={`flex-1 py-2 rounded-md text-sm font-medium capitalize transition ${
                mode === m ? 'bg-white shadow text-amber-700' : 'text-gray-500'
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4">
          <input
            type="tel"
            required
            placeholder="Phone number (e.g. +14155550100)"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
          {mode === 'register' && (
            <>
              <input
                required
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
              />
              <input
                required
                placeholder="Address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
              />
            </>
          )}
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-semibold py-2 rounded-lg transition"
          >
            {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
