// Cenário de fundo desenhado em SVG: represa e usina hidrelétrica à esquerda, térmica à direita, linha de transmissão ligando as duas.
export default function Cenario() {
  const torres = [660, 880, 1100, 1300]
  return (
    <div className="cenario" aria-hidden="true">
      <svg viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="ceu" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#07263a" /><stop offset=".45" stopColor="#1d6283" /><stop offset=".72" stopColor="#7fb6c4" /><stop offset="1" stopColor="#f3b673" />
          </linearGradient>
          <radialGradient id="sol" cx=".5" cy=".5" r=".5"><stop offset="0" stopColor="#fff2cf" stopOpacity=".95" /><stop offset=".4" stopColor="#ffc989" stopOpacity=".35" /><stop offset="1" stopColor="#ffc989" stopOpacity="0" /></radialGradient>
          <linearGradient id="lago" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1b6f8d" /><stop offset="1" stopColor="#05293a" /></linearGradient>
          <linearGradient id="concreto" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#d7e1e4" /><stop offset="1" stopColor="#8aa0a8" /></linearGradient>
          <linearGradient id="chamine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#c9d3d6" /><stop offset="1" stopColor="#7a8c93" /></linearGradient>
        </defs>
        <rect width="1920" height="1080" fill="url(#ceu)" />
        <circle cx="1480" cy="640" r="360" fill="url(#sol)" />
        <path d="M0 700 L180 560 L330 650 L520 500 L720 650 L900 560 L1120 690 L1330 540 L1560 680 L1760 560 L1920 650 V1080 H0Z" fill="#2c6f86" opacity=".7" />
        <path d="M0 780 L220 650 L400 740 L640 620 L860 760 L1080 680 L1300 780 L1520 690 L1760 770 L1920 700 V1080 H0Z" fill="#14465b" />
        {/* reservatório */}
        <rect y="800" width="1920" height="280" fill="url(#lago)" />
        {[830, 870, 915, 965, 1020].map((y, i) => (
          <line key={y} className="onda" x1={80 + i * 70} x2={520 + i * 90} y1={y} y2={y} stroke="#bfe9ff" strokeWidth="2" opacity=".35" style={{ animationDelay: `${i * .7}s` }} />
        ))}
        {/* barragem */}
        <polygon points="330,610 1010,610 1085,900 255,900" fill="url(#concreto)" />
        <polygon points="330,610 1010,610 1000,640 340,640" fill="#eef4f5" />
        {[0, 1, 2, 3, 4].map(i => (
          <g key={i}>
            <rect x={400 + i * 116} y="650" width="72" height="150" rx="6" fill="#4d6670" />
            <line className="queda" x1={436 + i * 116} x2={436 + i * 116 - i * 6} y1="800" y2="900" stroke="#e9fbff" strokeWidth="14" strokeLinecap="round" opacity=".85" />
          </g>
        ))}
        <rect x="255" y="896" width="830" height="12" fill="#6c828a" />
        {/* casa de força e tubulações */}
        <polygon points="1085,720 1190,780 1190,900 1085,900" fill="#3d5560" />
        <rect x="1180" y="810" width="190" height="92" rx="4" fill="#d5dfe2" />
        <rect x="1170" y="796" width="210" height="18" rx="4" fill="#2f4752" />
        {[0, 1, 2].map(i => <rect key={i} x={1198 + i * 54} y="836" width="34" height="46" rx="3" fill="#59c6ff" opacity=".85" />)}
        {/* linha de transmissão */}
        {torres.map(x => {
          const y = 560 + (x % 3) * 8
          return (
            <g key={x} stroke="#0b2230" strokeWidth="5" fill="none" opacity=".92">
              <path d={`M${x} 800 L${x + 18} ${y} L${x + 36} 800 M${x + 3} ${y + 70} L${x + 33} ${y + 70}`} />
              <path d={`M${x - 20} ${y + 8} H${x + 56}`} />
            </g>
          )
        })}
        <path d="M640 568 Q770 640 880 570 T1100 572 T1300 568 T1500 640" stroke="#0b2230" strokeWidth="2.5" fill="none" opacity=".9" />
        {/* térmica */}
        <rect x="1480" y="700" width="330" height="200" fill="#1d3a48" />
        <rect x="1480" y="700" width="330" height="22" fill="#2b4d5c" />
        {[0, 1, 2, 3].map(i => <rect key={i} x={1510 + i * 74} y="760" width="46" height="90" fill="#ffb347" opacity=".55" />)}
        <rect x="1540" y="400" width="52" height="300" fill="url(#chamine)" />
        <rect x="1540" y="400" width="52" height="30" fill="#e0433a" /><rect x="1540" y="460" width="52" height="30" fill="#e0433a" />
        <rect x="1650" y="460" width="44" height="240" fill="url(#chamine)" />
        <rect x="1650" y="460" width="44" height="26" fill="#e0433a" />
        <g fill="#eaf3f5" opacity=".6">
          <circle className="vapor" cx="1566" cy="380" r="34" /><circle className="vapor" cx="1580" cy="360" r="40" /><circle className="vapor" cx="1556" cy="370" r="30" />
          <circle className="vapor" cx="1672" cy="440" r="28" />
        </g>
        <rect y="900" width="1920" height="180" fill="#031521" opacity=".35" />
      </svg>
    </div>
  )
}
