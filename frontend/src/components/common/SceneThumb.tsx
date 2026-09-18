/**
 * SceneThumb — a CSS/SVG illustrated scene for a case preset (DESIGN §5.1 tiles, §5.2 crime scene, archive cards).
 * No external images: gradients + a silhouette per preset.
 */
import type { CasePreset } from '@/api/types'
import { cn } from '@/lib/cn'

export interface SceneThumbProps {
  preset: CasePreset | string
  className?: string
  /** decorative by default; pass a title to expose it to assistive tech */
  title?: string
  style?: React.CSSProperties
}

const SKY: Record<string, string> = {
  manor: 'linear-gradient(180deg, #0b1230 0%, #23163f 55%, #3a1a2a 100%)',
  liner: 'linear-gradient(180deg, #0a1a33 0%, #103555 45%, #0b2a3a 46%, #06202c 100%)',
  startup: 'linear-gradient(180deg, #0c0f1c 0%, #1a1f3a 60%, #0f1226 100%)',
  dorm: 'linear-gradient(180deg, #1b2440 0%, #3a3f66 60%, #cfd6e2 92%, #e6ebf2 100%)',
  room: 'linear-gradient(180deg, #2a1a24 0%, #3d2431 60%, #221419 100%)',
  other: 'linear-gradient(180deg, #1a1a1f 0%, #2d2a35 100%)',
}

function Manor() {
  return (
    <svg viewBox="0 0 180 110" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <circle cx="146" cy="24" r="11" fill="#f3e7cb" opacity=".9" />
      <circle cx="150" cy="21" r="10" fill="#23163f" opacity=".85" />
      {[20, 48, 75, 120, 165].map((x, i) => (
        <circle key={i} cx={x} cy={12 + (i % 3) * 7} r="1" fill="#f3e7cb" opacity=".8" />
      ))}
      {/* trees */}
      <path d="M6 96 L18 60 L30 96 Z M150 96 L164 58 L178 96 Z" fill="#070b18" />
      {/* manor */}
      <path d="M36 96 V56 H60 V44 L72 34 L84 44 V56 H96 V44 L108 34 L120 44 V56 H144 V96 Z" fill="#0d0a14" />
      <rect x="44" y="40" width="5" height="18" fill="#0d0a14" />
      <rect x="131" y="40" width="5" height="18" fill="#0d0a14" />
      {[46, 66, 100, 122].map((x) => (
        <rect key={x} x={x} y="64" width="8" height="10" fill="#e0bc63" opacity=".9" />
      ))}
      {[66, 100].map((x) => (
        <rect key={x} x={x} y="80" width="8" height="10" fill="#e0bc63" opacity=".6" />
      ))}
      <rect x="86" y="78" width="10" height="18" fill="#3a2116" />
      <rect x="0" y="96" width="180" height="14" fill="#08121a" />
      <path d="M0 100 Q90 92 180 100" stroke="#101c26" strokeWidth="2" fill="none" />
    </svg>
  )
}

function Liner() {
  return (
    <svg viewBox="0 0 180 110" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      {[14, 40, 66, 92, 130, 158].map((x, i) => (
        <circle key={i} cx={x} cy={10 + (i % 4) * 5} r="1" fill="#f3e7cb" opacity=".7" />
      ))}
      <circle cx="30" cy="22" r="8" fill="#f3e7cb" opacity=".85" />
      {/* hull */}
      <path d="M18 78 L30 62 H160 L170 78 Z" fill="#0d0d14" />
      <path d="M22 78 L164 78 L156 90 H34 Z" fill="#12141c" />
      <rect x="44" y="50" width="96" height="12" fill="#f3e7cb" opacity=".9" />
      <rect x="54" y="40" width="72" height="10" fill="#e6dcc0" opacity=".9" />
      {[62, 84, 106].map((x) => (
        <g key={x}>
          <rect x={x} y="22" width="10" height="20" fill="#9c1c1c" />
          <rect x={x} y="22" width="10" height="5" fill="#0d0d14" />
          <ellipse cx={x + 5} cy="18" rx="8" ry="4" fill="#3b3b44" opacity=".5" />
        </g>
      ))}
      {[48, 58, 68, 78, 88, 98, 108, 118, 128].map((x) => (
        <rect key={x} x={x} y="54" width="4" height="4" fill="#e0bc63" />
      ))}
      <path d="M0 80 Q20 74 40 80 T80 80 T120 80 T160 80 T200 80 V110 H0 Z" fill="#0b2a3a" />
      <path d="M0 88 Q20 82 40 88 T80 88 T120 88 T160 88 T200 88" stroke="#1f5570" strokeWidth="2" fill="none" />
      <path d="M0 98 Q25 92 50 98 T100 98 T150 98 T200 98" stroke="#1a4a60" strokeWidth="2" fill="none" />
    </svg>
  )
}

