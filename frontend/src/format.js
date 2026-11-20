// Sempre 2 casas decimais (o backend envia float32, ex.: 89.2300033569336)
export const fmtPct = (v) => `${Number(v ?? 0).toFixed(2)}%`

// Inteiros com separador de milhar pt-BR (1.482.910)
export const fmtInt = (v) => Number(v ?? 0).toLocaleString('pt-BR')