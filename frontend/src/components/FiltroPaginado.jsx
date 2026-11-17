import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'

// campos: [{ id, label, get: (linha) => valor, numerico?: bool }]  (definir fora do componente)
export function useFiltro(dados, campos, porPagina) {
  const [campo, setCampo] = useState(campos[0].id)
  const [termo, setTermo] = useState('')
  const [pagina, setPagina] = useState(0)

  const filtrados = useMemo(() => {
    const t = termo.trim().toLowerCase()
    if (!t) return dados
    const c = campos.find((x) => x.id === campo)
    if (c.numerico) {
      const min = parseFloat(t.replace(',', '.'))
      return Number.isNaN(min) ? dados : dados.filter((d) => Number(c.get(d)) >= min)
    }
    return dados.filter((d) => String(c.get(d) ?? '').toLowerCase().includes(t))
  }, [dados, campos, campo, termo])

  const paginas = Math.max(Math.ceil(filtrados.length / porPagina), 1)
  const atual = Math.min(pagina, paginas - 1)
  return {
    linhas: filtrados.slice(atual * porPagina, (atual + 1) * porPagina),
    campos, campo, termo, atual, paginas, total: filtrados.length, porPagina,
    setCampo: (v) => { setCampo(v); setPagina(0) },
    setTermo: (v) => { setTermo(v); setPagina(0) },
    anterior: () => setPagina(Math.max(atual - 1, 0)),
    proxima: () => setPagina(Math.min(atual + 1, paginas - 1)),
  }
}

export function BarraFiltro({ f }) {
  const c = f.campos.find((x) => x.id === f.campo)
  return (
    <div className="mb-2 flex items-center gap-2 text-sm">
      <select aria-label="Filtrar por" value={f.campo} onChange={(e) => f.setCampo(e.target.value)}
        className="rounded-sm border border-line bg-white px-2 py-1">
        {f.campos.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
      </select>
      <input aria-label="Valor do filtro" value={f.termo} onChange={(e) => f.setTermo(e.target.value)}
        placeholder={c.numerico ? 'mínimo, ex.: 90' : 'contém…'}
        className="min-w-0 flex-1 rounded-sm border border-line px-2 py-1" />
      {f.termo && (
        <button onClick={() => f.setTermo('')} aria-label="Limpar filtro" className="rounded-sm border border-line p-1.5 text-soft hover:bg-page">
          <X size={14} />
        </button>
      )}
    </div>
  )
}

export function Paginacao({ f }) {
  const ini = f.total === 0 ? 0 : f.atual * f.porPagina + 1
  const fim = Math.min((f.atual + 1) * f.porPagina, f.total)
  return (
    <div className="mt-2 flex items-center justify-between text-xs text-soft">
      <span className="tabular-nums">{ini}–{fim} de {f.total}</span>
      <div className="flex gap-1">
        <button onClick={f.anterior} disabled={f.atual === 0} aria-label="Página anterior"
          className="rounded-sm border border-line p-1 enabled:hover:bg-page disabled:opacity-40"><ChevronLeft size={14} /></button>
        <button onClick={f.proxima} disabled={f.atual >= f.paginas - 1} aria-label="Próxima página"
          className="rounded-sm border border-line p-1 enabled:hover:bg-page disabled:opacity-40"><ChevronRight size={14} /></button>
      </div>
    </div>
  )
}
