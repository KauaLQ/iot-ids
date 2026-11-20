import { Moon, Sun } from 'lucide-react'
import { estadoSistema, TONS } from '../estado'
import { useTheme } from '../theme/ThemeContext'
import { BTN_PRIMARIO, BTN_SECUNDARIO } from '../theme/ui'

// Equivalente à "barra de controles" do exemplo: título + descrição à esquerda, ações à direita.
export default function StatusBanner({ dados, conexao }) {
  const est = estadoSistema(dados, conexao)
  const tom = TONS[est.tom]
  const { tema, alternar } = useTheme()
  const temIncidente = (dados?.dispositivos_atacantes?.length ?? 0) > 0

  const irParaRelatorio = () =>
    document.getElementById('relatorio')?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white dark:border-zinc-800/80 dark:bg-zinc-900/50">
      <div className="flex flex-col justify-between gap-4 p-4 sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-start gap-3">
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${tom.soft}`}>
            <est.Icon size={18} strokeWidth={1.9} />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold">{est.titulo}</h1>
            <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
              <span className={`font-medium ${tom.texto}`}>{est.label}</span> · {est.sub}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button type="button" onClick={alternar} className={BTN_SECUNDARIO}>
            {tema === 'dark' ? <Sun size={14} className="text-amber-400" /> : <Moon size={14} className="text-zinc-600" />}
            {tema === 'dark' ? 'Modo Claro' : 'Modo Escuro'}
          </button>
          {temIncidente && (
            <button type="button" onClick={irParaRelatorio} className={BTN_PRIMARIO}>Ver relatório</button>
          )}
        </div>
      </div>

      {dados?.erro_modelo && (
        <p className="border-t border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-xs leading-relaxed text-amber-700 dark:text-amber-400">
          {dados.erro_modelo}
        </p>
      )}
    </div>
  )
}