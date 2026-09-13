import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, clearToken } from '../api'

function RecommendationCard({ rec, onFavorite }) {
  return (
    <div className="bg-white border border-amber-200 rounded-xl p-3 mt-2 shadow-sm">
      <div className="flex justify-between items-start">
        <h3 className="font-semibold text-amber-800">{rec.name}</h3>
        <span className="text-sm font-bold text-gray-700">${rec.price.toFixed(2)}</span>
      </div>
      <p className="text-sm text-gray-600">{rec.description}</p>
      <p className="text-xs text-amber-700 mt-1 italic">Why: {rec.reason}</p>
      <button
        onClick={() => onFavorite(rec.name)}
        className="text-xs text-amber-600 hover:text-amber-800 mt-1"
      >
        ♥ Save to favorites
      </button>
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [menu, setMenu] = useState([])
  const bottomRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([api.history(), api.menu()])
      .then(([history, menuItems]) => {
        setMessages(history.map((m) => ({ role: m.role, content: m.content })))
        setMenu(menuItems)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  async function send(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setBusy(true)
    try {
      const res = await api.chat(text)
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: res.reply, recommendations: res.recommendations },
      ])
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: `⚠️ ${err.message}` }])
    } finally {
      setBusy(false)
    }
  }

  async function favoriteByName(name) {
    const item = menu.find((i) => i.name === name)
    if (!item) return
    try {
      await api.addFavorite(item.id)
    } catch {
      /* already favorited */
    }
  }

  function logout() {
    clearToken()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col">
      <header className="bg-white shadow px-4 py-3 flex justify-between items-center">
        <h1 className="font-bold text-amber-800">🍹 Drink Bot</h1>
        <nav className="flex gap-4 text-sm">
          <Link to="/profile" className="text-amber-700 hover:underline">Profile</Link>
          <button onClick={logout} className="text-gray-500 hover:underline">Log out</button>
        </nav>
      </header>

      <main className="flex-1 overflow-y-auto p-4 max-w-2xl w-full mx-auto">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} mb-3`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                m.role === 'user'
                  ? 'bg-amber-600 text-white rounded-br-sm'
                  : 'bg-white shadow text-gray-800 rounded-bl-sm'
              }`}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.recommendations?.map((rec) => (
                <RecommendationCard key={rec.name} rec={rec} onFavorite={favoriteByName} />
              ))}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start mb-3">
            <div className="bg-white shadow rounded-2xl px-4 py-2 text-gray-400 animate-pulse">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      <form onSubmit={send} className="bg-white border-t p-3">
        <div className="max-w-2xl mx-auto flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. I want something refreshing and not too sweet"
            className="flex-1 border border-gray-300 rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-semibold px-5 rounded-full transition"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
