import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_PONTOS = 450 // ~15 min a cada 2 s
const FALHAS_PARA_OFFLINE = 3 // tolera lentidão pontual do backend
const hora = (d) => d.toLocaleTimeString('pt-BR', { hour12: false })

export function useStatus(apiBase, intervaloMs = 2000) {
  const [dados, setDados] = useState(null)
  const [conexao, setConexao] = useState('conectando') // conectando | online | offline
  const [latencia, setLatencia] = useState(null)       // ms do último /api/status
  const [ultimaLeitura, setUltimaLeitura] = useState('')
  const [serie, setSerie] = useState([])
  const [alertas, setAlertas] = useState([])
  const ultimaAssinatura = useRef('')
  const falhas = useRef(0)

  // Retorna true/false (leitura bem-sucedida?) — usado pelo botão de refresh do header.
  const buscar = useCallback(async () => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 6000)
    try {
      const t0 = performance.now()
      const r = await fetch(`${apiBase.replace(/\/$/, '')}/api/status?t=${Date.now()}`, { signal: ctrl.signal })
      setLatencia(Math.round(performance.now() - t0))
      if (!r.ok) throw new Error(r.status)
      const d = await r.json()
      falhas.current = 0
      setDados(d)
      setConexao('online')

      const agora = new Date()
      setUltimaLeitura(hora(agora))
      const suspeitos = d.total_ataques_detectados || 0
      setSerie((s) => [...s, {
        t: agora.getTime(), hora: hora(agora),
        benignos: Math.max((d.total_fluxos_analisados || 0) - suspeitos, 0),
        suspeitos,
      }].slice(-MAX_PONTOS))

      const atacantes = d.dispositivos_atacantes || []
      const assinatura = atacantes.map((a) => `${a.ip_dispositivo}:${a.tipo_ataque}`).join('|')
      if (assinatura && assinatura !== ultimaAssinatura.current) {
        const novos = atacantes.map((a) => ({ id: `${agora.getTime()}-${a.ip_dispositivo}-${a.tipo_ataque}`, hora: hora(agora), ...a }))
        setAlertas((h) => [...novos, ...h].slice(0, 50))
      }
      ultimaAssinatura.current = assinatura
      return true
    } catch {
      falhas.current += 1
      if (falhas.current >= FALHAS_PARA_OFFLINE) setConexao('offline')
      return false
    } finally {
      clearTimeout(timer)
    }
  }, [apiBase])

  useEffect(() => {
    falhas.current = 0
    buscar()
    const id = setInterval(buscar, intervaloMs)
    return () => clearInterval(id)
  }, [buscar, intervaloMs])

  return { dados, conexao, latencia, ultimaLeitura, serie, alertas, recarregar: buscar }
}