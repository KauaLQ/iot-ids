import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Clock, Cpu, RefreshCw, ShieldCheck, Sparkles, Wifi, WifiOff } from 'lucide-react'
import { estadoSistema, TONS } from '../estado'
import { useToast } from './Toast'

const IA_ROTULO = {
  desativado: 'desativada', ocioso: 'em espera', aguardando: 'aguardando', disponivel: 'disponível',
  gerando: 'gerando', pronto: 'pronto', erro: 'erro', limite: 'limite',
}
const IA_TOM = { pronto: 'ok', gerando: 'idle', aguardando: 'idle', ocioso: 'idle', disponivel: 'idle', desativado: 'idle', erro: 'warn', limite: 'warn' }

const PILULA = 'rounded-md border border-zinc-200/90 bg-zinc-50/80 text-xs dark:border-zinc-800 dark:bg-zinc-900/60'

function Linha({ tom, rotulo, valor }) {
  return (
    <div className="flex items-center justify-between px-3 py-2 text-xs">
      <span className="flex items-center gap-2 font-medium text-zinc-800 dark:text-zinc-200">
        <span className={`h-2 w-2 rounded-full ${TONS[tom].dot}`} />
        {rotulo}
      </span>
      <span className="font-mono text-[10px] text-zinc-400">{valor}</span>
    </div>
  )
}