function Startup() {
  return (
    <svg viewBox="0 0 180 110" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      {/* window frame + skyline */}
      <rect x="10" y="8" width="160" height="70" fill="#0a0d1a" stroke="#3a3f5a" strokeWidth="3" />
      {[
        [16, 40, 14],
        [34, 26, 18],
        [56, 48, 10],
        [70, 18, 22],
        [96, 34, 16],
        [116, 22, 20],
        [140, 44, 12],
        [156, 30, 10],
      ].map(([x, y, w], i) => (
        <g key={i}>
          <rect x={x} y={y} width={w} height={78 - (y ?? 0)} fill="#161b33" />
          {[0, 1, 2, 3].map((r) => (
            <rect key={r} x={(x ?? 0) + 2} y={(y ?? 0) + 4 + r * 9} width={(w ?? 0) - 4} height="4" fill={r % 2 ? '#e0bc63' : '#8fb3ff'} opacity={0.35 + ((i + r) % 3) * 0.25} />
          ))}
        </g>
      ))}
      <line x1="90" y1="8" x2="90" y2="78" stroke="#3a3f5a" strokeWidth="3" />
      {/* desk with monitor */}
      <rect x="0" y="82" width="180" height="28" fill="#14121c" />
      <rect x="66" y="60" width="48" height="28" rx="2" fill="#0d1022" stroke="#4a5070" strokeWidth="2" />
      <rect x="70" y="64" width="40" height="20" fill="#1e2b4a" />
      <path d="M74 80 L82 70 L90 76 L98 66 L106 74" stroke="#3fa34d" strokeWidth="2" fill="none" />
      <rect x="86" y="88" width="8" height="5" fill="#4a5070" />
      <rect x="78" y="93" width="24" height="2" fill="#4a5070" />
      <rect x="126" y="76" width="18" height="10" rx="2" fill="#9c1c1c" />
      <circle cx="40" cy="86" r="5" fill="#e0bc63" opacity=".7" />
    </svg>
  )
}

function Dorm() {
  return (
    <svg viewBox="0 0 180 110" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      {[20, 60, 100, 140, 170].map((x, i) => (
        <circle key={i} cx={x} cy={14 + (i % 2) * 8} r="1.5" fill="#fff" opacity=".8" />
      ))}
      {/* clock tower */}
      <rect x="120" y="22" width="22" height="70" fill="#3b2a3a" />
      <path d="M118 22 L131 8 L144 22 Z" fill="#2a1e2a" />
      <circle cx="131" cy="36" r="6" fill="#f3e7cb" />
      <path d="M131 36 V32 M131 36 H134" stroke="#2b1b12" strokeWidth="1.2" />
      {/* hall */}
      <rect x="22" y="40" width="90" height="52" fill="#4a2f2a" />
      <rect x="22" y="36" width="90" height="6" fill="#2a1a18" />
      {[30, 46, 62, 78, 94].map((x) =>
        [48, 64, 78].map((y) => <rect key={`${x}${y}`} x={x} y={y} width="8" height="9" fill={(x + y) % 3 === 0 ? '#2a1a18' : '#e0bc63'} opacity=".9" />),
      )}
      <rect x="62" y="80" width="10" height="12" fill="#2a1a18" />
      {/* snow */}
      <rect x="0" y="92" width="180" height="18" fill="#e6ebf2" />
      <ellipse cx="60" cy="92" rx="70" ry="4" fill="#f5f8fb" />
      <path d="M150 92 L158 66 L166 92 Z" fill="#1d2b22" />
      <ellipse cx="158" cy="66" rx="5" ry="3" fill="#f5f8fb" />
    </svg>
  )
}

