const coverKeys = new Set(['creative-act', 'interstellar', 'kind-of-blue', 'attention', 'severance', 'midnight-library', 'cosmos', 'dune', 'in-rainbows', 'slow-horses']);

export function Artwork({ content, size = '' }) {
  const key = coverKeys.has(content.cover_key) ? content.cover_key : 'fallback';
  return <div className={`cover cover--${key} ${size ? `cover--${size}` : ''}`} role="img" aria-label={`Original cover illustration for ${content.title}`}>
    <span className="cover-ornament" aria-hidden="true"><i /><i /><i /></span>
    <span className="cover-type" aria-hidden="true">{key === 'attention' ? 'RESEARCH NOTES' : 'THE REESATCK EDITION'}</span>
    <strong aria-hidden="true">{content.title}</strong>
    <span className="cover-creator" aria-hidden="true">{content.creator}</span>
  </div>;
}

export function Logo() {
  return <svg viewBox="0 0 40 42" fill="none" aria-hidden="true" className="brand-mark">
    <path d="m5 29 25-3 5 9-26 3z" fill="#adc48d" stroke="currentColor" strokeWidth="1.5" />
    <path d="m7 16 27 2-1 10-27-2z" fill="#f6f5f1" stroke="currentColor" strokeWidth="1.5" />
    <path d="m4 7 26-3 3 11-26 3z" fill="#dcebb7" stroke="currentColor" strokeWidth="1.5" />
    <path d="m11 10 17-2M12 21l16 1M13 33l17-2" stroke="currentColor" strokeWidth="1.5" />
  </svg>;
}

export function HeroArtwork() {
  return <svg className="hero-art" viewBox="0 0 320 220" fill="none" aria-hidden="true">
    <ellipse cx="175" cy="108" rx="94" ry="93" fill="#e9eddf" />
    <ellipse cx="175" cy="110" rx="139" ry="47" transform="rotate(-24 175 110)" stroke="#91a18b" strokeWidth="1" strokeDasharray="3 5" />
    <path d="m89 153 105 10 64-38-108-11z" fill="#c1ccab" />
    <path d="m91 144 99 13 65-39-103-11z" fill="#385341" />
    <path d="m93 131 97 15 62-39v12l-61 39-98-14z" fill="#eee9dc" stroke="#385341" strokeWidth="1.4" />
    <path d="m91 130 100 15 63-39-103-13z" fill="#385341" />
    <path d="m107 113 75 21 65-40-79-21z" fill="#c07e5c" />
    <path d="m108 103 74 21 63-40v11l-63 40-74-21z" fill="#faf5e7" stroke="#9b654a" strokeWidth="1.4" />
    <path d="m105 101 77 22 65-40-80-23z" fill="#c88e6b" />
    <path d="m108 80 68 25 68-42-71-27z" fill="#b6c99a" stroke="#738864" strokeWidth="1.4" />
    <path d="m108 80 68 25v13l-68-25z" fill="#f9f8ed" stroke="#738864" strokeWidth="1.4" />
    <path d="m176 105 68-42v13l-68 42z" fill="#e8ebd6" stroke="#738864" strokeWidth="1.4" />
    <path d="m145 69 35 13 29-18-36-13z" stroke="#738864" strokeWidth="1.4" />
    <path d="m135 72 42 16M180 88l35-21" stroke="#738864" strokeWidth="1.4" />
    <path d="m229 38 3-13 4 12 12 3-13 4-3 12-4-13-11-3z" fill="#8a9d76" />
    <circle cx="57" cy="123" r="7" fill="#b7795e" />
    <circle cx="276" cy="118" r="4" fill="#8f9e77" />
    <path d="m72 59 8 8m-8 0 8-8M230 180h15m-7-7v14" stroke="#7d9070" strokeWidth="1.5" />
    <path d="M119 176c17 10 37 12 57 9" stroke="#b6c0a4" strokeWidth="1.5" />
  </svg>;
}
