import { useState } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import Card from './Card'

const COR = { Benigno: '#2b8fd1', PortScan: '#ee8a2b', 'C&C': '#d6409f', DDoS: '#8a5bd0', Botnet_Okiru: '#a8a82a', Ataque_Generico: '#c94545' }
const corDe = (t) => COR[t] || '#c94545'

// Tooltip claro, texto escuro: contraste total
const tip = {
  contentStyle: { background: '#ffffff', border: '1px solid #d3d8de', borderRadius: 4, boxShadow: '0 2px 8px rgba(0,0,0,.12)', fontSize: 13 },
  labelStyle: { color: '#1f2933', fontWeight: 600, marginBottom: 2 },
  itemStyle: { color: '#1f2933' },
  cursor: { fill: 'rgba(31,41,51,.05)', stroke: '#d3d8de' },
}

const PERIODOS = [
  { id: '1m', label: '1 min', n: 30 },
  { id: '5m', label: '5 min', n: 150 },
  { id: 'all', label: 'Tudo', n: 450 },
]

export function Timeline({ serie }) {
  const [p, setP] = useState('5m')
  const dados = serie.slice(-PERIODOS.find((x) => x.id === p).n)
  return (
    <Card titulo="Tráfego ao longo do tempo" sub="Fluxos benignos e suspeitos por leitura" className="h-full">
      <div className="mb-2 flex justify-end">
        <div className="flex rounded-sm border border-line text-xs">
          {PERIODOS.map((x) => (
            <button key={x.id} onClick={() => setP(x.id)}
              className={`px-3 py-1 ${p === x.id ? 'bg-bar text-white' : 'text-soft hover:bg-page'}`}>{x.label}</button>
          ))}
        </div>
      </div>
      <div className="h-60">
        <ResponsiveContainer>
          <AreaChart data={dados}>
            <defs>
              <linearGradient id="gB" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2b8fd1" stopOpacity={0.25} /><stop offset="100%" stopColor="#2b8fd1" stopOpacity={0.02} /></linearGradient>
              <linearGradient id="gM" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c94545" stopOpacity={0.3} /><stop offset="100%" stopColor="#c94545" stopOpacity={0.02} /></linearGradient>
            </defs>
            <CartesianGrid stroke="#e5e8ec" vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="hora" stroke="#66727f" fontSize={12} minTickGap={50} tickLine={false} />
            <YAxis stroke="#66727f" fontSize={12} allowDecimals={false} width={36} tickLine={false} axisLine={false} />
            <Tooltip {...tip} />
            <Area type="monotone" dataKey="benignos" name="Benignos" stroke="#2b8fd1" fill="url(#gB)" strokeWidth={2} isAnimationActive={false} />
            <Area type="monotone" dataKey="suspeitos" name="Suspeitos" stroke="#c94545" fill="url(#gM)" strokeWidth={2} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export function Donut({ distribuicao }) {
  const itens = Object.entries(distribuicao || {}).map(([nome, valor]) => ({ nome, valor }))
  const total = itens.reduce((a, b) => a + b.valor, 0)
  const benigno = itens.find((i) => i.nome === 'Benigno')?.valor || 0
  return (
    <Card titulo="Normal vs. suspeito" sub="Proporção por tipo de tráfego" className="h-full">
      <div className="relative h-48">
        {total === 0 ? <p className="grid h-full place-items-center text-sm text-soft">Sem dados ainda</p> : (
          <>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={itens} dataKey="valor" nameKey="nome" innerRadius={55} outerRadius={78} paddingAngle={2} stroke="#fff" isAnimationActive={false}>
                  {itens.map((i) => <Cell key={i.nome} fill={corDe(i.nome)} />)}
                </Pie>
                <Tooltip {...tip} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
              <div><p className="text-2xl font-semibold tabular-nums">{Math.round((benigno / total) * 100)}%</p><p className="text-xs text-soft">benigno</p></div>
            </div>
          </>
        )}
      </div>
      <ul className="mt-3 space-y-1 text-sm">
        {itens.map((i) => (
          <li key={i.nome} className="flex items-center justify-between">
            <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm" style={{ background: corDe(i.nome) }} />{i.nome}</span>
            <b className="tabular-nums">{i.valor}</b>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function AtacantesBar({ atacantes }) {
  const dados = (atacantes || []).map((a) => ({ nome: `${a.ip_dispositivo} · ${a.tipo_ataque}`, fluxos: a.fluxos_maliciosos, tipo: a.tipo_ataque }))
  return (
    <Card titulo="Fluxos suspeitos por dispositivo" sub="Dispositivo e tipo de tráfego" className="h-[22rem]">
      {dados.length === 0 ? <p className="grid h-full place-items-center text-sm text-ok">Nenhum dispositivo em observação</p> : (
        <div style={{ height: Math.max(dados.length * 40 + 16, 200) }}>
          <ResponsiveContainer>
            <BarChart data={dados} layout="vertical" margin={{ left: 0, right: 12 }}>
              <CartesianGrid stroke="#e5e8ec" horizontal={false} strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} stroke="#66727f" fontSize={12} tickLine={false} />
              <YAxis type="category" dataKey="nome" width={200} stroke="#1f2933" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip {...tip} />
              <Bar dataKey="fluxos" name="Fluxos" radius={2} barSize={16} isAnimationActive={false}>
                {dados.map((d, i) => <Cell key={i} fill={corDe(d.tipo)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  )
}
