export default function Card({ titulo, sub, acao, className = '', rolagem = true, children, ...rest }) {
  return (
    <section
      {...rest}
      className={`flex min-h-0 flex-col rounded-xl border border-zinc-200/70 bg-white dark:border-zinc-800/70 dark:bg-zinc-900/30 ${className}`}
    >
      <header className="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold tracking-tight">{titulo}</h2>
          {sub && <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{sub}</p>}
        </div>
        {acao}
      </header>
      <div className={`sem-barra min-h-0 flex-1 px-5 pb-5 ${rolagem ? 'overflow-y-auto' : 'overflow-hidden'}`}>{children}</div>
    </section>
  )
}