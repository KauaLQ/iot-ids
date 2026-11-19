import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_PONTOS = 450 // ~15 min a cada 2 s
const FALHAS_PARA_OFFLINE = 3 // tolera lentidão pontual do backend
const hora = (d) => d.toLocaleTimeString('pt-BR')

export function useStatus(apiBase, intervaloMs = 2000) {
  const [dados, setDados] = useState(null)
  const [conexao, setConexao] = useState('conectando') // conectando | online | offline
  const [serie, setSerie] = useState([])
  const [alertas, setAlertas] = useState([])
  const ultimaAssinatura = useRef('')
  const falhas = useRef(0)

  const buscar = useCallback(async () => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 6000)
    try {
      const r = await fetch(`${apiBase.replace(/\/$/, '')}/api/status?t=${Date.now()}`, { signal: ctrl.signal })
      if (!r.ok) throw new Error(r.status)
      const d = await r.json()
      falhas.current = 0
      setDados(d)
      setConexao('online')

      const agora = new Date()
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
    } catch {
      falhas.current += 1
      if (falhas.current >= FALHAS_PARA_OFFLINE) setConexao('offline')
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

  // recarregar: força uma leitura imediata (usado após pedir a análise de IA)
  return { dados, conexao, serie, alertas, recarregar: buscar }
}