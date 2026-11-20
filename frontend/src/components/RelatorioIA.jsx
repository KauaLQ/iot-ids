import { useState } from 'react'
import { Check, Copy, Info, Loader2, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react'
import Card from './Card'
import { BTN_PRIMARIO } from '../theme/ui'

const SEV = {
  alta: { rotulo: 'Severidade alta', cls: 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/25' },
  media: { rotulo: 'Severidade média', cls: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/25' },
  baixa: { rotulo: 'Severidade baixa', cls: 'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/25' },
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
    <div className="mt-2 flex items-start gap-1 rounded-lg border border-zinc-800 bg-zinc-950 p-2.5">
      <code className="min-w-0 flex-1 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-zinc-300">{texto}</code>
      <button onClick={copiar} aria-label="Copiar comando"
        className="shrink-0 cursor-pointer rounded p-1 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100">
        {ok ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
      </button>
    </div>
  )
}

function Relatorio({ rel, ia }) {
  const sev = SEV[rel.severidade] ?? SEV.media
  return (
    <div className={ia.desatualizado ? 'opacity-60' : ''}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${sev.cls}`}>{sev.rotulo}</span>
        {ia.desatualizado && (
          <span className="rounded-md border border-zinc-200 bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500 dark:border-zinc-700/60 dark:bg-zinc-800/80 dark:text-zinc-400">Análise anterior</span>
        )}
        {ia.gerado_em && <span className="font-mono text-[11px] tabular-nums text-zinc-400">Gerado em {ia.gerado_em}</span>}
      </div>
      <p className="mt-3 text-sm font-medium leading-snug">{rel.resumo}</p>

      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Diagnóstico técnico</h3>
          <ul className="space-y-2">
            {rel.diagnostico_tecnico.map((t, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-snug">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
                <span className="text-zinc-700 [overflow-wrap:anywhere] dark:text-zinc-300">{t}</span>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Ações de mitigação</h3>
          <ol className="space-y-2">
            {rel.acoes_mitigacao.map((a, i) => (
              <li key={i} className="rounded-lg border border-zinc-200 bg-zinc-50/50 p-3 dark:border-zinc-800 dark:bg-zinc-900/40">
                <div className="flex items-start gap-2.5">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-zinc-900 font-mono text-[11px] font-medium text-white dark:bg-zinc-100 dark:text-zinc-900">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold leading-snug">
                      {a.titulo}
                      {a.onde && <span className="ml-1.5 rounded border border-zinc-200 bg-zinc-100 px-1.5 py-0.5 font-mono text-[10px] font-medium text-zinc-500 dark:border-zinc-700/60 dark:bg-zinc-800/80 dark:text-zinc-400">{a.onde}</span>}
                    </p>
                    {a.detalhe && <p className="mt-1 text-xs leading-relaxed text-zinc-600 [overflow-wrap:anywhere] dark:text-zinc-400">{a.detalhe}</p>}
                    {a.comando && <Comando texto={a.comando} />}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>

      {rel.ressalvas && (
        <p className="mt-4 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-700 dark:text-amber-400">
          <Info size={14} className="mt-0.5 shrink-0" />
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
    <Card id="relatorio" titulo="Relatório de incidente" sub={sub} rolagem={false} className="scroll-mt-20">
      <div className="space-y-4">
        {(temIncidente || mostrarBotao) && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <ShieldAlert size={15} className="text-rose-500" />
              {ia?.incidentes?.map((i) => (
                <span key={i} className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5 font-mono text-[11px] tabular-nums dark:border-zinc-800 dark:bg-zinc-900">{i}</span>
              ))}
            </div>
            {mostrarBotao && (
              <button onClick={solicitar} disabled={!ia.pode_solicitar || ocupado} className={BTN_PRIMARIO}
                title={!ia.pode_solicitar && ia.espera_s > 0 ? `Disponível em ${ia.espera_s} s` : undefined}>
                {ocupado ? <Loader2 size={14} className="animate-spin" /> : jaTemAtual ? <RefreshCw size={14} /> : <Sparkles size={14} />}
                {jaTemAtual ? 'Regenerar análise' : 'Gerar análise'}
                {!ia.pode_solicitar && !ocupado && ia.espera_s > 0 && <span className="font-mono tabular-nums opacity-60">({ia.espera_s}s)</span>}
              </button>
            )}
          </div>
        )}

        {(estado === 'gerando' || estado === 'aguardando') && (
          <p className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400">
            <Loader2 size={14} className="shrink-0 animate-spin" />
            {ia.mensagem || 'Gerando análise…'}
          </p>
        )}

        {ia?.mensagem && estado !== 'gerando' && estado !== 'aguardando' && (
          <p className={`flex items-start gap-2 rounded-lg border p-3 text-xs leading-relaxed ${
            alerta
              ? 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400'
              : 'border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400'}`}>
            <Info size={14} className="mt-0.5 shrink-0" />
            <span>{ia.mensagem}</span>
          </p>
        )}

        {erroLocal && (
          <p className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-400">{erroLocal}</p>
        )}

        {rel ? (
          <Relatorio rel={rel} ia={ia} />
        ) : (
          <div>
            {estado !== 'ocioso' && (
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Resumo automático (sem IA)</p>
            )}
            <p className="whitespace-pre-line rounded-lg border border-zinc-200 bg-zinc-50 p-3 font-mono text-[12px] leading-relaxed text-zinc-700 [overflow-wrap:anywhere] dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-300">
              {dados?.relatorio_llm || 'Aguardando o motor de análise…'}
            </p>
          </div>
        )}

        {ia && estado !== 'desativado' && (
          <p className="text-right font-mono text-[11px] text-zinc-400 dark:text-zinc-500">
            Modo {ia.modo} · {ia.chamadas_restantes_hora} chamadas restantes nesta hora
          </p>
        )}
      </div>
    </Card>
  )
}