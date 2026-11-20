import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const ThemeCtx = createContext({ tema: 'dark', alternar: () => {} })

export function ThemeProvider({ children }) {
  const [tema, setTema] = useState(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', tema === 'dark')
    try { localStorage.setItem('iot-ids-tema', tema) } catch { /* modo privado */ }
  }, [tema])

  const alternar = useCallback(() => setTema((t) => (t === 'dark' ? 'light' : 'dark')), [])
  const value = useMemo(() => ({ tema, alternar }), [tema, alternar])
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}

export const useTheme = () => useContext(ThemeCtx)