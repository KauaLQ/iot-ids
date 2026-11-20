import { useEffect, useRef } from 'react'
import { useStatus } from './hooks/useStatus'
import { useToast } from './components/Toast'
import Header from './components/Header'
import StatusBanner from './components/StatusBanner'
import Kpis from './components/Kpis'
import { Timeline, Donut } from './components/Charts'
import Dispositivos from './components/Dispositivos'
import { Historico, Feed } from './components/Panels'
import RelatorioIA from './components/RelatorioIA'

export default function App() {
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const { dados, conexao, latencia, ultimaLeitura, serie, alertas, recarregar } = useStatus(apiBase)
  const toast = useToast()

  const ultimoAlerta = useRef(null)
  useEffect(() => {
    const novo = alertas[0]
    if (novo && novo.id !== ultimoAlerta.current) {
      ultimoAlerta.current = novo.id
      toast(`Possível ${novo.tipo_ataque}: ${novo.ip_dispositivo} → ${novo.ip_vitima}:${novo.porta_vitima}`,
        { tom: 'bad', duracao: 8000 })
    }
  }, [alertas, toast])

  const anterior = useRef('conectando')
  useEffect(() => {
    if (conexao === 'offline' && anterior.current !== 'offline') toast('Sem comunicação com o backend', { tom: 'warn', key: 'conexao', duracao: 5000 })
    if (conexao === 'online' && anterior.current === 'offline') toast('Comunicação com o backend restabelecida', { tom: 'ok', key: 'conexao' })
    anterior.current = conexao
  }, [conexao, toast])

  return (
    <div className="flex min-h-screen flex-col">
      <Header dados={dados} conexao={conexao} latencia={latencia} ultimaLeitura={ultimaLeitura} onAtualizar={recarregar} />
      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-8 sm:px-6">
        <StatusBanner dados={dados} conexao={conexao} />
        <Kpis dados={dados} />
        <section className="grid items-stretch gap-4 xl:grid-cols-3">
          <div className="xl:col-span-2"><Timeline serie={serie} /></div>
          <Donut distribuicao={dados?.distribuicao_trafego} />
        </section>
        <section className="grid gap-4 lg:grid-cols-2">
          <Dispositivos atacantes={dados?.dispositivos_atacantes} />
          <Historico alertas={alertas} />
        </section>
        <RelatorioIA dados={dados} apiBase={apiBase} onAtualizar={recarregar} />
        <Feed feed={dados?.feed_tempo_real || []} />
      </main>
    </div>
  )
}