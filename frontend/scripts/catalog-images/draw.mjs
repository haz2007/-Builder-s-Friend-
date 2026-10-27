// Рисунки товаров каталога в одном стиле: светлый фон, мягкая тень,
// предмет по центру, подпись с размером в углу. Каждая функция возвращает
// фрагмент SVG 1200×900; frame() собирает из него готовую картинку.

const W = 1200;
const H = 900;

// Псевдослучайные числа с зерном: одна и та же доска рисуется одинаково
function rng(seed) {
  let s = 0;
  for (const ch of String(seed)) s = (s * 31 + ch.charCodeAt(0)) >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const f = (n) => Math.round(n * 10) / 10;

function lin(id, stops, x1 = 0, y1 = 0, x2 = 0, y2 = 1) {
  const st = stops
    .map(([o, c, a = 1]) => `<stop offset="${o}" stop-color="${c}" stop-opacity="${a}"/>`)
    .join("");
  return `<linearGradient id="${id}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}">${st}</linearGradient>`;
}

function rad(id, stops, cx = 0.5, cy = 0.5, r = 0.5) {
  const st = stops
    .map(([o, c, a = 1]) => `<stop offset="${o}" stop-color="${c}" stop-opacity="${a}"/>`)
    .join("");
  return `<radialGradient id="${id}" cx="${cx}" cy="${cy}" r="${r}">${st}</radialGradient>`;
}

// Металлы и пластики, общие для всех рисунков
const METAL = [[0, "#f4f6f8"], [0.35, "#c9cfd6"], [0.6, "#9aa2ab"], [1, "#5f666e"]];
const ZINC_YELLOW = [[0, "#fbeaa0"], [0.35, "#e4c05a"], [0.65, "#b88d2c"], [1, "#6f531a"]];
const BLACK_STEEL = [[0, "#8a8d91"], [0.3, "#4a4c50"], [0.65, "#25272a"], [1, "#0f1012"]];

function shadow(cx, cy, rx, ry, opacity = 0.26) {
  return `<ellipse cx="${f(cx)}" cy="${f(cy)}" rx="${f(rx)}" ry="${f(ry)}" fill="#2b1d10" opacity="${opacity}" filter="url(#blur)"/>`;
}

function badge(text) {
  if (!text) return "";
  const width = 40 + text.length * 25;
  return `<g transform="translate(${W - 48 - width},${H - 118})">
    <rect width="${width}" height="70" rx="35" fill="#ffffff" opacity="0.92"/>
    <rect width="${width}" height="70" rx="35" fill="none" stroke="#d9cfc4" stroke-width="2"/>
    <text x="${width / 2}" y="47" text-anchor="middle" font-family="Manrope, Arial, sans-serif"
      font-weight="700" font-size="38" fill="#4a3a2c">${text}</text>
  </g>`;
}

export function frame(body, caption, fontCss = "") {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <style>${fontCss}</style>
    ${rad("bg", [[0, "#fdfcfa"], [0.7, "#f3efe9"], [1, "#e9e3da"]], 0.5, 0.42, 0.78)}
    <filter id="blur" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="16"/></filter>
    <filter id="blur4" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="4"/></filter>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  ${body}
  ${badge(caption)}
</svg>`;
}

/* ---------- Пиломатериалы ---------- */

const PINE = {
  end: "#ecc68f", endDark: "#d9a96b", ring: "#b97a3f", top: "#f3d8aa", side: "#dfb176",
  grain: "#c08548", knot: "#8d5527", edge: "#b0743a",
};
const ASPEN = {
  end: "#ebe2cc", endDark: "#d6c8a8", ring: "#b5a27c", top: "#f1eadb", side: "#dcd0b5",
  grain: "#b9a785", knot: "#8f7c5a", edge: "#a8957a",
};

/** Доска, брус или брусок: торец к зрителю, длина уходит вправо-вверх. */
export function lumber({ t, w, len = 6000, aspen = false, seed = "" }) {
  const P = aspen ? ASPEN : PINE;
  const r = rng(`${t}x${w}x${len}${seed}`);
  const maxd = Math.max(t, w);
  const s = (120 + 0.95 * maxd) / maxd;
  const EW = w * s;
  const EH = t * s;
  const k = len >= 6000 ? 1 : 0.7;
  const dx = 640 * k;
  const dy = 330 * k;
  const bw = EW + dx;
  const bh = EH + dy;
  const x0 = W / 2 - bw / 2;
  const y0 = 430 - bh / 2 + dy;
  const ang = (Math.atan2(-dy, dx) * 180) / Math.PI;

  const top = `M${f(x0)},${f(y0)} L${f(x0 + EW)},${f(y0)} L${f(x0 + EW + dx)},${f(y0 - dy)} L${f(x0 + dx)},${f(y0 - dy)} Z`;
  const side = `M${f(x0 + EW)},${f(y0)} L${f(x0 + EW)},${f(y0 + EH)} L${f(x0 + EW + dx)},${f(y0 + EH - dy)} L${f(x0 + EW + dx)},${f(y0 - dy)} Z`;
  const bottom = `M${f(x0)},${f(y0 + EH)} L${f(x0 + EW)},${f(y0 + EH)} L${f(x0 + EW + dx)},${f(y0 + EH - dy)} L${f(x0 + dx)},${f(y0 + EH - dy)} Z`;

  // Волокна по верхней и боковой граням
  const grain = (fromX, fromY, alongX, alongY, n, face) => {
    let out = "";
    for (let i = 1; i <= n; i += 1) {
      const u = (i + (r() - 0.5) * 0.6) / (n + 1);
      const sx = fromX(u);
      const sy = fromY(u);
      const wob = (r() - 0.5) * 14;
      const mx = sx + dx * 0.5 + wob * 0.5;
      const my = sy - dy * 0.5 + wob;
      out += `<path d="M${f(sx)},${f(sy)} Q${f(mx)},${f(my)} ${f(sx + dx)},${f(sy - dy)}" stroke="${P.grain}" stroke-width="${f(1.4 + r() * 1.6)}" fill="none" opacity="${f(0.25 + r() * 0.25)}"/>`;
    }
    return `<g clip-path="url(#${face})">${out}</g>`;
  };

  const topGrain = grain((u) => x0 + u * EW, () => y0, null, null, Math.max(3, Math.round(EW / 22)), "clipTop");
  const sideGrain = grain(() => x0 + EW, (u) => y0 + u * EH, null, null, Math.max(2, Math.round(EH / 18)), "clipSide");

  // Сучки на боковой грани и сверху
  let knots = "";
  const knotCount = 1 + Math.floor(r() * 2);
  for (let i = 0; i < knotCount; i += 1) {
    const u = 0.25 + r() * 0.6;
    if (EH > 34) {
      const v = 0.3 + r() * 0.4;
      const cx = x0 + EW + u * dx;
      const cy = y0 + v * EH - u * dy;
      const rr = Math.min(EH * 0.18, 13);
      knots += `<ellipse cx="${f(cx)}" cy="${f(cy)}" rx="${f(rr * 1.6)}" ry="${f(rr)}" transform="rotate(${f(ang)} ${f(cx)} ${f(cy)})" fill="${P.knot}" opacity="0.38"/>`;
    }
    const v2 = 0.25 + r() * 0.5;
    const cx2 = x0 + v2 * EW + (u * 0.8 + 0.1) * dx;
    const cy2 = y0 - (u * 0.8 + 0.1) * dy;
    const rr2 = Math.min(EW * 0.08, 11);
    knots += `<ellipse cx="${f(cx2)}" cy="${f(cy2)}" rx="${f(rr2 * 1.5)}" ry="${f(rr2 * 0.6)}" transform="rotate(${f(ang * 0.4)} ${f(cx2)} ${f(cy2)})" fill="${P.knot}" opacity="0.28"/>`;
  }

  // Годовые кольца на торце: у бруса сердцевина внутри, у доски — ниже торца
  const square = Math.min(t, w) / Math.max(t, w) > 0.6;
  const pcx = x0 + EW * (0.45 + r() * 0.12);
  const pcy = square ? y0 + EH * (0.5 + r() * 0.1) : y0 + EH + Math.max(EW, EH) * (0.35 + r() * 0.3);
  let rings = "";
  const step = Math.max(6, Math.max(EW, EH) / 14);
  for (let rr = step * 0.6; rr < Math.max(EW, EH) * 2.2; rr += step * (0.8 + r() * 0.4)) {
    rings += `<circle cx="${f(pcx)}" cy="${f(pcy)}" r="${f(rr)}" fill="none" stroke="${P.ring}" stroke-width="${f(1.5 + r() * 1.8)}" opacity="0.42"/>`;
  }
  const pith = square ? `<circle cx="${f(pcx)}" cy="${f(pcy)}" r="4" fill="${P.knot}" opacity="0.6"/>` : "";

  return `
  <defs>
    ${lin("gTop", [[0, P.top], [1, P.side]], 0, 0, 1, 1)}
    ${lin("gSide", [[0, P.side], [1, P.endDark]], 0, 0, 0, 1)}
    ${rad("gEnd", [[0, P.end], [1, P.endDark]], 0.5, 0.5, 0.75)}
    <clipPath id="clipTop"><path d="${top}"/></clipPath>
    <clipPath id="clipSide"><path d="${side}"/></clipPath>
    <clipPath id="clipEnd"><rect x="${f(x0)}" y="${f(y0)}" width="${f(EW)}" height="${f(EH)}"/></clipPath>
  </defs>
  <path d="${bottom}" transform="translate(6,18)" fill="#2b1d10" opacity="0.32" filter="url(#blur)"/>
  <path d="${top}" fill="url(#gTop)"/>
  ${topGrain}
  <path d="${side}" fill="url(#gSide)"/>
  ${sideGrain}
  ${knots}
  <rect x="${f(x0)}" y="${f(y0)}" width="${f(EW)}" height="${f(EH)}" fill="url(#gEnd)"/>
  <g clip-path="url(#clipEnd)">${rings}${pith}</g>
  <path d="${top}" fill="none" stroke="${P.edge}" stroke-width="1.5" opacity="0.45"/>
  <path d="${side}" fill="none" stroke="${P.edge}" stroke-width="1.5" opacity="0.45"/>
  <rect x="${f(x0)}" y="${f(y0)}" width="${f(EW)}" height="${f(EH)}" fill="none" stroke="${P.edge}" stroke-width="2" opacity="0.55"/>
  <line x1="${f(x0)}" y1="${f(y0)}" x2="${f(x0 + EW)}" y2="${f(y0)}" stroke="#fff" stroke-width="2" opacity="0.6"/>`;
}

// Лист в изометрии: T — дальний угол, u — длинная сторона вправо-вниз, v — короткая влево-вниз
function sheet(ratio, thickness) {
  const a = 380;
  const b = 200;
  const k1 = ratio > 1 ? 1.25 : 1;
  const k2 = ratio > 1 ? 1.25 / ratio : 1;
  const u = [a * k1, b * k1];
  const v = [-a * k2, b * k2];
  const T = [600 + (a * (k2 - k1)) / 2, 400 - (b * (k1 + k2)) / 2];
  const add = (p, q, k = 1) => [f(p[0] + q[0] * k), f(p[1] + q[1] * k)];
  const R = add(T, u);
  const L = add(T, v);
  const B = add(R, v);
  const th = 12 + thickness * 1.6;
  const down = (p, y) => [p[0], f(p[1] + y)];
  return {
    T, R, B, L, u, v, th, add,
    top: `M${T} L${R} L${B} L${L} Z`,
    leftEdge: `M${L} L${B} L${down(B, th)} L${down(L, th)} Z`,
    rightEdge: `M${B} L${R} L${down(R, th)} L${down(B, th)} Z`,
    under: `M${down(L, th)} L${down(B, th)} L${down(R, th)} L${down(T, th)} Z`,
    // Полоса кромки на высоте y..y+h (для слоёв фанеры)
    band: (y, h) => `M${down(L, y)} L${down(B, y)} L${down(R, y)} L${down(R, y + h)} L${down(B, y + h)} L${down(L, y + h)} Z`,
  };
}

/** Лист фанеры: ФК — светлая берёза, ФСФ — с тёмными клеевыми слоями. */
export function plywood({ thickness = 18, ratio = 1, kind = "fk" }) {
  const S = sheet(ratio, thickness);
  const layers = Math.max(5, Math.round(thickness / 1.6) | 1);
  const glue = kind === "fsf" ? "#7a4a22" : "#c99a5e";
  let stripes = "";
  for (let i = 0; i < layers; i += 1) {
    const h = S.th / layers;
    stripes += `<path d="${S.band(h * i, h)}" fill="${i % 2 ? glue : "#e8c995"}"/>`;
  }
  const r = rng(`ply${thickness}${ratio}`);
  let grain = "";
  for (let i = 0; i < 18; i += 1) {
    const [sx, sy] = S.add(S.T, S.v, i / 18 + r() * 0.03);
    grain += `<path d="M${sx},${sy} q${f(S.u[0] * 0.5)},${f(S.u[1] * 0.5 + (r() - 0.5) * 20)} ${f(S.u[0])},${f(S.u[1])}" stroke="#c7a06a" stroke-width="${f(1 + r() * 1.5)}" fill="none" opacity="0.35"/>`;
  }
  let patches = "";
  for (let i = 0; i < 3; i += 1) {
    const [px, py] = S.add(S.add(S.T, S.u, 0.2 + r() * 0.6), S.v, 0.2 + r() * 0.6);
    patches += `<ellipse cx="${px}" cy="${py}" rx="${f(26 + r() * 14)}" ry="${f(9 + r() * 5)}" transform="rotate(28 ${px} ${py})" fill="#c8995c" opacity="0.22"/>`;
  }
  return `
  <defs>
    ${lin("pTop", [[0, "#f6e3bf"], [1, "#e6c690"]], 0, 0, 1, 1)}
    <clipPath id="cTop"><path d="${S.top}"/></clipPath>
  </defs>
  <path d="${S.under}" transform="translate(0,22)" fill="#2b1d10" opacity="0.3" filter="url(#blur)"/>
  ${stripes}
  <path d="${S.leftEdge}" fill="#000" opacity="0.06"/>
  <path d="${S.rightEdge}" fill="#000" opacity="0.14"/>
  <path d="${S.top}" fill="url(#pTop)"/>
  <g clip-path="url(#cTop)">${grain}${patches}</g>
  <path d="${S.top}" fill="none" stroke="#b98b52" stroke-width="2" opacity="0.5"/>`;
}

