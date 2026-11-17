import { useEffect, useRef } from 'react'
import { ToastContainer, toast } from 'react-toastify'
import { useStatus } from './hooks/useStatus'
import Header from './components/Header'
import Kpis from './components/Kpis'
import { Timeline, Donut, AtacantesBar } from './components/Charts'
import { Incidente, Historico, Feed } from './components/Panels'

export default function App() {
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const { dados, conexao, serie, alertas } = useStatus(apiBase)

  const ultimoAlerta = useRef(null)
  useEffect(() => {
    const novo = alertas[0]
    if (novo && novo.id !== ultimoAlerta.current) {
      ultimoAlerta.current = novo.id
      toast.warn(`Possível ${novo.tipo_ataque}: ${novo.ip_dispositivo} → ${novo.ip_vitima}:${novo.porta_vitima}`, { autoClose: 8000 })
    }
  }, [alertas])

  const anterior = useRef('conectando')
  useEffect(() => {
    if (conexao === 'offline' && anterior.current !== 'offline') toast.info('Sem comunicação com o backend.', { toastId: 'off' })
    if (conexao === 'online' && anterior.current === 'offline') toast.success('Comunicação com o backend restabelecida.')
    anterior.current = conexao
  }, [conexao])

  return (
    <div className="min-h-screen">
      <Header dados={dados} conexao={conexao} />
      <main className="mx-auto max-w-[1500px] space-y-4 p-4">
        {dados?.erro_modelo && (
          <div className="rounded-sm border border-warn/40 bg-warn/10 p-3 text-sm text-warn">{dados.erro_modelo}</div>
        )}
        <Kpis dados={dados} />
        <section className="grid items-stretch gap-4 xl:grid-cols-3">
          <div className="xl:col-span-2"><Timeline serie={serie} /></div>
          <Donut distribuicao={dados?.distribuicao_trafego} />
        </section>
        <section className="grid gap-4 lg:grid-cols-3">
          <AtacantesBar atacantes={dados?.dispositivos_atacantes} />
          <Incidente texto={dados?.relatorio_llm} />
          <Historico alertas={alertas} />
        </section>
        <Feed feed={dados?.feed_tempo_real || []} />
      </main>
      <ToastContainer position="bottom-right" theme="light" newestOnTop />
    </div>
  )
}
