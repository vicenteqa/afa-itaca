// Reescriu les rutes absolutes ("/...") del build estàtic perquè funcionin
// sota el subdirectori d'un preview de PR a GitHub Pages
// (p.ex. /afa-itaca/pr-preview/pr-34/). Només s'executa al workflow de
// previews; el build de producció (Netlify, arrel del domini) no el toca.
import { readdirSync, statSync, readFileSync, writeFileSync } from 'node:fs';
import { extname, join } from 'node:path';

const basePath = process.argv[2];
if (!basePath) {
  console.error('Ús: node rewrite-preview-base.mjs <base-path>');
  process.exit(1);
}

const distDir = 'dist';
const rewriteExtensions = new Set(['.html', '.css']);

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry);
    if (statSync(fullPath).isDirectory()) {
      walk(fullPath);
    } else if (rewriteExtensions.has(extname(fullPath))) {
      rewrite(fullPath);
    }
  }
}

function rewrite(filePath) {
  const original = readFileSync(filePath, 'utf8');
  const updated = original
    .replace(/((?:href|src)=")\/(?!\/)/g, `$1${basePath}/`)
    .replace(/(url\((['"]?))\/(?!\/)/g, `$1${basePath}/`);
  if (updated !== original) {
    writeFileSync(filePath, updated);
  }
}

walk(distDir);
console.log(`Rutes absolutes reescrites a "${distDir}/" amb el prefix "${basePath}"`);
