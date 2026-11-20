import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

const DOT = {
  ok: 'bg-emerald-400 dark:bg-emerald-600',
  warn: 'bg-amber-400 dark:bg-amber-600',
  bad: 'bg-rose-400 dark:bg-rose-600',
  info: 'bg-zinc-400 dark:bg-zinc-500',
}

const ToastCtx = createContext(() => {})

// toast('mensagem', { tom: 'ok'|'warn'|'bad'|'info', duracao: ms, key: 'id-p/-substituir' })
export function ToastProvider({ children }) {
  const [itens, setItens] = useState([])
  const seq = useRef(0)
  const timers = useRef(new Map())

  const remover = useCallback((id) => {
    clearTimeout(timers.current.get(id))
    timers.current.delete(id)
    setItens((l) => l.filter((t) => t.id !== id))
  }, [])

  const push = useCallback((msg, { tom = 'info', duracao = 3200, key } = {}) => {
    const id = key ?? `t${++seq.current}`
    clearTimeout(timers.current.get(id))
    setItens((l) => [...l.filter((t) => t.id !== id), { id, msg, tom }].slice(-3))
    timers.current.set(id, setTimeout(() => remover(id), duracao))
  }, [remover])

  useEffect(() => {
    const mapa = timers.current
    return () => mapa.forEach(clearTimeout)
  }, [])

  const lista = useMemo(() => itens, [itens])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2">
        {lista.map((t) => (
          <div key={t.id}
            className="toast-in pointer-events-auto flex max-w-sm items-center gap-2 rounded-lg bg-zinc-900 px-3.5 py-2 text-xs font-medium text-white shadow-lg dark:bg-zinc-100 dark:text-zinc-900">
            <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[t.tom] ?? DOT.info}`} />
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)