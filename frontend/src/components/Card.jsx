export default function Card({ titulo, sub, className = '', rolagem = true, children }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-sm border border-line bg-white shadow-sm ${className}`}>
      <header className="px-4 pb-2 pt-3">
        <h2 className="text-[15px] font-semibold leading-tight">{titulo}</h2>
        {sub && <p className="mt-0.5 text-xs text-soft">{sub}</p>}
      </header>
      <div className={`sem-barra min-h-0 flex-1 px-4 pb-4 ${rolagem ? 'overflow-y-auto' : 'overflow-hidden'}`}>{children}</div>
    </section>
  )
}