export default function Header({ dados, conexao, latencia, ultimaLeitura, onAtualizar }) {
  const toast = useToast()
  const est = estadoSistema(dados, conexao)
  const tom = TONS[est.tom]
  const online = conexao === 'online'
  const ia = dados?.relatorio_ia
  const iaAtiva = ia && ia.estado !== 'desativado' && ia.modelo
  const modelo = dados?.modelo_carregado ? `XGBoost ${dados.modelo_versao ?? ''}`.trim() : 'Sem modelo'

  const [aberto, setAberto] = useState(false)
  const [giro, setGiro] = useState(0)
  const [lendo, setLendo] = useState(false)
  const caixa = useRef(null)

  useEffect(() => {
    if (!aberto) return
    const fora = (e) => { if (caixa.current && !caixa.current.contains(e.target)) setAberto(false) }
    const esc = (e) => { if (e.key === 'Escape') setAberto(false) }
    document.addEventListener('mousedown', fora)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', fora)
      document.removeEventListener('keydown', esc)
    }
  }, [aberto])

  async function atualizar() {
    if (lendo) return
    setLendo(true)
    setGiro((g) => g + 360)
    const ok = await onAtualizar?.()
    setLendo(false)
    toast(ok ? 'Leitura sincronizada com sucesso' : 'Não foi possível sincronizar com o backend',
      { tom: ok ? 'ok' : 'warn', key: 'sync' })
  }

  const nDisp = dados?.dispositivos_atacantes?.length ?? 0
  const latTxt = online && latencia != null ? `${latencia}ms` : online ? '…' : 'offline'

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-200 bg-white/80 backdrop-blur-md transition-colors duration-200 dark:border-zinc-800 dark:bg-[#09090b]/80">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">

        {/* ESQUERDA: logo + projeto + status do sistema */}
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <div className="group flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-900 text-white shadow-sm transition-transform group-hover:scale-105 dark:bg-zinc-100 dark:text-zinc-950">
              <ShieldCheck size={16} strokeWidth={2.2} />
            </div>
            <div className="flex items-center gap-2">
              <span className="whitespace-nowrap text-sm font-semibold tracking-tight">IoT-IDS</span>
              <span className="hidden rounded border border-zinc-200/80 bg-zinc-100 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-500 dark:border-zinc-700/60 dark:bg-zinc-800/80 dark:text-zinc-400 md:inline-block">
                Lab
              </span>
            </div>
          </div>

          <span className="hidden h-4 w-px bg-zinc-200 dark:bg-zinc-800 sm:inline-block" aria-hidden="true" />

          <div className="relative" ref={caixa}>
            <button
              type="button" aria-haspopup="menu" aria-expanded={aberto}
              onClick={() => setAberto((a) => !a)}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-zinc-400/30 ${tom.pill}`}
            >
              <span className="relative flex h-2 w-2">
                {tom.ping && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${tom.pingCor}`} />}
                <span className={`relative inline-flex h-2 w-2 rounded-full ${tom.dot}`} />
              </span>
              {est.label}
              <ChevronDown size={12} className={`opacity-60 transition-transform ${aberto ? 'rotate-180' : ''}`} />
            </button>

            {aberto && (
              <div role="menu" className="absolute left-0 z-50 mt-2 w-60 rounded-xl border border-zinc-200 bg-white py-1.5 shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
                <div className="px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Estado do sistema</div>
                <Linha tom={est.tom === 'bad' && conexao === 'offline' ? 'idle' : est.tom} rotulo="Rede"
                  valor={nDisp > 0 ? `${nDisp} em observação` : est.id === 'normal' ? 'normal' : est.label.toLowerCase()} />
                <Linha tom={online ? 'ok' : conexao === 'offline' ? 'bad' : 'idle'} rotulo="Backend" valor={latTxt} />
                <Linha tom={!dados ? 'idle' : dados.modelo_carregado ? 'ok' : 'warn'} rotulo="Classificador"
                  valor={dados?.modelo_carregado ? dados.modelo_versao ?? 'ativo' : 'indisponível'} />
                <Linha tom={IA_TOM[ia?.estado] ?? 'idle'} rotulo="Relatório IA" valor={IA_ROTULO[ia?.estado] ?? '—'} />
              </div>
            )}
          </div>
        </div>

        {/* DIREITA: backend + modelo + leitura */}
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            type="button" onClick={atualizar} title="Clique para forçar uma nova leitura"
            className={`hidden cursor-pointer items-center gap-2 px-2.5 py-1 text-zinc-600 transition-colors hover:border-zinc-300 dark:text-zinc-300 dark:hover:border-zinc-700 sm:inline-flex ${PILULA}`}
          >
            {online
              ? <Wifi size={14} className="text-emerald-500" />
              : <WifiOff size={14} className={conexao === 'offline' ? 'text-rose-500' : 'text-zinc-400'} />}
            <span className="font-medium">{online ? 'API Conectada' : conexao === 'offline' ? 'Desconectado' : 'Conectando…'}</span>
            <span className="border-l border-zinc-200 pl-1 font-mono text-[11px] text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">{latTxt}</span>
          </button>

          <div title="Modelo de classificação ativo"
            className={`hidden items-center gap-1.5 px-2.5 py-1 font-mono text-zinc-700 dark:text-zinc-300 lg:inline-flex ${PILULA}`}>
            <Cpu size={14} className="text-indigo-500 dark:text-indigo-400" />
            <span>{modelo}</span>
          </div>

          {iaAtiva && (
            <div title="Modelo generativo dos relatórios de incidente"
              className={`hidden items-center gap-1.5 px-2.5 py-1 font-mono text-zinc-700 dark:text-zinc-300 xl:inline-flex ${PILULA}`}>
              <Sparkles size={14} className="text-indigo-500 dark:text-indigo-400" />
              <span>{ia.modelo}</span>
            </div>
          )}

          <div className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200/90 bg-white py-1 pl-2.5 pr-1 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            <Clock size={14} className="shrink-0 text-zinc-400 dark:text-zinc-500" />
            <span className="hidden text-zinc-400 dark:text-zinc-500 md:inline">Leitura:</span>
            <time className="font-mono text-[11px] font-medium tabular-nums text-zinc-800 dark:text-zinc-200">{ultimaLeitura || '—'}</time>
            <button
              type="button" onClick={atualizar} disabled={lendo} title="Atualizar leitura agora" aria-label="Atualizar leitura agora"
              className="cursor-pointer rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 focus:outline-none dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
            >
              <RefreshCw size={14} className="transition-transform duration-500" style={{ transform: `rotate(${giro}deg)` }} />
            </button>
          </div>
        </div>
      </div>

      {/* Barra compacta só para telas < 640px */}
      <div className="flex items-center justify-between border-t border-zinc-100 bg-zinc-50/50 px-4 py-1.5 text-[11px] text-zinc-500 dark:border-zinc-800/80 dark:bg-zinc-900/40 dark:text-zinc-400 sm:hidden">
        <span className="inline-flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-emerald-500' : conexao === 'offline' ? 'bg-rose-500' : 'bg-zinc-400'}`} />
          {online ? `API Conectada (${latTxt})` : conexao === 'offline' ? 'API Desconectada' : 'Conectando…'}
        </span>
        <span className="font-mono text-zinc-600 dark:text-zinc-300">{modelo}</span>
      </div>
    </header>
  )
}