/** Плита ОСБ: прессованная щепа и синяя маркировка. */
export function osb({ thickness = 9 }) {
  const S = sheet(2, thickness);
  const r = rng(`osb${thickness}`);
  const colors = ["#c99a52", "#e2bd7c", "#b8864a", "#d8ad66", "#a87a40", "#ecd09a"];
  let strands = "";
  for (let i = 0; i < 520; i += 1) {
    const [x, y] = S.add(S.add(S.T, S.u, r() * 1.05 - 0.025), S.v, r() * 1.05 - 0.025);
    const len = 34 + r() * 46;
    const wid = 7 + r() * 9;
    strands += `<rect x="${f(x - len / 2)}" y="${f(y - wid / 2)}" width="${f(len)}" height="${f(wid)}" rx="2" transform="rotate(${f(r() * 180)} ${x} ${y})" fill="${colors[Math.floor(r() * colors.length)]}" opacity="${f(0.65 + r() * 0.3)}"/>`;
  }
  let edge = "";
  for (let i = 0; i < 70; i += 1) {
    const k = r();
    const [x, y] = k < 0.55 ? S.add(S.L, S.u, k / 0.55) : S.add(S.B, S.v, -(k - 0.55) / 0.45);
    edge += `<rect x="${f(x - 6)}" y="${f(y + 3 + r() * (S.th - 8))}" width="${f(8 + r() * 10)}" height="2.5" fill="#7d5528" opacity="0.6"/>`;
  }
  const len = (q) => Math.hypot(q[0], q[1]);
  const [sx, sy] = S.add(S.add(S.T, S.u, 0.58), S.v, 0.42);
  const mat = `matrix(${f(S.u[0] / len(S.u))} ${f(S.u[1] / len(S.u))} ${f(S.v[0] / len(S.v))} ${f(S.v[1] / len(S.v))} ${sx} ${sy})`;
  return `
  <defs>
    ${lin("oTop", [[0, "#e7c88d"], [1, "#cfa45e"]], 0, 0, 1, 1)}
    <clipPath id="cTop"><path d="${S.top}"/></clipPath>
    <clipPath id="cEdge"><path d="${S.leftEdge}"/><path d="${S.rightEdge}"/></clipPath>
  </defs>
  <path d="${S.under}" transform="translate(0,22)" fill="#2b1d10" opacity="0.3" filter="url(#blur)"/>
  <path d="${S.leftEdge}" fill="#c4945a"/>
  <path d="${S.rightEdge}" fill="#a97b44"/>
  <g clip-path="url(#cEdge)">${edge}</g>
  <path d="${S.top}" fill="url(#oTop)"/>
  <g clip-path="url(#cTop)">${strands}</g>
  <g transform="${mat}" opacity="0.75">
    <text x="0" y="0" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="46" fill="#1f4f9a">OSB-3</text>
    <text x="0" y="40" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="700" font-size="24" fill="#1f4f9a">${thickness} mm · E1</text>
  </g>
  <path d="${S.top}" fill="none" stroke="#9c7038" stroke-width="2" opacity="0.5"/>`;
}

/* ---------- Рулоны, плиты ---------- */

/** Рулон плёнки или мембраны с цветной бандеролью. */
export function roll({ band = "#2f6db5", film = "#eef1f3", title = "", big = "", sub = "", fluffy = false, dark = false }) {
  const x1 = 330;
  const x2 = 900;
  const cy = 440;
  const R = 165;
  const ex = 58;
  const filmStops = dark
    ? [[0, "#8d9297"], [0.35, "#62676c"], [1, "#2e3134"]]
    : [[0, "#ffffff"], [0.3, film], [0.75, "#c9ced3"], [1, "#9ea4aa"]];
  const body = `M${x1},${cy - R} L${x2},${cy - R} A${ex},${R} 0 0 1 ${x2},${cy + R} L${x1},${cy + R} Z`;
  let spiral = "";
  for (let i = 0; i < 7; i += 1) {
    const k = 1 - i * 0.1;
    spiral += `<ellipse cx="${x1}" cy="${cy}" rx="${f(ex * k)}" ry="${f(R * k)}" fill="none" stroke="${dark ? "#43474b" : "#c4c9ce"}" stroke-width="2"/>`;
  }
  const fuzzRng = rng("fuzz");
  const fuzz = fluffy
    ? `<g clip-path="url(#cBody)" opacity="0.35">${Array.from({ length: 140 }, () => {
        const r = fuzzRng;
        return `<circle cx="${f(x1 + r() * (x2 - x1))}" cy="${f(cy - R + r() * 2 * R)}" r="${f(1 + r() * 2.2)}" fill="#b9bec4"/>`;
      }).join("")}</g>`
    : "";
  const bx = 460;
  const bw = 330;
  const label = band
    ? `<g clip-path="url(#cBody)">
        <rect x="${bx}" y="${cy - R}" width="${bw}" height="${2 * R}" fill="${band}"/>
        <rect x="${bx}" y="${cy - R}" width="${bw}" height="${2 * R}" fill="url(#shade)"/>
      </g>
      <text x="${bx + bw / 2}" y="${cy - 62}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="34" fill="#fff" letter-spacing="2">${title}</text>
      <text x="${bx + bw / 2}" y="${cy + 46}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="${big.length > 3 ? 66 : 100}" fill="#fff">${big}</text>
      <text x="${bx + bw / 2}" y="${cy + 112}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="700" font-size="36" fill="#fff" opacity="0.95">${sub}</text>`
    : "";
  return `
  <defs>
    ${lin("film", filmStops)}
    ${lin("shade", [[0, "#fff", 0.28], [0.35, "#fff", 0], [0.7, "#000", 0.12], [1, "#000", 0.35]])}
    ${rad("endG", [[0, dark ? "#55595d" : "#e3e6e9"], [1, dark ? "#2c2f32" : "#b9bfc5"]])}
    <clipPath id="cBody"><path d="${body}"/></clipPath>
  </defs>
  ${shadow(615, cy + R + 8, 330, 26)}
  <path d="${body}" fill="url(#film)"/>
  ${fuzz}
  ${label}
  <ellipse cx="${x1}" cy="${cy}" rx="${ex}" ry="${R}" fill="url(#endG)"/>
  ${spiral}
  <ellipse cx="${x1}" cy="${cy}" rx="18" ry="48" fill="#a88a62"/>
  <ellipse cx="${x1 + 2}" cy="${cy}" rx="10" ry="34" fill="#4a3a28"/>`;
}

