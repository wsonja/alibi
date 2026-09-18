/**
 * RoomBackdrop — the fixed, full-screen study behind every screen (DESIGN §1).
 * Layered CSS gradients (.room-bg in theme.css) plus a little inline-SVG garnish on the desk:
 * a stack of books (INTERROGATE / OBSERVE / CONNECT / SOLVE), the mug, and the CONFIDENTIAL folder.
 */
export function RoomBackdrop() {
  return (
    <div className="room-bg" aria-hidden="true">
      <svg
        viewBox="0 0 320 120"
        className="absolute hidden md:block"
        style={{ right: '3vw', bottom: '2vh', width: 'min(34vw, 420px)', height: 'auto', opacity: 0.92, filter: 'drop-shadow(0 6px 10px rgba(0,0,0,.6))' }}
        focusable="false"
      >
        {/* book stack */}
        <g transform="translate(10 18)">
          <rect x="0" y="66" width="120" height="16" rx="2" fill="#6b1f1f" stroke="#2a1610" strokeWidth="1.5" />
          <text x="60" y="78" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="9" fill="#e0bc63" letterSpacing="1.5">
            INTERROGATE
          </text>
          <rect x="6" y="48" width="112" height="18" rx="2" fill="#1f3a2a" stroke="#2a1610" strokeWidth="1.5" />
          <text x="62" y="61" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="9" fill="#e0bc63" letterSpacing="1.5">
            OBSERVE
          </text>
          <rect x="2" y="32" width="118" height="16" rx="2" fill="#2a2f5a" stroke="#2a1610" strokeWidth="1.5" />
          <text x="61" y="44" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="9" fill="#e0bc63" letterSpacing="1.5">
            CONNECT
          </text>
          <rect x="10" y="14" width="104" height="18" rx="2" fill="#5a331c" stroke="#2a1610" strokeWidth="1.5" />
          <text x="62" y="27" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="9" fill="#f0d48a" letterSpacing="1.5">
            SOLVE
          </text>
        </g>
        {/* mug */}
        <g transform="translate(150 52)">
          <rect x="0" y="6" width="34" height="42" rx="4" fill="#15100c" stroke="#3a2a14" strokeWidth="1.5" />
          <path d="M34 16 q14 0 14 12 q0 12 -14 12" fill="none" stroke="#15100c" strokeWidth="6" />
          <ellipse cx="17" cy="6" rx="17" ry="4" fill="#2a1e17" stroke="#3a2a14" strokeWidth="1.5" />
          <text x="17" y="24" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="5" fill="#e0bc63" letterSpacing="0.6">
            GOOD SUSPECTS
          </text>
          <text x="17" y="32" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="5" fill="#e0bc63" letterSpacing="0.6">
            MAKE GREAT
          </text>
          <text x="17" y="40" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="5" fill="#e0bc63" letterSpacing="0.6">
            STORIES
          </text>
        </g>
        {/* folder */}
        <g transform="translate(206 60) rotate(-6)">
          <path d="M0 8 h40 l6 6 h60 v48 h-106 z" fill="#c9a76a" stroke="#7a4b22" strokeWidth="1.5" />
          <rect x="0" y="14" width="106" height="48" fill="#d9b97f" stroke="#7a4b22" strokeWidth="1.5" />
          <g transform="translate(53 38) rotate(-8)">
            <rect x="-40" y="-9" width="80" height="18" fill="none" stroke="#9c1c1c" strokeWidth="2" />
            <text x="0" y="4" textAnchor="middle" fontFamily="Cinzel, serif" fontSize="9" fill="#9c1c1c" letterSpacing="2" fontWeight="700">
              CONFIDENTIAL
            </text>
          </g>
        </g>
        {/* fountain pen */}
        <g transform="translate(236 20) rotate(28)">
          <rect x="0" y="0" width="70" height="6" rx="3" fill="#15100c" stroke="#c9a24b" strokeWidth="1" />
          <path d="M70 0 l10 3 l-10 3 z" fill="#c9a24b" />
          <rect x="18" y="1" width="3" height="4" fill="#c9a24b" />
        </g>
      </svg>
    </div>
  )
}

export default RoomBackdrop
