import { tipoDe } from '../theme/tipos'

export default function Tag({ t }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${tipoDe(t).tag}`}>
      {String(t).replace('_', ' ')}
    </span>
  )
}