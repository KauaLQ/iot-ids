import { useState } from 'react'
import { Check, Copy, Info, Loader2, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react'
import Card from './Card'

const SEV = {
  alta: { rotulo: 'Severidade alta', cls: 'bg-bad/10 text-bad' },
  media: { rotulo: 'Severidade média', cls: 'bg-warn/10 text-warn' },
  baixa: { rotulo: 'Severidade baixa', cls: 'bg-blue/10 text-blue' },
}

function Comando({ texto }) {
  const [ok, setOk] = useState(false)
  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto)
    } catch {
      // http em rede local (sem contexto seguro): fallback com textarea
      const t = document.createElement('textarea')
      t.value = texto
      document.body.appendChild(t)
      t.select()
      try { document.execCommand('copy') } finally { document.body.removeChild(t) }
    }
    setOk(true)
    setTimeout(() => setOk(false), 1500)
  }
  return (
    <div className="mt-1.5 flex items-start gap-1 rounded-sm bg-bar p-2">
      <code className="min-w-0 flex-1 whitespace-pre-wrap break-all font-mono text-xs text-emerald-200">{texto}</code>
      <button onClick={copiar} aria-label="Copiar comando" className="shrink-0 rounded-sm p-1 text-white/70 hover:bg-white/10">
        {ok ? <Check size={14} /> : <Copy size={14} />}
      </button>
    </div>
  )
}

