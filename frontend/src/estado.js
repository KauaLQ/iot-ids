import { ShieldAlert, ShieldCheck, ShieldQuestion, WifiOff } from 'lucide-react'

// Tons semânticos (classes completas, para o Tailwind detectá-las)
export const TONS = {
  ok: {
    pill: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/15',
    dot: 'bg-emerald-500', pingCor: 'bg-emerald-400', ping: true,
    texto: 'text-emerald-600 dark:text-emerald-400',
    soft: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    fill: 'bg-emerald-500',
  },
  warn: {
    pill: 'bg-amber-500/10 border-amber-500/25 text-amber-700 dark:text-amber-400 hover:bg-amber-500/15',
    dot: 'bg-amber-500', pingCor: 'bg-amber-400', ping: true,
    texto: 'text-amber-600 dark:text-amber-400',
    soft: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    fill: 'bg-amber-500',
  },
  bad: {
    pill: 'bg-rose-500/10 border-rose-500/25 text-rose-700 dark:text-rose-400 hover:bg-rose-500/15',
    dot: 'bg-rose-500', pingCor: 'bg-rose-400', ping: true,
    texto: 'text-rose-600 dark:text-rose-400',
    soft: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
    fill: 'bg-rose-500',
  },
  idle: {
    pill: 'bg-zinc-500/10 border-zinc-500/20 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-500/15',
    dot: 'bg-zinc-400', pingCor: '', ping: false,
    texto: 'text-zinc-500 dark:text-zinc-400',
    soft: 'bg-zinc-500/10 text-zinc-500 dark:text-zinc-400',
    fill: 'bg-zinc-400',
  },
}

// Estado global do sistema, derivado do /api/status + estado da conexão.
export function estadoSistema(dados, conexao) {
  const n = dados?.dispositivos_atacantes?.length ?? 0
  if (conexao === 'offline') {
    return { id: 'offline', tom: 'bad', label: 'Sem conexão', Icon: WifiOff,
      titulo: 'Backend inacessível', sub: 'Os dados exibidos podem estar desatualizados' }
  }
  switch (dados?.status_rede) {
    case 'SOB ATAQUE':
      return { id: 'anomalia', tom: 'bad', label: 'Anomalia', Icon: ShieldAlert,
        titulo: 'Possível anomalia detectada',
        sub: `Tráfego suspeito monitorado em ${n} dispositivo${n === 1 ? '' : 's'}` }
    case 'NORMAL':
      return { id: 'normal', tom: 'ok', label: 'Operacional', Icon: ShieldCheck,
        titulo: 'Operação normal', sub: 'Nenhuma anomalia na janela atual' }
    case 'ERRO_MODELO':
      return { id: 'modelo', tom: 'warn', label: 'Degradado', Icon: ShieldQuestion,
        titulo: 'Modelo de análise indisponível', sub: 'A classificação está pausada' }
    default:
      return { id: 'init', tom: 'idle', label: 'Iniciando', Icon: ShieldQuestion,
        titulo: 'Inicializando…', sub: 'Aguardando dados do backend' }
  }
}