/** Плита пенопласта: белая плита с гранулами. */
export function foamBoard({ thickness = 100 }) {
  const cx = 600;
  const cy = 390;
  const a = 360;
  const b = 190;
  const th = thickness * 0.95;
  const T = [cx - 60, cy - b];
  const R = [cx + a, cy - 40];
  const B = [cx + 60, cy + b - 40];
  const L = [cx - a, cy];
  const top = `M${T} L${R} L${B} L${L} Z`;
  const left = `M${L} L${B} L${B[0]},${B[1] + th} L${L[0]},${L[1] + th} Z`;
  const right = `M${B} L${R} L${R[0]},${R[1] + th} L${B[0]},${B[1] + th} Z`;
  const r = rng(`foam${thickness}`);
  const beads = (n, x0, y0, x1, y1) =>
    Array.from({ length: n }, () => {
      const x = x0 + r() * (x1 - x0);
      const y = y0 + r() * (y1 - y0);
      return `<circle cx="${f(x)}" cy="${f(y)}" r="${f(3 + r() * 4)}" fill="none" stroke="#d6dadd" stroke-width="1.4"/>`;
    }).join("");
  return `
  <defs>
    <clipPath id="cL"><path d="${left}"/></clipPath>
    <clipPath id="cR"><path d="${right}"/></clipPath>
    <clipPath id="cT"><path d="${top}"/></clipPath>
  </defs>
  <path d="M${L[0]},${L[1] + th} L${B[0]},${B[1] + th} L${R[0]},${R[1] + th} Z" transform="translate(0,18)" fill="#2b1d10" opacity="0.28" filter="url(#blur)"/>
  <path d="${top}" fill="#fbfbfa"/>
  <g clip-path="url(#cT)" opacity="0.6">${beads(260, L[0], T[1], R[0], B[1])}</g>
  <path d="${left}" fill="#eceeef"/>
  <g clip-path="url(#cL)">${beads(90, L[0], L[1], B[0], B[1] + th)}</g>
  <path d="${right}" fill="#dde0e3"/>
  <g clip-path="url(#cR)">${beads(110, B[0], R[1], R[0], B[1] + th)}</g>
  <path d="${top}" fill="none" stroke="#cfd3d6" stroke-width="2"/>
  <path d="${left}" fill="none" stroke="#cfd3d6" stroke-width="2"/>
  <path d="${right}" fill="none" stroke="#c4c8cc" stroke-width="2"/>`;
}

/* ---------- Ёмкости ---------- */

/** Пластиковая канистра: объём сбоку, ручка-петля сверху, горловина с крышкой, этикетка. */
export function canister({ litres = 10, label = "#3f8a4a", title = "", cap = "#c23b2a", sub = "огнебиозащита" }) {
  const sc = { 5: 1.0, 10: 1.12, 20: 1.24 }[litres] ?? 1.1;
  const w = 290 * sc;
  const h = 380 * sc;
  const dx = w * 0.3;
  const dy = w * 0.16;
  const x = 600 - (w + dx) / 2;
  const yb = 740;
  const y = yb - h;
  const r = 22 * sc;
  // Петля ручки над верхней гранью (слева), горловина — справа сзади
  const hx1 = x + w * 0.08;
  const hx2 = x + w * 0.62;
  const hTop = y - h * 0.2;
  const neckX = x + w * 0.74 + dx * 0.5;
  const neckY = y - dy * 0.5;
  const nw = w * 0.2;
  const titleSize = Math.min(40 * sc, ((w * 0.84 - 30) / Math.max(title.length, 3)) * 1.32);
  return `
  <defs>
    ${lin("canF", [[0, "#ffffff"], [0.55, "#f2f3f1"], [1, "#d9dcd9"]], 0, 0, 1, 0)}
    ${lin("canS", [[0, "#d3d7d4"], [1, "#b3b8b5"]], 0, 0, 1, 0)}
    ${lin("canT", [[0, "#ffffff"], [1, "#e4e7e5"]], 0, 0, 0, 1)}
    ${lin("lab", [[0, label], [1, label]])}
    ${lin("capG", [[0, cap], [0.5, cap], [1, "#000"]], 0, 0, 1, 0)}
  </defs>
  ${shadow(600 + dx * 0.3, yb + 4, (w + dx) * 0.62, 24)}
  <path d="M${f(x + w)},${f(y + r)} L${f(x + w + dx)},${f(y + r - dy)} L${f(x + w + dx)},${f(yb - r - dy)} Q${f(x + w + dx)},${f(yb - dy)} ${f(x + w + dx - r * 0.6)},${f(yb - dy + r * 0.3)} L${f(x + w)},${f(yb)} Z" fill="url(#canS)" stroke="#a9aeab" stroke-width="2" stroke-linejoin="round"/>
  <path d="M${f(x + r)},${f(y)} L${f(x + w - r)},${f(y)} L${f(x + w + dx - r)},${f(y - dy)} L${f(x + dx + r)},${f(y - dy)} Z" fill="url(#canT)" stroke="#b9beba" stroke-width="2" stroke-linejoin="round"/>
  <path d="M${f(hx1)},${f(y - dy * 0.15)} C${f(hx1 - 6)},${f(hTop)} ${f(hx2 + 6)},${f(hTop)} ${f(hx2)},${f(y - dy * 0.6)}
           L${f(hx2 - w * 0.1)},${f(y - dy * 0.55)} C${f(hx2 - w * 0.1)},${f(hTop + h * 0.08)} ${f(hx1 + w * 0.1)},${f(hTop + h * 0.08)} ${f(hx1 + w * 0.1)},${f(y - dy * 0.2)} Z"
        fill="url(#canF)" stroke="#9ca29e" stroke-width="3" stroke-linejoin="round"/>
  <rect x="${f(neckX - nw / 2)}" y="${f(neckY - h * 0.06)}" width="${f(nw)}" height="${f(h * 0.07)}" fill="url(#canS)"/>
  <rect x="${f(neckX - nw * 0.62)}" y="${f(neckY - h * 0.14)}" width="${f(nw * 1.24)}" height="${f(h * 0.09)}" rx="6" fill="url(#capG)"/>
  ${Array.from({ length: 6 }, (_, i) => `<line x1="${f(neckX - nw * 0.5 + i * nw * 0.2)}" y1="${f(neckY - h * 0.13)}" x2="${f(neckX - nw * 0.5 + i * nw * 0.2)}" y2="${f(neckY - h * 0.06)}" stroke="#000" stroke-width="2" opacity="0.18"/>`).join("")}
  <rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" rx="${f(r)}" fill="url(#canF)" stroke="#b9beba" stroke-width="2"/>
  <rect x="${f(x + 6)}" y="${f(y + 10)}" width="${f(w * 0.06)}" height="${f(h - 20)}" rx="${f(r * 0.4)}" fill="#fff" opacity="0.6"/>
  <rect x="${f(x + w * 0.08)}" y="${f(y + h * 0.24)}" width="${f(w * 0.84)}" height="${f(h * 0.62)}" rx="8" fill="#ffffff" stroke="#d6d9d6" stroke-width="2"/>
  <rect x="${f(x + w * 0.08)}" y="${f(y + h * 0.24)}" width="${f(w * 0.84)}" height="${f(h * 0.2)}" rx="8" fill="url(#lab)"/>
  <rect x="${f(x + w * 0.08)}" y="${f(y + h * 0.36)}" width="${f(w * 0.84)}" height="${f(h * 0.08)}" fill="url(#lab)"/>
  <text x="${f(x + w / 2)}" y="${f(y + h * 0.37)}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="${f(titleSize)}" fill="#fff">${title}</text>
  <text x="${f(x + w / 2)}" y="${f(y + h * 0.53)}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="700" font-size="${f(19 * sc)}" fill="#6b625a">${sub}</text>
  <text x="${f(x + w / 2)}" y="${f(y + h * 0.74)}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="${f(66 * sc)}" fill="${label}">${litres} л</text>
  <rect x="${f(x + w * 0.08)}" y="${f(y + h * 0.8)}" width="${f(w * 0.84)}" height="${f(h * 0.06)}" fill="url(#lab)" opacity="0.85"/>`;
}

