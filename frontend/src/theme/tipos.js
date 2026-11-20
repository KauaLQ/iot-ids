// Cores por classe de tráfego: `cor` (hex) para gráficos/barras, `tag` (classes) para badges.
const ROSE = 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/25'

export const TIPOS = {
  Benigno: { cor: '#10b981', tag: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20' },
  PortScan: { cor: '#f59e0b', tag: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/25' },
  DDoS: { cor: '#f43f5e', tag: ROSE },
  'C&C': { cor: '#8b5cf6', tag: 'bg-violet-500/10 text-violet-700 dark:text-violet-400 border-violet-500/25' },
  Botnet_Okiru: { cor: '#6366f1', tag: 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-500/25' },
  Ataque_Generico: { cor: '#0ea5e9', tag: 'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/25' },
}
const DESCONHECIDO = { cor: '#f43f5e', tag: ROSE }
export const tipoDe = (t) => TIPOS[t] ?? DESCONHECIDO

// Fonte mono usada dentro do SVG do Recharts (var() não é confiável em atributos SVG)
export const MONO = "'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, monospace"

// Paleta dos gráficos por tema (os mesmos zincs do design system)
export function paletaGrafico(tema) {
  const escuro = tema === 'dark'
  return {
    grade: escuro ? '#27272a' : '#e4e4e7',
    eixo: escuro ? '#71717a' : '#a1a1aa',
    tooltipBg: escuro ? '#18181b' : '#ffffff',
    tooltipBorda: escuro ? '#3f3f46' : '#e4e4e7',
    tooltipTexto: escuro ? '#fafafa' : '#18181b',
    benigno: '#10b981',
    suspeito: '#f43f5e',
  }
}