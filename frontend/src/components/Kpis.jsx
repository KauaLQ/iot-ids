import { Activity, Bug, Cpu, Percent } from 'lucide-react'

function Kpi({ Icon, titulo, valor, nota, cor }) {
  return (
    <div className="flex items-center justify-between rounded-sm border border-line bg-white px-4 py-3 shadow-sm">
      <div>
        <p className="text-xs text-soft">{titulo}</p>
        <p className="text-3xl font-semibold leading-tight tabular-nums">{valor}</p>
        <p className="text-xs text-soft">{nota}</p>
      </div>
      <Icon size={28} className={cor} strokeWidth={1.75} />
    </div>
  )
}

export default function Kpis({ dados }) {
  const total = dados?.total_fluxos_analisados ?? 0
  const sus = dados?.total_ataques_detectados ?? 0
  const disp = dados?.dispositivos_atacantes?.length ?? 0
  const pct = total ? ((sus / total) * 100).toFixed(2) : '0.00'
  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Kpi Icon={Activity} titulo="Fluxos analisados" valor={total} nota="na janela atual" cor="text-blue" />
      <Kpi Icon={Bug} titulo="Fluxos suspeitos" valor={sus} nota="após filtros de confiança" cor="text-warn" />
      <Kpi Icon={Cpu} titulo="Dispositivos em observação" valor={disp} nota="com tráfego suspeito" cor="text-warn" />
      <Kpi Icon={Percent} titulo="Taxa de tráfego suspeito" valor={`${pct}%`} nota="suspeitos / total" cor={Number(pct) > 0 ? 'text-warn' : 'text-ok'} />
    </section>
  )
}