function Room() {
  return (
    <svg viewBox="0 0 180 110" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      {/* window with moon */}
      <rect x="112" y="14" width="46" height="40" fill="#0f1a33" stroke="#2b1b12" strokeWidth="3" />
      <circle cx="140" cy="28" r="7" fill="#f3e7cb" />
      <line x1="135" y1="14" x2="135" y2="54" stroke="#2b1b12" strokeWidth="2" />
      <line x1="112" y1="34" x2="158" y2="34" stroke="#2b1b12" strokeWidth="2" />
      {/* lamp */}
      <rect x="36" y="44" width="4" height="26" fill="#3a2116" />
      <path d="M22 46 L54 46 L48 30 L28 30 Z" fill="#e0bc63" />
      <circle cx="38" cy="52" r="26" fill="#f0c86e" opacity=".18" />
      {/* bed */}
      <rect x="10" y="70" width="110" height="22" rx="3" fill="#5a2a3a" />
      <rect x="10" y="64" width="110" height="10" rx="3" fill="#7a3a4a" />
      <rect x="16" y="58" width="30" height="10" rx="3" fill="#f3e7cb" />
      <rect x="6" y="52" width="6" height="40" fill="#3a2116" />
      <rect x="118" y="58" width="6" height="34" fill="#3a2116" />
      <rect x="0" y="92" width="180" height="18" fill="#1a0f0a" />
      {/* poster */}
      <rect x="70" y="16" width="26" height="30" fill="#2a3a5a" stroke="#2b1b12" strokeWidth="2" />
      <circle cx="83" cy="30" r="6" fill="#e0bc63" opacity=".7" />
    </svg>
  )
}

function Other() {
  return (
    <svg viewBox="0 0 180 110" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <rect x="20" y="16" width="140" height="78" fill="#f3e7cb" opacity=".08" stroke="#c9a24b" strokeWidth="1" strokeDasharray="4 3" />
      <path d="M40 60 Q70 30 100 60 T160 50" stroke="#c9a24b" strokeWidth="1.5" fill="none" strokeDasharray="3 3" />
      <circle cx="72" cy="52" r="16" fill="rgba(243,231,203,.2)" stroke="#c9a24b" strokeWidth="4" />
      <path d="M84 64 L104 84" stroke="#7a4b22" strokeWidth="8" strokeLinecap="round" />
      <path d="M84 64 L104 84" stroke="#c9a24b" strokeWidth="3" strokeLinecap="round" />
      <text x="126" y="40" fontFamily="Cinzel, serif" fontSize="10" fill="#e0bc63">
        ?
      </text>
    </svg>
  )
}

export function SceneThumb({ preset, className, title, style }: SceneThumbProps) {
  const key = (['manor', 'liner', 'startup', 'dorm', 'room'] as string[]).includes(preset) ? preset : 'other'
  const Scene = key === 'manor' ? Manor : key === 'liner' ? Liner : key === 'startup' ? Startup : key === 'dorm' ? Dorm : key === 'room' ? Room : Other
  return (
    <div
      className={cn('relative overflow-hidden', className)}
      style={{ background: SKY[key], ...style }}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      data-preset={key}
    >
      <div className="absolute inset-0 [&>svg]:w-full [&>svg]:h-full">
        <Scene />
      </div>
      <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 50% 40%, transparent 55%, rgba(0,0,0,.45) 100%)' }} />
    </div>
  )
}

export default SceneThumb
