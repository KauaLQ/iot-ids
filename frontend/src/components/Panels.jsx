import Card from './Card'
import { BarraFiltro, Paginacao, useFiltro } from './FiltroPaginado'
import { fmtPct } from '../format'

const sev = (t) => (t === 'Benigno' ? 'text-ok bg-ok/10' : t === 'PortScan' ? 'text-warn bg-warn/10' : 'text-bad bg-bad/10')
const Tag = ({ t }) => <span className={`rounded-sm px-2 py-0.5 text-xs font-semibold ${sev(t)}`}>{t}</span>
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

export function Incidente({ texto }) {
  return (
    <Card titulo="Resumo da análise" sub="Gerado pelo motor de IA" className="h-[22rem]">
      <p className="whitespace-pre-line rounded-sm border-l-4 border-blue bg-page p-3 text-sm leading-relaxed [overflow-wrap:anywhere]">
        {texto || 'Aguardando o motor de IA…'}
      </p>
    </Card>
  )
}

export function Historico({ alertas }) {
  const f = useFiltro(alertas, CAMPOS_ALERTA, 3)
  return (
    <Card titulo="Histórico de alertas" sub="Sinalizações desta sessão" className="h-[22rem]" rolagem={false}>
      <div className="flex h-full flex-col">
        <BarraFiltro f={f} />
        <ul className="flex-1 divide-y divide-line">
          {f.linhas.map((a) => (
            <li key={a.id} className="py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <Tag t={a.tipo_ataque} />
                <span className="text-xs text-soft tabular-nums">{a.hora} · {fmtPct(a.confianca_ia_pct)}</span>
              </div>
              <p className="mt-1 truncate tabular-nums"><b>{a.ip_dispositivo}</b> <span className="text-soft">→ {a.ip_vitima}:{a.porta_vitima}</span></p>
            </li>
          ))}
          {f.linhas.length === 0 && <li className="py-6 text-center text-sm text-soft">{alertas.length ? 'Nenhum alerta com esse filtro.' : 'Nenhum alerta nesta sessão.'}</li>}
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
        <table className="w-full min-w-[680px] text-sm tabular-nums">
          <thead className="bg-page text-left text-xs text-soft">
            <tr><th className="px-3 py-2 font-medium">Hora</th><th className="font-medium">Origem</th><th className="font-medium">Destino</th><th className="font-medium">Proto</th><th className="font-medium">Classificação</th><th className="px-3 text-right font-medium">Confiança</th></tr>
          </thead>
          <tbody>
            {f.linhas.map((r, i) => (
              <tr key={i} className="border-t border-line even:bg-page/50">
                <td className="px-3 py-1.5 text-soft">{r.horario}</td>
                <td>{r['id.orig_h']}</td>
                <td>{r['id.resp_h']}:{r['id.resp_p']}</td>
                <td className="uppercase text-soft">{r.proto}</td>
                <td><Tag t={classe(r)} /></td>
                <td className="px-3 text-right">{fmtPct(r.confianca_ia)}</td>
              </tr>
            ))}
            {f.linhas.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-soft">{feed.length ? 'Nenhuma conexão com esse filtro.' : 'Aguardando tráfego…'}</td></tr>}
          </tbody>
        </table>
      </div>
      <Paginacao f={f} />
    </Card>
  )
}