/** Садовый опрыскиватель «Жук»: бак, насос, шланг и удочка. */
export function sprayer({ litres = 8 }) {
  const backpack = litres >= 12;
  const sc = { 5: 0.82, 8: 0.92, 12: 1 }[litres] ?? 0.9;
  const w = (backpack ? 300 : 250) * sc;
  const h = (backpack ? 430 : 360) * sc;
  const x = 520 - w / 2;
  const yb = 720;
  const y = yb - h;
  const body = backpack
    ? `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" rx="46" fill="url(#tank)" stroke="#c9c6b4" stroke-width="2"/>
       <rect x="${f(x + w - 26)}" y="${f(y + 60)}" width="22" height="${f(h - 120)}" rx="11" fill="#2d6b33"/>`
    : `<rect x="${f(x)}" y="${f(y + 30)}" width="${f(w)}" height="${f(h - 30)}" rx="${f(w * 0.3)}" fill="url(#tank)" stroke="#c9c6b4" stroke-width="2"/>`;
  const capY = backpack ? y - 6 : y + 20;
  return `
  <defs>
    ${lin("tank", [[0, "#ffffff"], [0.5, "#f1eedf"], [1, "#cfcab2"]], 0, 0, 1, 0)}
    ${lin("liq", [[0, "#9ccf7a", 0.5], [1, "#6fa64c", 0.55]])}
  </defs>
  ${shadow(600, yb + 4, w * 0.95, 24)}
  ${body}
  <rect x="${f(x + 14)}" y="${f(y + h * 0.55)}" width="${f(w - 28)}" height="${f(h * 0.42)}" rx="30" fill="url(#liq)"/>
  <g stroke="#9c9884" stroke-width="2" opacity="0.6">
    ${[0.25, 0.4, 0.55, 0.7, 0.85].map((v) => `<line x1="${f(x + 18)}" y1="${f(y + h * v)}" x2="${f(x + 46)}" y2="${f(y + h * v)}"/>`).join("")}
  </g>
  <rect x="${f(x + w / 2 - 46)}" y="${f(capY - 18)}" width="92" height="36" rx="10" fill="#2f7a37"/>
  <rect x="${f(x + w / 2 - 8)}" y="${f(capY - 120)}" width="16" height="104" fill="#3a3d40"/>
  <rect x="${f(x + w / 2 - 70)}" y="${f(capY - 136)}" width="140" height="26" rx="13" fill="#2f7a37"/>
  <path d="M${f(x + w - 10)},${f(yb - 60)} C${f(x + w + 120)},${f(yb - 30)} ${f(x + w + 140)},${f(y + 120)} ${f(x + w + 90)},${f(y + 40)}" stroke="#2b2d30" stroke-width="12" fill="none" stroke-linecap="round"/>
  <rect x="${f(x + w + 60)}" y="${f(y - 10)}" width="30" height="60" rx="8" fill="#2f7a37" transform="rotate(-30 ${f(x + w + 75)} ${f(y + 20)})"/>
  <line x1="${f(x + w + 92)}" y1="${f(y - 4)}" x2="${f(x + w + 300)}" y2="${f(y - 210)}" stroke="#8b929a" stroke-width="10" stroke-linecap="round"/>
  <rect x="${f(x + w + 290)}" y="${f(y - 236)}" width="34" height="22" rx="6" fill="#2f7a37" transform="rotate(-45 ${f(x + w + 307)} ${f(y - 225)})"/>
  <text x="${f(x + w / 2)}" y="${f(y + h * 0.42)}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="${f(58 * sc)}" fill="#2f7a37">${litres} л</text>`;
}

/** Баллон монтажной пены. */
export function foamCan() {
  return `
  <defs>
    ${lin("canB", [[0, "#6f7880"], [0.25, "#e9eef2"], [0.55, "#b6bec5"], [1, "#4c535a"]], 0, 0, 1, 0)}
    ${lin("canL", [[0, "#9a3a12"], [0.3, "#f07a2e"], [0.6, "#d9611c"], [1, "#7a2c0c"]], 0, 0, 1, 0)}
  </defs>
  ${shadow(610, 726, 140, 20)}
  <rect x="515" y="270" width="170" height="450" rx="14" fill="url(#canB)"/>
  <rect x="515" y="330" width="170" height="330" fill="url(#canL)"/>
  <path d="M515,280 Q600,200 685,280 Z" fill="url(#canB)"/>
  <rect x="580" y="208" width="40" height="40" rx="6" fill="#33373b"/>
  <path d="M600,214 L720,170 L870,120" stroke="#e7e2d8" stroke-width="10" fill="none" stroke-linecap="round"/>
  <path d="M600,214 L720,170 L870,120" stroke="#c9c2b4" stroke-width="2" fill="none"/>
  <rect x="540" y="430" width="120" height="70" rx="8" fill="#fff" opacity="0.9"/>
  <text x="600" y="478" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="34" fill="#c9561a">PU</text>`;
}

/** Картридж герметика. */
export function sealant() {
  return `
  <defs>
    ${lin("cart", [[0, "#cfd4d8"], [0.3, "#ffffff"], [0.7, "#e2e6e9"], [1, "#9aa1a7"]], 0, 0, 1, 0)}
    ${lin("lab2", [[0, "#1f5fa8"], [0.35, "#3b82d6"], [1, "#163f70"]], 0, 0, 1, 0)}
  </defs>
  <g transform="rotate(-24 600 470)">
    ${shadow(600, 740, 120, 18)}
    <rect x="530" y="330" width="140" height="390" rx="10" fill="url(#cart)"/>
    <rect x="530" y="400" width="140" height="240" fill="url(#lab2)"/>
    <path d="M552,330 L582,250 L618,250 L648,330 Z" fill="url(#cart)"/>
    <path d="M585,250 L594,110 L606,110 L615,250 Z" fill="#e6e9ec" stroke="#b8bec4" stroke-width="2"/>
    <text x="600" y="530" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="30" fill="#fff" transform="rotate(-90 600 520)">СИЛИКОН</text>
  </g>`;
}

/* ---------- Крепёж ---------- */

function screwShape(len, { color = "yellow", fine = false, head = "csk", tip = "sharp" } = {}) {
  const r = 12;
  const id = `sc_${color}`;
  let thread = "";
  const pitch = fine ? 11 : 17;
  const start = head === "hex" ? len * 0.42 : 30;
  for (let x = start; x < len - 30; x += pitch) {
    thread += `<path d="M${f(x)},${-r - 6} L${f(x + pitch * 0.55)},${r + 6}" stroke="url(#${id})" stroke-width="5" stroke-linecap="round"/>`;
  }
  const headSvg =
    head === "hex"
      ? `<rect x="-34" y="-30" width="30" height="60" rx="3" fill="url(#${id})"/><line x1="-34" y1="-10" x2="-4" y2="-10" stroke="#00000033" stroke-width="2"/><line x1="-34" y1="10" x2="-4" y2="10" stroke="#00000033" stroke-width="2"/><rect x="-6" y="-36" width="8" height="72" rx="3" fill="url(#${id})"/>`
      : `<path d="M-14,-30 L4,-${r} L4,${r} L-14,30 Q-20,0 -14,-30 Z" fill="url(#${id})"/>`;
  const tipSvg =
    tip === "drill"
      ? `<path d="M${len - 34},-${r} L${len - 4},-5 L${len},0 L${len - 4},5 L${len - 34},${r} Z" fill="url(#${id})"/>`
      : `<path d="M${len - 34},-${r} L${len},0 L${len - 34},${r} Z" fill="url(#${id})"/>`;
  return `<g>
    <rect x="0" y="-${r}" width="${len - 34}" height="${2 * r}" fill="url(#${id})"/>
    ${thread}
    ${tipSvg}
    ${headSvg}
  </g>`;
}

function fastenerDefs() {
  return `<defs>
    ${lin("sc_yellow", ZINC_YELLOW)}
    ${lin("sc_black", BLACK_STEEL)}
    ${lin("sc_metal", METAL)}
  </defs>`;
}

/** Три самореза или шурупа, лежащих наискосок. */
export function screws({ len = 51, color = "yellow", fine = false, head = "csk", tip = "sharp" }) {
  const px = Math.min(700, 250 + len * 3.4);
  const items = [-90, 0, 90]
    .map(
      (dy, i) => `<g transform="translate(${600 - px / 2 + i * 26},${430 + dy}) rotate(-14 ${px / 2} 0)">
        <g transform="translate(14,34)" opacity="0.3" filter="url(#blur4)"><rect x="-10" y="-14" width="${px}" height="28" rx="14" fill="#2b1d10"/></g>
        ${screwShape(px, { color, fine, head, tip })}
      </g>`,
    )
    .join("");
  return fastenerDefs() + items;
}

/** Анкерный болт с гайкой: гильза с прорезями, шайба, гайка. */
export function anchorBolt({ len = 100 }) {
  const px = Math.min(720, 300 + len * 2.4);
  const one = `
    <g transform="translate(14,36)" opacity="0.3" filter="url(#blur4)"><rect x="-40" y="-20" width="${px + 40}" height="40" rx="20" fill="#2b1d10"/></g>
    <rect x="-70" y="-10" width="${px * 0.35}" height="20" fill="url(#sc_metal)"/>
    ${Array.from({ length: 8 }, (_, i) => `<line x1="${-66 + i * 9}" y1="-11" x2="${-62 + i * 9}" y2="11" stroke="#6d747c" stroke-width="2"/>`).join("")}
    <rect x="-40" y="-34" width="34" height="68" rx="4" fill="url(#sc_metal)"/>
    <rect x="-6" y="-42" width="10" height="84" rx="3" fill="url(#sc_metal)"/>
    <rect x="4" y="-18" width="${px - 70}" height="36" rx="4" fill="url(#sc_metal)"/>
    ${[0.3, 0.55].map((u) => `<rect x="${f(4 + (px - 70) * u)}" y="-18" width="${f((px - 70) * 0.18)}" height="3" fill="#5f666e"/>`).join("")}
    <path d="M${px - 66},-18 L${px},-12 L${px},12 L${px - 66},18 Z" fill="url(#sc_metal)"/>`;
  return `${fastenerDefs()}
  <g transform="translate(${600 - px / 2 + 40},360) rotate(-12)">${one}</g>
  <g transform="translate(${600 - px / 2 + 70},520) rotate(-12)">${one}</g>`;
}

