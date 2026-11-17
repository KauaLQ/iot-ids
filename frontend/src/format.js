// Sempre 2 casas decimais (o backend envia float32, ex.: 89.2300033569336)
export const fmtPct = (v) => `${Number(v ?? 0).toFixed(2)}%`
