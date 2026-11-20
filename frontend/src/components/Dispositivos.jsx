import { ShieldCheck } from 'lucide-react'
import Card from './Card'
import ProgressBar from './ProgressBar'
import Tag from './Tag'
import { tipoDe } from '../theme/tipos'
import { fmtInt, fmtPct } from '../format'

function Vazio() {
  return (
    <div className="flex h-full min-h-48 flex-col items-center justify-center rounded-lg border border-dashed border-zinc-200 p-6 text-center dark:border-zinc-800">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-100 text-emerald-500 dark:bg-zinc-900">
        <ShieldCheck size={18} strokeWidth={1.8} />
      </div>
      <p className="text-xs font-medium text-zinc-600 dark:text-zinc-300">Nenhum dispositivo em observação</p>
      <p className="mt-1 max-w-xs text-xs text-zinc-400 dark:text-zinc-500">O tráfego da janela atual não apresenta indícios suspeitos.</p>
    </div>
  )
}

export default function Dispositivos({ atacantes }) {
  const lista = atacantes ?? []
  const max = Math.max(...lista.map((a) => a.fluxos_maliciosos), 1)

  return (
    <Card titulo="Dispositivos em observação" sub="Fluxos suspeitos por origem e tipo" className="h-[24rem]"
      acao={<span className="font-mono text-[11px] text-zinc-400">{lista.length} {lista.length === 1 ? 'ativo' : 'ativos'}</span>}>
      {lista.length === 0 ? <Vazio /> : (
        <ul className="space-y-5">
          {lista.map((a) => (
            <li key={`${a.ip_dispositivo}-${a.tipo_ataque}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-medium">{a.ip_dispositivo}</span>
                    <Tag t={a.tipo_ataque} />
                  </div>
                  <p className="mt-1 truncate font-mono text-[11px] text-zinc-500 dark:text-zinc-400">
                    → {a.ip_vitima}:{a.porta_vitima} · último {a.ultimo_alerta} · conf. {fmtPct(a.confianca_ia_pct)}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="font-mono text-lg font-semibold leading-none tabular-nums">{fmtInt(a.fluxos_maliciosos)}</p>
                  <p className="mt-1 text-[10px] text-zinc-400">fluxos</p>
                </div>
              </div>
              <ProgressBar className="mt-2.5" valor={(a.fluxos_maliciosos / max) * 100} cor={tipoDe(a.tipo_ataque).cor} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}