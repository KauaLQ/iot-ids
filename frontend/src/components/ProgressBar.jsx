// Barra de progresso do design system (h-1.5, trilho zinc, ponta arredondada).
// `fill`: classes Tailwind da cor; `cor`: hex (tem prioridade, usado p/ cores por classe de tráfego).
export default function ProgressBar({ valor = 0, fill = 'bg-zinc-900 dark:bg-zinc-200', cor, altura = 'h-1.5', className = '' }) {
  const w = Math.min(Math.max(Number(valor) || 0, 0), 100)
  return (
    <div
      role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(w)}
      className={`${altura} w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800 ${className}`}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${cor ? '' : fill}`}
        style={{ width: `${w}%`, ...(cor ? { backgroundColor: cor } : null) }}
      />
    </div>
  )
}