/** Гайки: шестигранники в лёгкой перспективе. */
export function nuts({ m = 10 }) {
  const R = 60 + m * 4;
  const hex = (cx, cy, rr) => {
    const pts = Array.from({ length: 6 }, (_, i) => {
      const a = (Math.PI / 3) * i + Math.PI / 6;
      return [cx + rr * Math.cos(a), cy + rr * Math.sin(a) * 0.62];
    });
    return pts;
  };
  const one = (cx, cy) => {
    const th = R * 0.55;
    const top = hex(cx, cy, R);
    const sides = [0, 1, 2]
      .map((i) => {
        const a = top[i];
        const b = top[i + 1];
        return `<path d="M${f(a[0])},${f(a[1])} L${f(b[0])},${f(b[1])} L${f(b[0])},${f(b[1] + th)} L${f(a[0])},${f(a[1] + th)} Z" fill="url(#sc_metal)" stroke="#7d848c" stroke-width="1.5"/>`;
      })
      .join("");
    return `${shadow(cx + 10, cy + th + 30, R * 1.05, R * 0.35, 0.22)}
      ${sides}
      <path d="M${top.map((p) => `${f(p[0])},${f(p[1])}`).join(" L")} Z" fill="url(#nutTop)" stroke="#7d848c" stroke-width="1.5"/>
      <ellipse cx="${cx}" cy="${cy}" rx="${f(R * 0.52)}" ry="${f(R * 0.32)}" fill="#6b727a"/>
      <ellipse cx="${cx}" cy="${cy + 6}" rx="${f(R * 0.44)}" ry="${f(R * 0.26)}" fill="#3e4348"/>`;
  };
  return `${fastenerDefs()}<defs>${lin("nutTop", [[0, "#f7f9fa"], [1, "#a9b0b7"]], 0, 0, 1, 1)}</defs>
    ${one(470, 340)}${one(740, 380)}${one(590, 560)}`;
}

/** Шайбы: плоские кольца стопкой. */
export function washers({ m = 10 }) {
  const R = 80 + m * 4;
  const one = (cx, cy) => `
    ${shadow(cx + 8, cy + 30, R * 1.02, R * 0.32, 0.2)}
    <ellipse cx="${cx}" cy="${cy + 8}" rx="${R}" ry="${f(R * 0.42)}" fill="#7d848c"/>
    <ellipse cx="${cx}" cy="${cy}" rx="${R}" ry="${f(R * 0.42)}" fill="url(#wTop)"/>
    <ellipse cx="${cx}" cy="${cy}" rx="${f(R * 0.45)}" ry="${f(R * 0.19)}" fill="#e9e3da"/>
    <path d="M${f(cx - R * 0.45)},${cy} A${f(R * 0.45)},${f(R * 0.19)} 0 0 1 ${f(cx + R * 0.45)},${cy}" stroke="#6b727a" stroke-width="7" fill="none"/>`;
  return `<defs>${lin("wTop", [[0, "#ffffff"], [0.5, "#c3c9cf"], [1, "#8a9199"]], 0, 0, 1, 1)}</defs>
    ${one(470, 380)}${one(740, 330)}${one(620, 560)}`;
}

/** Шпилька резьбовая 1 м. */
export function threadedRod({ m = 10 }) {
  const r = 8 + m * 0.9;
  const len = 960;
  let thread = "";
  for (let x = 6; x < len - 6; x += 10) {
    thread += `<line x1="${x}" y1="${f(-r)}" x2="${x + 6}" y2="${f(r)}" stroke="#6d747c" stroke-width="2.2"/>`;
  }
  return `${fastenerDefs()}
  <g transform="translate(130,560) rotate(-20)">
    <g transform="translate(14,40)" opacity="0.3" filter="url(#blur4)"><rect width="${len}" height="${2 * r}" y="${-r}" rx="${r}" fill="#2b1d10"/></g>
    <rect width="${len}" height="${f(2 * r)}" y="${f(-r)}" rx="3" fill="url(#sc_metal)"/>
    ${thread}
  </g>`;
}

/** Гвозди: три гвоздя с плоской шляпкой. */
export function nails({ len = 120 }) {
  const px = Math.min(720, 280 + len * 3.4);
  const one = `
    <g transform="translate(14,30)" opacity="0.3" filter="url(#blur4)"><rect x="-10" y="-8" width="${px}" height="16" rx="8" fill="#2b1d10"/></g>
    <rect x="0" y="-7" width="${px - 40}" height="14" fill="url(#sc_metal)"/>
    <path d="M${px - 40},-7 L${px},0 L${px - 40},7 Z" fill="url(#sc_metal)"/>
    <rect x="-10" y="-26" width="12" height="52" rx="4" fill="url(#sc_metal)"/>
    ${[0, 1, 2, 3].map((i) => `<line x1="${8 + i * 7}" y1="-7" x2="${11 + i * 7}" y2="7" stroke="#7d848c" stroke-width="1.5"/>`).join("")}`;
  return `${fastenerDefs()}${[-80, 0, 80]
    .map((dy, i) => `<g transform="translate(${600 - px / 2 + i * 22},${440 + dy}) rotate(-12)">${one}</g>`)
    .join("")}`;
}

/** Скобы для степлера: блок скоб и коробочка. */
export function staples() {
  let lines = "";
  for (let i = 0; i < 46; i += 1) lines += `<line x1="${330 + i * 8}" y1="420" x2="${330 + i * 8}" y2="500" stroke="#8f979f" stroke-width="2"/>`;
  return `${fastenerDefs()}
  <defs>${lin("box", [[0, "#2d6db3"], [1, "#1a467a"]], 0, 0, 1, 1)}</defs>
  ${shadow(600, 640, 340, 26)}
  <path d="M640,560 L900,500 L900,330 L640,390 Z" fill="#1a467a"/>
  <path d="M640,390 L900,330 L820,290 L560,350 Z" fill="#3c84d0"/>
  <path d="M560,350 L640,390 L640,560 L560,520 Z" fill="url(#box)"/>
  <text x="770" y="460" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="40" fill="#fff" transform="skewY(-13) translate(0,170)">1000</text>
  <rect x="320" y="410" width="384" height="22" rx="4" fill="url(#sc_metal)"/>
  <rect x="320" y="410" width="16" height="96" fill="url(#sc_metal)"/>
  <rect x="688" y="410" width="16" height="96" fill="url(#sc_metal)"/>
  <g opacity="0.8">${lines}</g>`;
}

/* ---------- Ленты ---------- */

/** Рулон ленты: изолента, малярная, скотч, перфолента. */
export function tape({ kind = "insulation" }) {
  const cfg = {
    insulation: { outer: 150, inner: 62, depth: 40, c1: "#3d7fd6", c2: "#1d4f96", core: "#1d4f96" },
    masking: { outer: 170, inner: 90, depth: 90, c1: "#f1e3b4", c2: "#cdb879", core: "#b99a62" },
    packing: { outer: 170, inner: 90, depth: 90, c1: "#e8b86a", c2: "#b9873a", core: "#b99a62" },
    perforated: { outer: 175, inner: 70, depth: 26, c1: "#eef1f4", c2: "#9aa2ab", core: "#c9cfd6" },
  }[kind];
  const cx = 560;
  const cy = 430;
  const { outer: R, inner: r, depth: d } = cfg;
  const holes =
    kind === "perforated"
      ? Array.from({ length: 5 }, (_, i) => {
          const rr = r + 18 + i * 22;
          return Array.from({ length: 14 }, (_, j) => {
            const a = (Math.PI * 2 * j) / 14 + i * 0.2;
            return `<circle cx="${f(cx + rr * Math.cos(a) * 0.82)}" cy="${f(cy + rr * Math.sin(a))}" r="4" fill="#7f8790" opacity="0.7"/>`;
          }).join("");
        }).join("")
      : "";
  const rings =
    kind === "perforated"
      ? Array.from({ length: 6 }, (_, i) => `<ellipse cx="${cx}" cy="${cy}" rx="${f((r + 10 + i * 20) * 0.82)}" ry="${r + 10 + i * 20}" fill="none" stroke="#8f979f" stroke-width="1.5"/>`).join("")
      : "";
  return `
  <defs>
    ${lin("tSide", [[0, cfg.c1], [1, cfg.c2]], 0, 0, 0, 1)}
    ${rad("tFace", [[0, cfg.c1], [1, cfg.c2]], 0.4, 0.35, 0.8)}
  </defs>
  ${shadow(cx + d / 2 + 10, cy + R + 6, R * 1.05, 24)}
  <path d="M${cx},${cy - R} L${cx + d},${cy - R} A${f(R * 0.82)},${R} 0 0 1 ${cx + d},${cy + R} L${cx},${cy + R} Z" fill="url(#tSide)"/>
  <ellipse cx="${cx}" cy="${cy}" rx="${f(R * 0.82)}" ry="${R}" fill="url(#tFace)"/>
  ${rings}${holes}
  <ellipse cx="${cx}" cy="${cy}" rx="${f(r * 0.82)}" ry="${r}" fill="${cfg.core}"/>
  <ellipse cx="${cx + 6}" cy="${cy}" rx="${f(r * 0.82 - 8)}" ry="${r - 8}" fill="#efe9e1"/>
  ${kind === "packing" ? `<ellipse cx="${cx}" cy="${cy}" rx="${f(R * 0.82)}" ry="${R}" fill="#fff" opacity="0.18"/>` : ""}`;
}

