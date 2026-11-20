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

const CAMPO =
  'h-8 rounded-lg border border-zinc-200 px-2.5 text-xs text-zinc-700 dark:border-zinc-800 dark:text-zinc-300'

export function BarraFiltro({ f }) {
  const c = f.campos.find((x) => x.id === f.campo)
  return (
    <div className="mb-3 flex items-center gap-2">
      <select aria-label="Filtrar por" value={f.campo} onChange={(e) => f.setCampo(e.target.value)}
        className={`${CAMPO} bg-zinc-50 dark:bg-zinc-900`}>
        {f.campos.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
      </select>
      <input aria-label="Valor do filtro" value={f.termo} onChange={(e) => f.setTermo(e.target.value)}
        placeholder={c.numerico ? 'mínimo, ex.: 90' : 'contém…'}
        className={`${CAMPO} min-w-0 flex-1 bg-white font-mono placeholder:font-sans placeholder:text-zinc-400 dark:bg-zinc-950`} />
      {f.termo && (
        <button onClick={() => f.setTermo('')} aria-label="Limpar filtro"
          className="grid h-8 w-8 cursor-pointer place-items-center rounded-lg border border-zinc-200 text-zinc-500 transition-colors hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800">
          <X size={14} />
        </button>
      )}
    </div>
  )
}

const BTN_PAG =
  'grid h-7 w-7 place-items-center rounded-md border border-zinc-200 text-zinc-600 dark:border-zinc-800 dark:text-zinc-300 enabled:cursor-pointer enabled:hover:bg-zinc-100 dark:enabled:hover:bg-zinc-800 disabled:opacity-40'

export function Paginacao({ f }) {
  const ini = f.total === 0 ? 0 : f.atual * f.porPagina + 1
  const fim = Math.min((f.atual + 1) * f.porPagina, f.total)
  return (
    <div className="mt-3 flex items-center justify-between">
      <span className="font-mono text-[11px] tabular-nums text-zinc-400 dark:text-zinc-500">{ini}–{fim} de {f.total}</span>
      <div className="flex gap-1">
        <button onClick={f.anterior} disabled={f.atual === 0} aria-label="Página anterior" className={BTN_PAG}><ChevronLeft size={14} /></button>
        <button onClick={f.proxima} disabled={f.atual >= f.paginas - 1} aria-label="Próxima página" className={BTN_PAG}><ChevronRight size={14} /></button>
      </div>
    </div>
  )
}