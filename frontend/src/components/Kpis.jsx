import { Activity, Bug, Cpu, Percent } from 'lucide-react'
import ProgressBar from './ProgressBar'
import { TONS } from '../estado'
import { fmtInt, fmtPct } from '../format'

function Kpi({ Icon, titulo, badge, badgeTom = 'idle', valor, nota, pct, fill }) {
  return (
    <div className="space-y-3 rounded-xl border border-zinc-200/70 bg-white p-5 dark:border-zinc-800/70 dark:bg-zinc-900/30">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          <Icon size={13} />{titulo}
        </span>
        <span className={`font-mono text-[11px] ${badgeTom === 'idle' ? 'text-zinc-400' : TONS[badgeTom].texto}`}>{badge}</span>
      </div>
      <div className="font-mono text-2xl font-semibold tabular-nums tracking-tight">{valor}</div>
      <ProgressBar valor={pct} fill={fill} />
      <p className="text-[11px] text-zinc-400 dark:text-zinc-500">{nota}</p>
    </div>
  )
}

export default function Kpis({ dados }) {
  const total = dados?.total_fluxos_analisados ?? 0
  const sus = dados?.total_ataques_detectados ?? 0
  const atacantes = dados?.dispositivos_atacantes ?? []
  const feed = dados?.feed_tempo_real ?? []
  const disp = atacantes.length

  const pctSus = total ? (sus / total) * 100 : 0
  const pctBenigno = total ? 100 - pctSus : 0
  const confMedia = disp ? atacantes.reduce((s, a) => s + (a.confianca_ia_pct || 0), 0) / disp : 0
  // Dispositivos ativos ≈ origens distintas no feed recente + atacantes
  const ativos = new Set([...feed.map((f) => f['id.orig_h']), ...atacantes.map((a) => a.ip_dispositivo)]).size

  const taxaTom = pctSus === 0 ? 'ok' : pctSus < 25 ? 'warn' : 'bad'
  const taxaRotulo = pctSus === 0 ? 'Estável' : pctSus < 25 ? 'Atenção' : 'Elevada'

  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Kpi Icon={Activity} titulo="Fluxos analisados" badge="janela atual"
        valor={fmtInt(total)} pct={pctBenigno} nota={`${fmtPct(pctBenigno)} do tráfego benigno`} />
      <Kpi Icon={Bug} titulo="Fluxos suspeitos" badge={disp ? `conf. ${fmtPct(confMedia)}` : 'nenhum'} badgeTom={disp ? 'warn' : 'ok'}
        valor={fmtInt(sus)} pct={confMedia} fill="bg-indigo-500" nota="após filtros de confiança" />
      <Kpi Icon={Cpu} titulo="Dispositivos em observação" badge={ativos ? `de ${ativos} ativos` : 'sem tráfego'}
        valor={fmtInt(disp)} pct={ativos ? (disp / ativos) * 100 : 0} fill={disp ? TONS.warn.fill : TONS.ok.fill}
        nota="com tráfego suspeito" />
      <Kpi Icon={Percent} titulo="Taxa de tráfego suspeito" badge={taxaRotulo} badgeTom={taxaTom}
        valor={fmtPct(pctSus)} pct={pctSus} fill={TONS[taxaTom].fill} nota="suspeitos / total" />
    </section>
  )
}