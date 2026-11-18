#!/usr/bin/env node
// Regenerates src/assets/mapStyleDark.json / mapStyleLight.json from
// CloudParse's real up_dark_matter tile style, recolored to match this app's
// own @theme palette (src/styles/index.css) — same technique
// up-miniapps-explore/up-miniapps-by-night used for their own local styles:
// identical sources/layers/filters, only `paint` colors change.
//
// Run again whenever either the base CloudParse style changes upstream, or
// this app's own @theme accent colors change enough to warrant re-deriving
// (added 2026-10-06 — see AGENTS.md's "coverage audit" entry and
// build-log.md for the full story, including two real bugs this transform's
// own history already ran into once).
//
// Usage: node scripts/generate-map-style.js
//
// Layer-object-aware, not a blind hue regex over the serialized JSON: an
// early version did a global hsl(...) string replace and mixed up hue 210
// used by BOTH the water fill (wants pale in light mode) and the
// water_name label text (wants dark in light mode, same as every other
// label) — one lightness formula per hue can't tell those apart, and
// produced a near-invisible light-mode water label. This version walks
// each layer's actual paint keys and treats text-color/text-halo-color
// specially regardless of their original hue.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE_STYLE_URL = "https://tiles.cloudparse.fr/style/up_dark_matter";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ASSETS_DIR = path.join(__dirname, "..", "src", "assets");

function parseHsl(str) {
  const m = /^hsla?\((\d+), (\d+)%, (\d+)%(?:, ([\d.]+))?\)/.exec(str);
  if (!m) return null;
  return {
    a: m[4] !== undefined ? Number(m[4]) : null,
    h: Number(m[1]),
    l: Number(m[3]),
    s: Number(m[2]),
  };
}

function toHsl({ h, s, l, a }) {
  return a !== null
    ? `hsla(${h}, ${s}%, ${l}%, ${a})`
    : `hsl(${h}, ${s}%, ${l}%)`;
}

// isLabel: true for any text-color/text-halo-color value — these always
// need the "readable foreground on this theme's background" treatment
// regardless of which semantic category (water/place/road name) they
// label.
function recolor(str, theme, isLabel) {
  const c = parseHsl(str);
  if (!c) return str;
  let { h, s, l, a } = c;

  // highway_name_motorway's own text-color is hue 35 (amber) in the base
  // style, matching the motorway line it labels — exempt it from the
  // generic "every label goes neutral" rule below so the name stays
  // amber-tinted like the road itself, not flattened to plain gray-blue.
  if (isLabel && h === 35) {
    l = theme === "dark" ? l : Math.max(30, Math.min(50, 100 - l - 10));
    return toHsl({ a, h, l, s });
  }

  if (isLabel) {
    // Every label (and its halo) shares one treatment: neutral hue, full
    // lightness inversion for light mode (dark text on light bg), small
    // saturation bump to stay legible instead of washed-out gray.
    h = theme === "dark" ? 222 : 220;
    s = Math.min(100, s + (theme === "dark" ? 8 : 4));
    l = theme === "dark" ? l : Math.max(0, Math.min(100, 100 - l + 2));
    return toHsl({ a, h, l, s });
  }

  if (h === 220) {
    // Neutral UI palette: background/land/roads/buildings fills+lines —
    // this app's own brand-bg/brand-card already sit at hue ~222-223, so
    // the dark theme only needs a tiny nudge; light theme inverts.
    h = theme === "dark" ? 222 : 220;
    s = Math.min(100, s + (theme === "dark" ? 8 : 4));
    l = theme === "dark" ? l : Math.max(0, Math.min(100, 100 - l + 2));
  } else if (h === 210) {
    // Water fill/line: stays blue, pale in light mode (not inverted to
    // dark — only text-color/text-halo-color get that treatment, above).
    h = 205;
    l = theme === "dark" ? l : Math.max(60, Math.min(92, 100 - l + 60));
  } else if (h === 140) {
    // Park/wood fill: stays green, pale in light mode.
    l = theme === "dark" ? l : Math.max(60, Math.min(88, 100 - l + 62));
  } else if (h === 35) {
    // Motorway highlight: stays amber, darkened for contrast in light mode.
    l = theme === "dark" ? l : Math.max(35, Math.min(55, 100 - l));
  }
  return toHsl({ a, h, l, s });
}

const LABEL_KEYS = new Set(["text-color", "text-halo-color"]);

// Paint values are either a plain hsl(...) string, or a MapLibre expression
// object with a `stops` array of [zoom, value] pairs (value itself can be a
// string or nested further) — recurse into stops, leave everything else
// (widths, opacities, non-color stops) untouched.
function recolorValue(value, theme, isLabel) {
  if (typeof value === "string") {
    return recolor(value, theme, isLabel);
  }
  if (value && typeof value === "object" && Array.isArray(value.stops)) {
    return {
      ...value,
      stops: value.stops.map(([zoom, v]) => [
        zoom,
        typeof v === "string" ? recolor(v, theme, isLabel) : v,
      ]),
    };
  }
  return value;
}

function recolorLayer(layer, theme) {
  const out = JSON.parse(JSON.stringify(layer));
  if (!out.paint) return out;
  for (const [key, value] of Object.entries(out.paint)) {
    out.paint[key] = recolorValue(value, theme, LABEL_KEYS.has(key));
  }
  return out;
}

async function main() {
  const response = await fetch(BASE_STYLE_URL);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${BASE_STYLE_URL}: ${response.status}`);
  }
  const base = await response.json();

  for (const theme of ["dark", "light"]) {
    const style = JSON.parse(JSON.stringify(base));
    style.layers = style.layers.map((layer) => recolorLayer(layer, theme));
    const outPath = path.join(
      ASSETS_DIR,
      `mapStyle${theme === "dark" ? "Dark" : "Light"}.json`,
    );
    fs.writeFileSync(outPath, `${JSON.stringify(style, null, 2)}\n`);
    console.log(`Wrote ${outPath}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