/* ---------- Инструмент ---------- */

const WOOD = [[0, "#e0a76a"], [0.5, "#c58446"], [1, "#8f5627"]];

/** Малярный валик. */
export function roller() {
  return `<defs>
    ${lin("fur", [[0, "#ffffff"], [0.4, "#eef0f3"], [1, "#b8bfc7"]])}
    ${lin("plast", [[0, "#ffb34d"], [1, "#d26b0c"]])}
    ${lin("sc_metal", METAL)}
  </defs>
  ${shadow(600, 700, 360, 24)}
  <rect x="300" y="250" width="420" height="140" rx="30" fill="url(#fur)"/>
  ${Array.from({ length: 30 }, (_, i) => `<line x1="${314 + i * 13.5}" y1="258" x2="${318 + i * 13.5}" y2="382" stroke="#d3d8de" stroke-width="2"/>`).join("")}
  <path d="M720,320 L760,320 L760,470 L600,520 L600,560" stroke="url(#sc_metal)" stroke-width="12" fill="none" stroke-linejoin="round"/>
  <rect x="572" y="540" width="56" height="190" rx="24" fill="url(#plast)"/>`;
}

/** Ручка-удлинитель для валика. */
export function rollerPole() {
  return `<defs>
    ${lin("pole", [[0, "#f0f2f4"], [0.5, "#aeb5bd"], [1, "#6d747c"]])}
    ${lin("plast", [[0, "#ffb34d"], [1, "#d26b0c"]])}
  </defs>
  <g transform="translate(160,620) rotate(-24)">
    <g transform="translate(12,40)" opacity="0.28" filter="url(#blur4)"><rect width="980" height="34" rx="17" fill="#2b1d10"/></g>
    <rect x="0" y="-16" width="300" height="34" rx="16" fill="url(#plast)"/>
    <rect x="300" y="-12" width="560" height="26" fill="url(#pole)"/>
    <rect x="560" y="-15" width="20" height="32" rx="4" fill="#33373b"/>
    <rect x="860" y="-16" width="90" height="34" rx="6" fill="#33373b"/>
    <rect x="950" y="-9" width="40" height="20" fill="url(#pole)"/>
  </g>`;
}

/** Плоская кисть. */
export function brush() {
  return `<defs>
    ${lin("wood", WOOD)}
    ${lin("ferr", METAL)}
    ${lin("bristle", [[0, "#f4e2c0"], [1, "#c9a978"]])}
  </defs>
  <g transform="translate(600,450) rotate(-32)">
    <g transform="translate(14,40)" opacity="0.28" filter="url(#blur4)"><rect x="-420" y="-60" width="840" height="120" rx="40" fill="#2b1d10"/></g>
    <path d="M-60,-46 Q-260,-30 -400,-18 Q-420,0 -400,18 Q-260,30 -60,46 Z" fill="url(#wood)"/>
    <circle cx="-360" cy="0" r="12" fill="#efe9e1"/>
    <rect x="-70" y="-62" width="140" height="124" rx="10" fill="url(#ferr)"/>
    <path d="M70,-58 L380,-62 L392,62 L70,58 Z" fill="url(#bristle)"/>
    ${Array.from({ length: 12 }, (_, i) => `<line x1="80" y1="${-50 + i * 9}" x2="385" y2="${-54 + i * 9.8}" stroke="#b8975f" stroke-width="1.5" opacity="0.6"/>`).join("")}
  </g>`;
}

/** Пластиковое ведро с ручкой. */
export function bucket() {
  return `<defs>
    ${lin("bk", [[0, "#ffffff"], [0.5, "#f1f2f3"], [1, "#c3c8cd"]], 0, 0, 1, 0)}
  </defs>
  ${shadow(600, 742, 230, 26)}
  <path d="M380,300 L820,300 L770,730 Q600,750 430,730 Z" fill="url(#bk)" stroke="#c4c9ce" stroke-width="2"/>
  <ellipse cx="600" cy="300" rx="220" ry="54" fill="#dfe3e6" stroke="#c4c9ce" stroke-width="3"/>
  <ellipse cx="600" cy="306" rx="200" ry="44" fill="#c9ced3"/>
  <path d="M392,330 Q600,90 808,330" stroke="#8a9199" stroke-width="7" fill="none"/>
  <rect x="540" y="168" width="120" height="26" rx="13" fill="#3a3d40"/>
  ${[400, 480].map((y) => `<path d="M${400 + (y - 300) * 0.12},${y} Q600,${y + 30} ${800 - (y - 300) * 0.12},${y}" stroke="#d3d7db" stroke-width="3" fill="none"/>`).join("")}`;
}

/** Шпатель. */
export function spatula() {
  return `<defs>
    ${lin("blade", [[0, "#f7f9fa"], [0.5, "#c3c9cf"], [1, "#8d949c"]], 0, 0, 1, 1)}
    ${lin("plast", [[0, "#4a4e53"], [1, "#1f2124"]])}
  </defs>
  <g transform="translate(600,450) rotate(-28)">
    <g transform="translate(14,36)" opacity="0.28" filter="url(#blur4)"><path d="M-380,-30 L0,-30 L360,-150 L360,150 L0,30 L-380,30 Z" fill="#2b1d10"/></g>
    <rect x="-380" y="-34" width="320" height="68" rx="30" fill="url(#plast)"/>
    <rect x="-80" y="-24" width="60" height="48" rx="6" fill="#8d949c"/>
    <path d="M-20,-22 L360,-150 L360,150 L-20,22 Z" fill="url(#blade)" stroke="#8d949c" stroke-width="2"/>
  </g>`;
}

/** Строительный карандаш. */
export function pencil() {
  return `<defs>
    ${lin("pen", [[0, "#ff6b5c"], [0.5, "#d8352a"], [1, "#9b1f17"]])}
    ${lin("wood", [[0, "#f3d3a2"], [1, "#d9ab6a"]])}
  </defs>
  <g transform="translate(600,450) rotate(-24)">
    <g transform="translate(14,34)" opacity="0.28" filter="url(#blur4)"><rect x="-400" y="-30" width="800" height="60" rx="10" fill="#2b1d10"/></g>
    <rect x="-400" y="-32" width="660" height="64" rx="6" fill="url(#pen)"/>
    <line x1="-400" y1="0" x2="260" y2="0" stroke="#8d1b14" stroke-width="2" opacity="0.4"/>
    <path d="M260,-32 L400,-8 L400,8 L260,32 Z" fill="url(#wood)"/>
    <path d="M372,-12 L410,-4 L410,4 L372,12 Z" fill="#2e2e2e"/>
    <text x="-150" y="12" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="30" fill="#ffd8d3" opacity="0.8">2H</text>
  </g>`;
}

/** Рулетка. */
export function tapeMeasure() {
  let ticks = "";
  for (let i = 0; i < 26; i += 1) ticks += `<line x1="${700 + i * 16}" y1="560" x2="${700 + i * 16}" y2="${i % 5 ? 574 : 584}" stroke="#2b2b2b" stroke-width="2"/>`;
  return `<defs>
    ${lin("tm", [[0, "#ffd84a"], [1, "#e0a400"]], 0, 0, 1, 1)}
    ${lin("rub", [[0, "#4a4e53"], [1, "#1f2124"]], 0, 0, 1, 1)}
  </defs>
  ${shadow(640, 680, 380, 26)}
  <rect x="300" y="300" width="380" height="360" rx="80" fill="url(#rub)"/>
  <rect x="330" y="330" width="320" height="300" rx="64" fill="url(#tm)"/>
  <circle cx="490" cy="480" r="70" fill="#1f2124" opacity="0.85"/>
  <circle cx="490" cy="480" r="30" fill="#e0a400"/>
  <rect x="640" y="408" width="70" height="40" rx="10" fill="#1f2124"/>
  <path d="M660,548 L1120,548 L1120,592 L660,592 Z" fill="#ffe36b" stroke="#c99a00" stroke-width="2"/>
  ${ticks}
  <rect x="1112" y="532" width="16" height="76" rx="3" fill="#8d949c"/>`;
}

/** Молоток. */
export function hammer() {
  return `<defs>
    ${lin("wood", WOOD)}
    ${lin("steel", METAL, 0, 0, 1, 0)}
  </defs>
  <g transform="translate(600,470) rotate(-30)">
    <g transform="translate(16,40)" opacity="0.28" filter="url(#blur4)"><rect x="-380" y="-24" width="720" height="48" rx="20" fill="#2b1d10"/><rect x="190" y="-190" width="110" height="330" rx="16" fill="#2b1d10"/></g>
    <rect x="-380" y="-24" width="640" height="48" rx="22" fill="url(#wood)"/>
    <rect x="-380" y="-28" width="200" height="56" rx="26" fill="#2c2f33"/>
    <path d="M210,-70 Q214,-150 168,-196 L192,-204 Q262,-150 282,-70 Z" fill="url(#steel)"/>
    <rect x="200" y="-74" width="86" height="176" rx="10" fill="url(#steel)"/>
    <rect x="188" y="92" width="110" height="44" rx="12" fill="url(#steel)"/>
    <rect x="188" y="128" width="110" height="8" rx="4" fill="#5f666e" opacity="0.5"/>
  </g>`;
}

