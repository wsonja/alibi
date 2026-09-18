/** Simple gold line icons per evidence kind (lib/evidenceKind.ts). */
import { evidenceKind, type EvidenceKind } from '@/lib/evidenceKind'

export interface EvidenceIconProps {
  kind?: EvidenceKind
  /** derive the kind from a name (+ description) when `kind` is not given */
  name?: string
  description?: string
  size?: number
  className?: string
  color?: string
}

export function EvidenceIcon({ kind, name, description, size = 28, className, color = 'currentColor' }: EvidenceIconProps) {
  const k: EvidenceKind = kind ?? evidenceKind(name ?? '', description)
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, className, 'aria-hidden': true as const, focusable: 'false' as const }
  switch (k) {
    case 'bottle':
      return (
        <svg {...common}>
          <path d="M10 3h4v3l2 3v11a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V9l2-3z" />
          <path d="M8 13h8" />
        </svg>
      )
    case 'glass':
      return (
        <svg {...common}>
          <path d="M7 3h10l-1 9a4 4 0 0 1-8 0z" />
          <path d="M12 16v4M9 20h6" />
        </svg>
      )
    case 'letter':
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="14" rx="1.5" />
          <path d="M3 7l9 6 9-6" />
        </svg>
      )
    case 'book':
      return (
        <svg {...common}>
          <path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z" />
          <path d="M5 17a2 2 0 0 1 2-2h11M9 8h5" />
        </svg>
      )
    case 'jar':
      return (
        <svg {...common}>
          <rect x="6" y="7" width="12" height="14" rx="2" />
          <path d="M8 4h8v3H8zM9 12h6M12 10v5" />
          <path d="M9 17l6-2" />
        </svg>
      )
    case 'ash':
      return (
        <svg {...common}>
          <path d="M4 19h16M6 19c1-3 3-4 6-4s5 1 6 4" />
          <path d="M12 4c-1 2 1 3 0 5M9 6c-1 1 0 2 0 3M15 6c-1 1 0 2 0 3" />
        </svg>
      )
    case 'case':
      return (
        <svg {...common}>
          <rect x="3" y="7" width="18" height="13" rx="2" />
          <path d="M9 7V5a3 3 0 0 1 6 0v2M3 12h18" />
        </svg>
      )
    case 'jewel':
      return (
        <svg {...common}>
          <path d="M7 4h10l4 5-9 11L3 9z" />
          <path d="M3 9h18M9 9l3 11 3-11" />
        </svg>
      )
    case 'paper':
      return (
        <svg {...common}>
          <path d="M6 3h8l4 4v14H6z" />
          <path d="M14 3v4h4M9 12h6M9 16h6" />
        </svg>
      )
    case 'key':
      return (
        <svg {...common}>
          <circle cx="8" cy="9" r="4" />
          <path d="M11 12l9 9M17 18l2-2M14 15l2-2" />
        </svg>
      )
    case 'weapon':
      return (
        <svg {...common}>
          <path d="M14 4l6 6-9 9-3 1 1-3z" />
          <path d="M5 21l-2-2M12 9l3 3" />
        </svg>
      )
    case 'phone':
      return (
        <svg {...common}>
          <rect x="7" y="3" width="10" height="18" rx="2" />
          <path d="M11 18h2" />
        </svg>
      )
    case 'photo':
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="14" rx="1.5" />
          <circle cx="9" cy="10" r="2" />
          <path d="M21 16l-5-5-8 8" />
        </svg>
      )
    case 'footprint':
      return (
        <svg {...common}>
          <path d="M8 4c2 0 3 2 3 5s-1 4-2 6-3 3-4 1 0-4 0-7 1-5 3-5z" />
          <path d="M16 8c2 0 3 2 3 5s-1 4-2 6-3 3-4 1 0-4 0-7 1-5 3-5z" />
        </svg>
      )
    default:
      return (
        <svg {...common}>
          <circle cx="10" cy="10" r="6" />
          <path d="M14.5 14.5L21 21" />
        </svg>
      )
  }
}

export default EvidenceIcon
