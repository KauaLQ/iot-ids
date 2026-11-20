import { useState } from 'react'
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Card from './Card'
import ProgressBar from './ProgressBar'
import { useTheme } from '../theme/ThemeContext'
import { MONO, paletaGrafico, tipoDe } from '../theme/tipos'
import { fmtInt } from '../format'

const PERIODOS = [
  { id: '1m', label: '1 min', n: 30 },
  { id: '5m', label: '5 min', n: 150 },
  { id: 'all', label: 'Tudo', n: 450 },
]

const tooltipProps = (p) => ({
  contentStyle: {
    background: p.tooltipBg, border: `1px solid ${p.tooltipBorda}`, borderRadius: 10,
    boxShadow: '0 8px 24px rgba(0,0,0,.18)', fontSize: 12, padding: '8px 10px',
  },
  labelStyle: { color: p.tooltipTexto, fontWeight: 600, marginBottom: 2, fontFamily: MONO },
  itemStyle: { color: p.tooltipTexto, padding: 0 },
  cursor: { stroke: p.grade },
})

function Segmentado({ opcoes, valor, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 text-xs dark:border-zinc-800 dark:bg-zinc-900">
      {opcoes.map((o) => (
        <button key={o.id} type="button" onClick={() => onChange(o.id)}
          className={`cursor-pointer rounded-md px-2.5 py-1 font-medium transition-colors ${
            valor === o.id
              ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
              : 'text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Timeline({ serie }) {
  const { tema } = useTheme()
  const p = paletaGrafico(tema)
  const [per, setPer] = useState('5m')
  const dados = serie.slice(-PERIODOS.find((x) => x.id === per).n)
  const tick = { fill: p.eixo, fontSize: 11, fontFamily: MONO }

  return (
    <Card titulo="Tráfego ao longo do tempo" sub="Fluxos benignos e suspeitos por leitura" className="h-full"
      acao={<Segmentado opcoes={PERIODOS} valor={per} onChange={setPer} />}>
      <div className="h-60">
        <ResponsiveContainer>
          <AreaChart data={dados} margin={{ top: 6, right: 4, left: -8, bottom: 0 }}>
            <defs>
              <linearGradient id="gB" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={p.benigno} stopOpacity={0.22} /><stop offset="100%" stopColor={p.benigno} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gM" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={p.suspeito} stopOpacity={0.28} /><stop offset="100%" stopColor={p.suspeito} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={p.grade} vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="hora" tick={tick} minTickGap={56} tickLine={false} axisLine={{ stroke: p.grade }} />
            <YAxis tick={tick} allowDecimals={false} width={40} tickLine={false} axisLine={false} />
            <Tooltip {...tooltipProps(p)} />
            <Area type="monotone" dataKey="benignos" name="Benignos" stroke={p.benigno} fill="url(#gB)" strokeWidth={1.75} isAnimationActive={false} />
            <Area type="monotone" dataKey="suspeitos" name="Suspeitos" stroke={p.suspeito} fill="url(#gM)" strokeWidth={1.75} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex items-center gap-4 text-[11px] text-zinc-500 dark:text-zinc-400">
        <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-emerald-500" />Benignos</span>
        <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-rose-500" />Suspeitos</span>
      </div>
    </Card>
  )
}

export function Donut({ distribuicao }) {
  const { tema } = useTheme()
  const p = paletaGrafico(tema)
  const itens = Object.entries(distribuicao || {}).map(([nome, valor]) => ({ nome, valor })).sort((a, b) => b.valor - a.valor)
  const total = itens.reduce((a, b) => a + b.valor, 0)
  const benigno = itens.find((i) => i.nome === 'Benigno')?.valor || 0

  return (
    <Card titulo="Normal vs. suspeito" sub="Proporção por tipo de tráfego" className="h-full">
      <div className="relative h-44">
        {total === 0 ? (
          <p className="grid h-full place-items-center text-xs text-zinc-400 dark:text-zinc-500">Sem dados ainda</p>
        ) : (
          <>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={itens} dataKey="valor" nameKey="nome" innerRadius={56} outerRadius={76}
                  paddingAngle={3} stroke="none" isAnimationActive={false}>
                  {itens.map((i) => <Cell key={i.nome} fill={tipoDe(i.nome).cor} />)}
                </Pie>
                <Tooltip {...tooltipProps(p)} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
              <div>
                <p className="font-mono text-2xl font-semibold tabular-nums tracking-tight">{Math.round((benigno / total) * 100)}%</p>
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">benigno</p>
              </div>
            </div>
          </>
        )}
      </div>

      <ul className="mt-4 space-y-3">
        {itens.map((i) => {
          const pct = total ? (i.valor / total) * 100 : 0
          const cor = tipoDe(i.nome).cor
          return (
            <li key={i.nome}>
              <div className="mb-1.5 flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 font-medium text-zinc-700 dark:text-zinc-300">
                  <span className="h-2 w-2 rounded-full" style={{ background: cor }} />{i.nome}
                </span>
                <span className="font-mono tabular-nums text-zinc-500 dark:text-zinc-400">
                  {fmtInt(i.valor)} <span className="text-zinc-400 dark:text-zinc-500">· {pct.toFixed(1)}%</span>
                </span>
              </div>
              <ProgressBar valor={pct} cor={cor} altura="h-1" />
            </li>
          )
        })}
      </ul>
    </Card>
  )
}