/** Топор: топорище наискосок, лезвие с бородкой. */
export function axe() {
  return `<defs>
    ${lin("wood", WOOD)}
    ${lin("steel", [[0, "#f4f6f8"], [0.55, "#aab2ba"], [1, "#545b62"]], 0, 1, 0, 0)}
  </defs>
  <g transform="translate(560,500) rotate(-32)">
    <g transform="translate(16,40)" opacity="0.28" filter="url(#blur4)">
      <rect x="-400" y="-24" width="780" height="48" rx="22" fill="#2b1d10"/>
      <path d="M230,44 L380,44 L430,-120 Q450,-230 410,-290 Q290,-310 160,-250 Q210,-150 230,-44 Z" fill="#2b1d10"/>
    </g>
    <path d="M-400,-18 Q-60,-30 372,-24 L372,24 Q-60,30 -400,18 Q-424,0 -400,-18 Z" fill="url(#wood)"/>
    <path d="M-330,-16 Q0,-26 360,-20" stroke="#f0c08a" stroke-width="3" fill="none" opacity="0.5"/>
    <path d="M236,44 L378,44 L378,-40 L428,-120 Q448,-228 410,-290 Q290,-312 160,-252 Q214,-150 236,-44 Z" fill="url(#steel)" stroke="#6d747c" stroke-width="2"/>
    <path d="M410,-290 Q290,-312 160,-252" stroke="#ffffff" stroke-width="7" fill="none" opacity="0.85"/>
    <path d="M236,-40 L378,-40" stroke="#6d747c" stroke-width="2" opacity="0.6"/>
    <rect x="352" y="-30" width="22" height="60" rx="4" fill="#b88454"/>
  </g>`;
}

/** Ножовка по дереву. */
export function saw() {
  let teeth = "";
  for (let x = -250; x < 420; x += 18) teeth += `L${x + 9},${100 + (x + 250) * 0.06 + 14} L${x + 18},${100 + (x + 268) * 0.06}`;
  return `<defs>
    ${lin("blade", [[0, "#f7f9fa"], [0.6, "#c3c9cf"], [1, "#8d949c"]], 0, 0, 0, 1)}
    ${lin("hand", [[0, "#ffb34d"], [1, "#d26b0c"]])}
  </defs>
  <g transform="translate(560,430) rotate(-14)">
    <g transform="translate(14,36)" opacity="0.25" filter="url(#blur4)"><path d="M-250,-20 L420,40 L420,140 L-250,100 Z" fill="#2b1d10"/></g>
    <path d="M-250,-20 L420,40 L420,${100 + 670 * 0.06} ${teeth} L-250,100 Z" fill="url(#blade)" stroke="#8d949c" stroke-width="2"/>
    <path d="M-250,-40 L-420,-60 Q-470,40 -420,150 L-250,130 Z" fill="url(#hand)"/>
    <path d="M-300,-10 L-400,-20 Q-420,40 -400,100 L-300,100 Z" fill="#efe9e1"/>
  </g>`;
}

/** Рабочая перчатка с ПВХ-точками. */
export function glove() {
  // Ладонь, пальцы и большой палец — капсулы; общий контур рисуем обводкой снизу
  const parts = `
    <rect x="452" y="330" width="266" height="300" rx="70"/>
    <rect x="458" y="190" width="62" height="220" rx="31"/>
    <rect x="526" y="150" width="64" height="260" rx="32"/>
    <rect x="596" y="170" width="62" height="240" rx="31"/>
    <rect x="662" y="232" width="54" height="190" rx="27"/>
    <rect x="424" y="400" width="66" height="220" rx="33" transform="rotate(-32 457 590)"/>`;
  return `<defs>
    <clipPath id="gl">${parts}</clipPath>
    <pattern id="dots" width="30" height="30" patternUnits="userSpaceOnUse">
      <circle cx="8" cy="8" r="6" fill="#2d5aa8"/><circle cx="23" cy="23" r="6" fill="#2d5aa8"/>
    </pattern>
    ${lin("knit", [[0, "#3a6fc4"], [1, "#22498c"]])}
    ${lin("shade", [[0, "#fff", 0], [1, "#000", 1]], 0, 0, 1, 0)}
  </defs>
  ${shadow(600, 730, 220, 24)}
  <g fill="#cfc9bf" stroke="#cfc9bf" stroke-width="8">${parts}</g>
  <g fill="#f8f6f1">${parts}</g>
  <g clip-path="url(#gl)">
    <rect x="300" y="120" width="500" height="520" fill="url(#dots)" opacity="0.9"/>
    <rect x="300" y="120" width="500" height="520" fill="url(#shade)" opacity="0.15"/>
  </g>
  ${[[489, 410], [558, 410], [627, 410]].map(([x, y]) => `<line x1="${x}" y1="${y - 6}" x2="${x}" y2="${y + 4}" stroke="#d8d2c8" stroke-width="3"/>`).join("")}
  <rect x="444" y="610" width="282" height="104" rx="14" fill="url(#knit)"/>
  ${Array.from({ length: 13 }, (_, i) => `<line x1="${458 + i * 21}" y1="618" x2="${458 + i * 21}" y2="706" stroke="#fff" stroke-width="2" opacity="0.25"/>`).join("")}`;
}

/** Сверло по металлу: гладкий хвостовик и винтовые канавки. */
export function drillBit() {
  const r = 24;
  let flutes = "";
  for (let x = 250; x < 760; x += 54) {
    flutes += `<path d="M${x},${-r} C${x + 14},-8 ${x + 22},8 ${x + 34},${r} L${x + 52},${r} C${x + 40},8 ${x + 32},-8 ${x + 18},${-r} Z" fill="#454b52"/>`;
    flutes += `<path d="M${x + 18},${-r} C${x + 32},-8 ${x + 40},8 ${x + 52},${r}" stroke="#f4f6f8" stroke-width="3" fill="none" opacity="0.7"/>`;
  }
  return `${fastenerDefs()}
  <defs><clipPath id="flute"><rect x="250" y="${-r}" width="530" height="${2 * r}"/><path d="M780,${-r} L840,0 L780,${r} Z"/></clipPath></defs>
  <g transform="translate(150,600) rotate(-22)">
    <g transform="translate(16,38)" opacity="0.28" filter="url(#blur4)"><rect x="0" y="${-r}" width="840" height="${2 * r}" rx="${r}" fill="#2b1d10"/></g>
    <rect x="0" y="-20" width="262" height="40" rx="6" fill="url(#sc_metal)"/>
    <rect x="250" y="${-r}" width="530" height="${2 * r}" fill="url(#sc_metal)"/>
    <path d="M780,${-r} L840,0 L780,${r} Z" fill="url(#sc_metal)"/>
    <g clip-path="url(#flute)">${flutes}</g>
    <path d="M806,-12 L840,0 L806,12" stroke="#f4f6f8" stroke-width="3" fill="none"/>
  </g>`;
}

/** Отрезной диск по металлу. */
export function cutDisc({ d = 125 }) {
  const R = 160 + d * 0.45;
  const discRng = rng(`disc${d}`);
  return `<defs>
    ${rad("disc", [[0, "#5b5f63"], [0.75, "#3a3d40"], [1, "#2a2c2e"]])}
  </defs>
  ${shadow(610, 450 + R * 0.62 + 18, R * 1.02, 26)}
  <ellipse cx="600" cy="450" rx="${f(R)}" ry="${f(R * 0.62)}" fill="#1f2022"/>
  <ellipse cx="600" cy="440" rx="${f(R)}" ry="${f(R * 0.62)}" fill="url(#disc)"/>
  ${Array.from({ length: 40 }, () => {
    const r = discRng;
    const a = r() * Math.PI * 2;
    const rr = R * (0.45 + r() * 0.5);
    return `<circle cx="${f(600 + rr * Math.cos(a))}" cy="${f(440 + rr * Math.sin(a) * 0.62)}" r="2" fill="#7a7f84"/>`;
  }).join("")}
  <ellipse cx="600" cy="440" rx="${f(R * 0.45)}" ry="${f(R * 0.28)}" fill="#c9302a"/>
  <ellipse cx="600" cy="440" rx="${f(R * 0.2)}" ry="${f(R * 0.124)}" fill="#c9cfd6"/>
  <ellipse cx="600" cy="440" rx="${f(R * 0.11)}" ry="${f(R * 0.068)}" fill="#e9e3da"/>
  <text x="600" y="${f(440 - R * 0.17)}" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="26" fill="#fff" transform="scale(1,1)">METAL</text>`;
}

/** Щётка для УШМ: чашечная или дисковая, со стальной проволокой. */
export function wireBrush({ d = 100, disc = false }) {
  const R = 120 + d * 0.9;
  const wires = Array.from({ length: 160 }, (_, i) => {
    const a = (Math.PI * 2 * i) / 160;
    const r1 = R * 0.62;
    const r2 = R * (0.96 + (i % 3) * 0.02);
    return `<line x1="${f(600 + r1 * Math.cos(a))}" y1="${f(430 + r1 * Math.sin(a) * 0.6)}" x2="${f(600 + r2 * Math.cos(a))}" y2="${f(430 + r2 * Math.sin(a) * 0.6)}" stroke="#a7afb7" stroke-width="2"/>`;
  }).join("");
  const cupWall = disc
    ? ""
    : `<path d="M${f(600 - R * 0.62)},430 L${f(600 - R * 0.55)},${f(430 + R * 0.5)} A${f(R * 0.55)},${f(R * 0.33)} 0 0 0 ${f(600 + R * 0.55)},${f(430 + R * 0.5)} L${f(600 + R * 0.62)},430 Z" fill="url(#sc_metal)"/>`;
  return `${fastenerDefs()}
  ${shadow(610, 430 + R * 0.6 + (disc ? 30 : 90), R * 1.02, 26)}
  ${cupWall}
  <ellipse cx="600" cy="430" rx="${f(R)}" ry="${f(R * 0.6)}" fill="#d3d8dc"/>
  ${wires}
  <ellipse cx="600" cy="430" rx="${f(R * 0.62)}" ry="${f(R * 0.37)}" fill="url(#sc_metal)"/>
  <ellipse cx="600" cy="430" rx="${f(R * 0.3)}" ry="${f(R * 0.18)}" fill="#7d848c"/>
  <ellipse cx="600" cy="426" rx="${f(R * 0.16)}" ry="${f(R * 0.1)}" fill="#3e4348"/>`;
}

