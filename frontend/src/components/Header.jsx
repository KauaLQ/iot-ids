import { ShieldCheck, ShieldAlert, ShieldQuestion, Wifi, WifiOff, Loader2 } from 'lucide-react'

function estadoRede(dados) {
  const n = dados?.dispositivos_atacantes?.length ?? 0
  switch (dados?.status_rede) {
    case 'SOB ATAQUE':
      return { Icon: ShieldAlert, cor: 'text-amber-300', titulo: 'Possível anomalia detectada',
        sub: `Tráfego suspeito monitorado em ${n} dispositivo${n === 1 ? '' : 's'}` }
    case 'NORMAL':
      return { Icon: ShieldCheck, cor: 'text-emerald-300', titulo: 'Operação normal', sub: 'Nenhuma anomalia na janela atual' }
    case 'ERRO_MODELO':
      return { Icon: ShieldQuestion, cor: 'text-amber-300', titulo: 'Modelo de análise indisponível', sub: 'A classificação está pausada' }
    default:
      return { Icon: ShieldQuestion, cor: 'text-white/60', titulo: 'Inicializando…', sub: 'Aguardando dados do backend' }
  }
}

export default function Header({ dados, conexao }) {
  const est = estadoRede(dados)
  const online = conexao === 'online'
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-3 bg-bar px-4 py-3 text-white">
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-sm bg-accent text-bar"><ShieldCheck size={18} /></span>
        <div className="leading-tight">
          <p className="text-base font-semibold">IoT-IDS</p>
          <p className="text-xs text-white/60">Monitor de Segurança</p>
        </div>
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-3 lg:border-l lg:border-white/15 lg:pl-6">
        <est.Icon size={28} className={est.cor} />
        <div className="min-w-0">
          <h1 className={`truncate text-lg font-semibold leading-tight ${est.cor}`}>{est.titulo}</h1>
          <p className="truncate text-sm text-white/70">{est.sub}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <span className={`flex items-center gap-1.5 ${online ? 'text-emerald-300' : conexao === 'offline' ? 'text-red-300' : 'text-white/60'}`}>
          {online ? <Wifi size={15} /> : conexao === 'offline' ? <WifiOff size={15} /> : <Loader2 size={15} className="animate-spin" />}
          {online ? 'Backend conectado' : conexao === 'offline' ? 'Backend inacessível' : 'Conectando…'}
        </span>
        <span className={dados?.modelo_carregado ? 'text-sky-300' : 'text-amber-300'}>
          {dados?.modelo_carregado ? 'Modelo ativo' : 'Modelo não carregado'}
        </span>
        <p className="text-xs leading-tight text-white/60">Última leitura<br /><span className="text-sm text-white tabular-nums">{dados?.ultima_atualizacao || '—'}</span></p>
      </div>
    </header>
  )
}