function Relatorio({ rel, ia }) {
  const sev = SEV[rel.severidade] ?? SEV.media
  return (
    <div className={ia.desatualizado ? 'opacity-60' : ''}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-sm px-2 py-0.5 text-xs font-semibold ${sev.cls}`}>{sev.rotulo}</span>
        {ia.desatualizado && (
          <span className="rounded-sm bg-page px-2 py-0.5 text-xs font-medium text-soft">Análise anterior</span>
        )}
        {ia.gerado_em && <span className="text-xs tabular-nums text-soft">Gerado em {ia.gerado_em}</span>}
      </div>
      <p className="mt-2 text-sm font-medium leading-snug">{rel.resumo}</p>

      <div className="mt-3 grid gap-5 lg:grid-cols-2">
        <section>
          <h3 className="mb-1.5 text-sm font-semibold">Diagnóstico técnico</h3>
          <ul className="space-y-1.5">
            {rel.diagnostico_tecnico.map((t, i) => (
              <li key={i} className="flex gap-2 text-sm leading-snug">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue" />
                <span className="[overflow-wrap:anywhere]">{t}</span>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3 className="mb-1.5 text-sm font-semibold">Ações de mitigação</h3>
          <ol className="space-y-2">
            {rel.acoes_mitigacao.map((a, i) => (
              <li key={i} className="rounded-sm border border-line bg-white p-2.5">
                <div className="flex items-start gap-2">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-sm bg-bar text-xs font-semibold text-white">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold leading-snug">
                      {a.titulo}
                      {a.onde && <span className="ml-1.5 rounded-sm bg-page px-1.5 py-0.5 text-[11px] font-medium text-soft">{a.onde}</span>}
                    </p>
                    {a.detalhe && <p className="mt-0.5 text-sm leading-snug text-ink/80 [overflow-wrap:anywhere]">{a.detalhe}</p>}
                    {a.comando && <Comando texto={a.comando} />}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>

      {rel.ressalvas && (
        <p className="mt-3 flex items-start gap-1.5 rounded-sm border-l-4 border-warn bg-page p-2 text-xs leading-snug text-soft">
          <Info size={13} className="mt-0.5 shrink-0" />
          <span>{rel.ressalvas}</span>
        </p>
      )}
    </div>
  )
}

export default function RelatorioIA({ dados, apiBase, onAtualizar }) {
  const ia = dados?.relatorio_ia
  const estado = ia?.estado ?? 'ocioso'
  const [enviando, setEnviando] = useState(false)
  const [erroLocal, setErroLocal] = useState('')

  async function solicitar() {
    setEnviando(true)
    setErroLocal('')
    try {
      const r = await fetch(`${apiBase.replace(/\/$/, '')}/api/ia/relatorio/gerar`, { method: 'POST' })
      if (!r.ok) {
        const j = await r.json().catch(() => null)
        throw new Error(j?.detail || `Erro ${r.status}`)
      }
      await onAtualizar?.()
    } catch (e) {
      setErroLocal(e.message)
    } finally {
      setEnviando(false)
    }
  }

  const temIncidente = (ia?.incidentes?.length ?? 0) > 0
  const mostrarBotao = ia && estado !== 'desativado' && temIncidente
  const ocupado = estado === 'gerando' || enviando
  const rel = ia?.relatorio
  const jaTemAtual = rel && !ia.desatualizado
  const alerta = estado === 'erro' || estado === 'limite' || (estado === 'pronto' && ia?.mensagem)

  const sub = ia?.modelo && estado !== 'desativado'
    ? `Diagnóstico e mitigação gerados por IA (${ia.modelo})`
    : 'Resumo automático do motor de análise'

  return (
    <Card titulo="Relatório de incidente" sub={sub} rolagem={false}>
      <div className="space-y-3">
        {(temIncidente || mostrarBotao) && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <ShieldAlert size={15} className="text-warn" />
              {ia?.incidentes?.map((i) => (
                <span key={i} className="rounded-sm bg-page px-2 py-0.5 text-xs tabular-nums">{i}</span>
              ))}
            </div>
            {mostrarBotao && (
              <button
                onClick={solicitar}
                disabled={!ia.pode_solicitar || ocupado}
                className="flex items-center gap-1.5 rounded-sm border border-line bg-white px-3 py-1.5 text-xs font-medium hover:bg-page disabled:cursor-not-allowed disabled:opacity-50"
                title={!ia.pode_solicitar && ia.espera_s > 0 ? `Disponível em ${ia.espera_s} s` : undefined}
              >
                {ocupado ? <Loader2 size={14} className="animate-spin" /> : jaTemAtual ? <RefreshCw size={14} /> : <Sparkles size={14} />}
                {jaTemAtual ? 'Regenerar análise' : 'Gerar análise'}
                {!ia.pode_solicitar && !ocupado && ia.espera_s > 0 && <span className="tabular-nums text-soft">({ia.espera_s}s)</span>}
              </button>
            )}
          </div>
        )}

        {(estado === 'gerando' || estado === 'aguardando') && (
          <p className="flex items-center gap-2 rounded-sm bg-page p-2.5 text-sm text-soft">
            <Loader2 size={15} className="shrink-0 animate-spin" />
            {ia.mensagem || 'Gerando análise…'}
          </p>
        )}

        {ia?.mensagem && estado !== 'gerando' && estado !== 'aguardando' && (
          <p className={`flex items-start gap-1.5 rounded-sm p-2.5 text-sm ${alerta ? 'bg-warn/10 text-warn' : 'bg-page text-soft'}`}>
            <Info size={15} className="mt-0.5 shrink-0" />
            <span>{ia.mensagem}</span>
          </p>
        )}

        {erroLocal && <p className="rounded-sm bg-bad/10 p-2.5 text-sm text-bad">{erroLocal}</p>}

        {rel ? (
          <Relatorio rel={rel} ia={ia} />
        ) : (
          <div>
            {estado !== 'ocioso' && (
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-soft">Resumo automático (sem IA)</p>
            )}
            <p className="whitespace-pre-line rounded-sm border-l-4 border-blue bg-page p-3 text-sm leading-relaxed [overflow-wrap:anywhere]">
              {dados?.relatorio_llm || 'Aguardando o motor de análise…'}
            </p>
          </div>
        )}

        {ia && estado !== 'desativado' && (
          <p className="text-right text-[11px] text-soft">
            Modo {ia.modo} · {ia.chamadas_restantes_hora} chamadas restantes nesta hora
          </p>
        )}
      </div>
    </Card>
  )
}