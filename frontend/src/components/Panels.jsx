import Card from './Card'
import ProgressBar from './ProgressBar'
import Tag from './Tag'
import { BarraFiltro, Paginacao, useFiltro } from './FiltroPaginado'
import { tipoDe } from '../theme/tipos'
import { fmtPct } from '../format'

const classe = (f) => (f.status_geral === 'BENIGNO' ? 'Benigno' : f.tipo_trafego)

const CAMPOS_ALERTA = [
  { id: 'hora', label: 'Hora', get: (a) => a.hora },
  { id: 'origem', label: 'Origem', get: (a) => a.ip_dispositivo },
  { id: 'destino', label: 'Destino', get: (a) => `${a.ip_vitima}:${a.porta_vitima}` },
  { id: 'classe', label: 'Classificação', get: (a) => a.tipo_ataque },
  { id: 'conf', label: 'Confiança', get: (a) => a.confianca_ia_pct, numerico: true },
]

const CAMPOS_FEED = [
  { id: 'hora', label: 'Hora', get: (f) => f.horario },
  { id: 'origem', label: 'Origem', get: (f) => f['id.orig_h'] },
  { id: 'destino', label: 'Destino', get: (f) => `${f['id.resp_h']}:${f['id.resp_p']}` },
  { id: 'proto', label: 'Protocolo', get: (f) => f.proto },
  { id: 'classe', label: 'Classificação', get: classe },
  { id: 'conf', label: 'Confiança', get: (f) => f.confianca_ia, numerico: true },
]

const TH = 'px-3 py-2 text-left font-mono text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500'

export function Historico({ alertas }) {
  const f = useFiltro(alertas, CAMPOS_ALERTA, 4)
  return (
    <Card titulo="Histórico de alertas" sub="Sinalizações desta sessão" className="h-[24rem]" rolagem={false}>
      <div className="flex h-full flex-col">
        <BarraFiltro f={f} />
        <ul className="flex-1 divide-y divide-zinc-100 dark:divide-zinc-800/70">
          {f.linhas.map((a) => (
            <li key={a.id} className="py-2.5">
              <div className="flex items-center justify-between gap-2">
                <Tag t={a.tipo_ataque} />
                <span className="font-mono text-[11px] tabular-nums text-zinc-400">{a.hora} · {fmtPct(a.confianca_ia_pct)}</span>
              </div>
              <p className="mt-1.5 truncate font-mono text-xs">
                <b className="font-medium">{a.ip_dispositivo}</b>{' '}
                <span className="text-zinc-400">→ {a.ip_vitima}:{a.porta_vitima}</span>
              </p>
            </li>
          ))}
          {f.linhas.length === 0 && (
            <li className="py-8 text-center text-xs text-zinc-400 dark:text-zinc-500">
              {alertas.length ? 'Nenhum alerta com esse filtro.' : 'Nenhum alerta nesta sessão.'}
            </li>
          )}
        </ul>
        <Paginacao f={f} />
      </div>
    </Card>
  )
}

export function Feed({ feed }) {
  const f = useFiltro(feed, CAMPOS_FEED, 10)
  return (
    <Card titulo="Últimas conexões" sub="Fluxos recentes classificados pelo modelo" rolagem={false}>
      <BarraFiltro f={f} />
      <div className="sem-barra overflow-x-auto">
        <table className="w-full min-w-[720px] text-xs">
          <thead className="border-b border-zinc-100 dark:border-zinc-800/70">
            <tr>
              <th className={TH}>Hora</th><th className={TH}>Origem</th><th className={TH}>Destino</th>
              <th className={TH}>Proto</th><th className={TH}>Classificação</th><th className={`${TH} text-right`}>Confiança</th>
            </tr>
          </thead>
          <tbody>
            {f.linhas.map((r, i) => {
              const c = classe(r)
              return (
                <tr key={r.uid ?? i} className="border-t border-zinc-100 transition-colors first:border-t-0 hover:bg-zinc-50 dark:border-zinc-800/70 dark:hover:bg-zinc-900/60">
                  <td className="px-3 py-2 font-mono tabular-nums text-zinc-400">{r.horario}</td>
                  <td className="px-3 py-2 font-mono">{r['id.orig_h']}</td>
                  <td className="px-3 py-2 font-mono">{r['id.resp_h']}:{r['id.resp_p']}</td>
                  <td className="px-3 py-2 font-mono uppercase text-zinc-400">{r.proto}</td>
                  <td className="px-3 py-2"><Tag t={c} /></td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-end gap-2">
                      <span className="font-mono tabular-nums">{fmtPct(r.confianca_ia)}</span>
                      <div className="w-12"><ProgressBar valor={r.confianca_ia} cor={tipoDe(c).cor} altura="h-1" /></div>
                    </div>
                  </td>
                </tr>
              )
            })}
            {f.linhas.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-zinc-400 dark:text-zinc-500">
                {feed.length ? 'Nenhuma conexão com esse filtro.' : 'Aguardando tráfego…'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <Paginacao f={f} />
    </Card>
  )
}