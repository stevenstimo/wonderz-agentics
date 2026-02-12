import { useEffect, useState } from 'react'

export default function UnifiedProducts() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetch(`${import.meta.env.VITE_API_URL}/products/unified`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch unified products')
        return res.json()
      })
      .then(setProducts)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div>Loading unified products...</div>
  if (error) return <div className="text-red-600">Error: {error}</div>

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">Unified Products</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {products.map(prod => (
          <div key={prod.external_id} className="border p-4 rounded-lg">
            <h3 className="font-semibold text-lg text-gray-800 mb-2">{prod.title}</h3>
            <div className="text-sm text-gray-600 mb-1">Platform: {prod.source_platform}</div>
            <div className="text-sm text-gray-600 mb-1">Price: {prod.price} {prod.currency}</div>
            <div className="text-sm text-gray-600 mb-1">Inventory: {prod.inventory_quantity}</div>
            <div className="text-xs text-gray-500 mb-1">SEO: {prod.seo_title}</div>
            <div className="text-xs text-gray-500 mb-1">Tags: {prod.tags?.join(', ')}</div>
            <div className="text-xs text-gray-400">ID: {prod.external_id}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
