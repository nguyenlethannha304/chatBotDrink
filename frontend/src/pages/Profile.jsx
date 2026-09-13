import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

function ListEditor({ label, values, onChange }) {
  const [draft, setDraft] = useState('')

  function add(e) {
    e.preventDefault()
    const v = draft.trim().toLowerCase()
    if (v && !values.includes(v)) onChange([...values, v])
    setDraft('')
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div className="flex flex-wrap gap-2 mb-2">
        {values.map((v) => (
          <span key={v} className="bg-amber-100 text-amber-800 text-sm px-2 py-1 rounded-full">
            {v}
            <button
              onClick={() => onChange(values.filter((x) => x !== v))}
              className="ml-1 text-amber-600 hover:text-red-600"
            >
              ×
            </button>
          </span>
        ))}
        {values.length === 0 && <span className="text-sm text-gray-400">none</span>}
      </div>
      <form onSubmit={add} className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add…"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
        />
        <button type="submit" className="text-sm bg-amber-600 text-white px-3 rounded-lg">Add</button>
      </form>
    </div>
  )
}

export default function Profile() {
  const [me, setMe] = useState(null)
  const [prefs, setPrefs] = useState(null)
  const [favorites, setFavorites] = useState([])
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    Promise.all([api.me(), api.preferences(), api.favorites()])
      .then(([user, preferences, favs]) => {
        setMe(user)
        setPrefs(preferences)
        setFavorites(favs)
      })
      .catch(() => {})
  }, [])

  async function save() {
    await api.updatePreferences(prefs)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  async function removeFavorite(menuItemId) {
    await api.removeFavorite(menuItemId)
    setFavorites((f) => f.filter((fav) => fav.menu_item.id !== menuItemId))
  }

  if (!me || !prefs) return <div className="min-h-screen bg-amber-50 p-8 text-gray-500">Loading…</div>

  return (
    <div className="min-h-screen bg-amber-50">
      <header className="bg-white shadow px-4 py-3 flex justify-between items-center">
        <h1 className="font-bold text-amber-800">🍹 Drink Bot</h1>
        <Link to="/chat" className="text-amber-700 text-sm hover:underline">← Back to chat</Link>
      </header>

      <main className="max-w-2xl mx-auto p-4 space-y-6">
        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-2">Account</h2>
          <p className="text-gray-600">{me.name} · {me.phone}</p>
          <p className="text-gray-500 text-sm">{me.address}</p>
        </section>

        <section className="bg-white rounded-2xl shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Preferences</h2>
          <ListEditor label="Tastes" values={prefs.tastes} onChange={(v) => setPrefs({ ...prefs, tastes: v })} />
          <ListEditor label="Drink types" values={prefs.drink_types} onChange={(v) => setPrefs({ ...prefs, drink_types: v })} />
          <ListEditor label="Allergies" values={prefs.allergies} onChange={(v) => setPrefs({ ...prefs, allergies: v })} />
          <ListEditor label="Dietary restrictions" values={prefs.dietary_restrictions} onChange={(v) => setPrefs({ ...prefs, dietary_restrictions: v })} />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
              <select
                value={prefs.temperature || 'either'}
                onChange={(e) => setPrefs({ ...prefs, temperature: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="hot">Hot</option>
                <option value="iced">Iced</option>
                <option value="either">Either</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Caffeine</label>
              <select
                value={prefs.caffeine || 'any'}
                onChange={(e) => setPrefs({ ...prefs, caffeine: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="none">None</option>
                <option value="low">Low</option>
                <option value="any">Any</option>
              </select>
            </div>
          </div>

          <button
            onClick={save}
            className="bg-amber-600 hover:bg-amber-700 text-white font-semibold px-4 py-2 rounded-lg transition"
          >
            {saved ? 'Saved ✓' : 'Save preferences'}
          </button>
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Favorite drinks</h2>
          {favorites.length === 0 && <p className="text-gray-400 text-sm">No favorites yet — save one from chat!</p>}
          <ul className="space-y-2">
            {favorites.map((fav) => (
              <li key={fav.id} className="flex justify-between items-center border-b pb-2 last:border-0">
                <div>
                  <span className="font-medium text-gray-800">{fav.menu_item.name}</span>
                  <span className="text-gray-500 text-sm ml-2">${fav.menu_item.price.toFixed(2)}</span>
                </div>
                <button
                  onClick={() => removeFavorite(fav.menu_item.id)}
                  className="text-sm text-red-500 hover:underline"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}