/** Пистолет для монтажной пены: ствол, переходник под баллон, рукоять и курок. */
export function foamGun() {
  return `${fastenerDefs()}
  <defs>${lin("gun", [[0, "#5a5f65"], [1, "#25282b"]], 0, 0, 1, 0)}${lin("blue", [[0, "#4b8ee0"], [1, "#1d4f96"]], 0, 0, 1, 0)}${lin("brass", [[0, "#ffe9a8"], [0.5, "#d9b04a"], [1, "#8a6a1c"]], 0, 0, 1, 0)}</defs>
  ${shadow(600, 700, 360, 22)}
  <rect x="420" y="322" width="470" height="20" rx="6" fill="url(#sc_metal)"/>
  <path d="M890,320 L960,326 L960,338 L890,344 Z" fill="url(#sc_metal)"/>
  <rect x="300" y="300" width="150" height="66" rx="14" fill="url(#gun)"/>
  <rect x="260" y="318" width="44" height="30" rx="6" fill="url(#sc_metal)"/>
  <rect x="236" y="310" width="28" height="46" rx="8" fill="#33373b"/>
  <rect x="318" y="246" width="96" height="58" rx="8" fill="url(#brass)"/>
  <rect x="312" y="226" width="108" height="26" rx="6" fill="url(#brass)"/>
  ${[262, 276, 290].map((y) => `<line x1="320" y1="${y}" x2="412" y2="${y}" stroke="#8a6a1c" stroke-width="2"/>`).join("")}
  <path d="M310,360 L410,360 L392,640 Q390,664 366,664 L318,664 Q294,664 296,640 Z" fill="url(#gun)"/>
  ${[420, 470, 520, 570, 620].map((y) => `<line x1="${306 - (y - 360) * 0.01}" y1="${y}" x2="${396 - (y - 360) * 0.06}" y2="${y}" stroke="#16181a" stroke-width="3" opacity="0.6"/>`).join("")}
  <path d="M430,362 Q470,372 474,420 L478,560 Q478,586 456,586 L446,586 Q426,586 430,560 L426,420 Q424,390 412,372 Z" fill="url(#blue)"/>`;
}

/** Строительный степлер: корпус с магазином и рычаг сверху. */
export function stapleGun() {
  return `<defs>${lin("sg", [[0, "#ffb34d"], [1, "#d26b0c"]])}${lin("sgm", METAL)}${lin("sgd", [[0, "#5a5f65"], [1, "#25282b"]])}</defs>
  ${shadow(600, 664, 330, 24)}
  <path d="M300,640 L880,640 L880,470 Q880,440 850,440 L760,440 L740,520 L420,520 Q340,520 320,560 L300,600 Z" fill="url(#sgm)" stroke="#7d848c" stroke-width="2"/>
  <rect x="320" y="612" width="560" height="10" fill="#6d747c" opacity="0.6"/>
  <rect x="860" y="600" width="26" height="44" rx="4" fill="#33373b"/>
  <path d="M760,440 L880,440 L880,500 L748,500 Z" fill="url(#sgd)"/>
  <path d="M836,420 Q600,300 330,330 Q300,334 302,362 L306,392 Q310,414 338,410 Q590,384 800,470 Z" fill="url(#sg)" stroke="#b55a06" stroke-width="2"/>
  ${[0, 1, 2, 3, 4, 5].map((i) => `<line x1="${380 + i * 34}" y1="${342 - i * 1.5}" x2="${384 + i * 34}" y2="${394 - i * 0.5}" stroke="#b55a06" stroke-width="3" opacity="0.5"/>`).join("")}
  <circle cx="820" cy="452" r="14" fill="#33373b"/><circle cx="820" cy="452" r="5" fill="#9aa2ab"/>`;
}

/** Газовая горелка на баллоне. */
export function gasTorch() {
  return `<defs>
    ${lin("can", [[0, "#8a1d14"], [0.3, "#e0483a"], [0.6, "#c32f22"], [1, "#6a140d"]], 0, 0, 1, 0)}
    ${lin("br", [[0, "#ffe9a8"], [0.5, "#d9b04a"], [1, "#8a6a1c"]])}
  </defs>
  ${shadow(560, 742, 200, 22)}
  <rect x="420" y="430" width="200" height="310" rx="20" fill="url(#can)"/>
  <path d="M420,450 Q520,380 620,450 Z" fill="url(#can)"/>
  <rect x="500" y="378" width="40" height="40" rx="6" fill="url(#br)"/>
  <path d="M520,388 L640,300 L860,190" stroke="url(#br)" stroke-width="26" fill="none" stroke-linecap="round"/>
  <path d="M860,190 L930,152" stroke="#33373b" stroke-width="40" stroke-linecap="round"/>
  <rect x="560" y="280" width="80" height="36" rx="10" fill="#33373b" transform="rotate(-30 600 298)"/>
  <rect x="450" y="520" width="140" height="120" rx="8" fill="#fff" opacity="0.9"/>
  <text x="520" y="595" text-anchor="middle" font-family="Manrope, Arial, sans-serif" font-weight="800" font-size="40" fill="#c32f22">GAS</text>`;
}

/** Навесной замок. */
export function padlock() {
  return `<defs>
    ${lin("lk", [[0, "#ffe9a8"], [0.4, "#e2b84e"], [1, "#8a6a1c"]], 0, 0, 1, 1)}
    ${lin("sh", METAL, 0, 0, 1, 0)}
  </defs>
  ${shadow(610, 712, 210, 24)}
  <path d="M480,420 L480,300 Q480,180 600,180 Q720,180 720,300 L720,420" stroke="url(#sh)" stroke-width="40" fill="none"/>
  <rect x="400" y="400" width="400" height="300" rx="40" fill="url(#lk)"/>
  <circle cx="600" cy="530" r="30" fill="#5a4410"/>
  <path d="M588,540 L612,540 L606,610 L594,610 Z" fill="#5a4410"/>`;
}

/** Дверная петля в раскрытом виде. */
export function hinge() {
  const holes = (x) => [330, 450, 570].map((y) => `<circle cx="${x}" cy="${y}" r="16" fill="#e9e3da" stroke="#8d949c" stroke-width="4"/>`).join("");
  return `${fastenerDefs()}
  ${shadow(600, 730, 300, 24)}
  <rect x="380" y="240" width="200" height="420" rx="14" fill="url(#sc_metal)"/>
  <rect x="620" y="240" width="200" height="420" rx="14" fill="url(#sc_metal)"/>
  <rect x="572" y="230" width="56" height="440" rx="26" fill="url(#sc_metal)" stroke="#7d848c" stroke-width="2"/>
  ${[300, 450, 600].map((y) => `<line x1="572" y1="${y}" x2="628" y2="${y}" stroke="#6d747c" stroke-width="3"/>`).join("")}
  ${holes(480)}${holes(720)}`;
}

/** Стяжной ремень: смотанная лента, храповик и крюк. */
export function strap() {
  const gear = (cx, cy, r) =>
    `<path d="${Array.from({ length: 28 }, (_, i) => {
      const a = (Math.PI * 2 * i) / 28;
      const rr = i % 2 ? r : r * 0.82;
      return `${i ? "L" : "M"}${f(cx + rr * Math.cos(a))},${f(cy + rr * Math.sin(a))}`;
    }).join(" ")} Z" fill="url(#sc_metal)" stroke="#6d747c" stroke-width="1.5"/>`;
  return `${fastenerDefs()}
  <defs>${lin("st", [[0, "#ffa04a"], [1, "#d25e05"]], 0, 0, 0, 1)}${rad("stR", [[0, "#ff9a3d"], [1, "#c95604"]])}${lin("grip", [[0, "#4a4e53"], [1, "#1f2124"]])}</defs>
  ${shadow(600, 712, 380, 26)}
  <circle cx="400" cy="510" r="180" fill="url(#stR)"/>
  ${Array.from({ length: 9 }, (_, i) => `<circle cx="400" cy="510" r="${60 + i * 14}" fill="none" stroke="#b44f04" stroke-width="2" opacity="0.7"/>`).join("")}
  <circle cx="400" cy="510" r="48" fill="#e9e3da" stroke="#b44f04" stroke-width="3"/>
  <path d="M520,650 L760,650 L760,690 L520,690 Z" fill="url(#st)"/>
  <rect x="700" y="560" width="230" height="130" rx="12" fill="url(#sc_metal)" stroke="#6d747c" stroke-width="2"/>
  ${gear(790, 600, 44)}
  <circle cx="790" cy="600" r="16" fill="#5f666e"/>
  <path d="M790,600 L960,470 L990,500 L820,628 Z" fill="url(#sc_metal)" stroke="#6d747c" stroke-width="2"/>
  <rect x="900" y="440" width="110" height="46" rx="18" fill="url(#grip)" transform="rotate(-37 955 463)"/>
  <path d="M930,640 L1010,640 Q1060,640 1060,600 L1060,560 Q1060,532 1034,532" stroke="url(#sc_metal)" stroke-width="22" fill="none" stroke-linecap="round"/>`;
}
