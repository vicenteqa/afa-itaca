// @ts-check

import mdx from '@astrojs/mdx';
import netlify from '@astrojs/netlify';
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  site: 'https://www.afaitaca.org',
  output: 'static',
  // En els previews de PR (build estàtic a GitHub Pages) desactivem el
  // proxy d'imatges de Netlify: aquell endpoint no existeix fora de Netlify,
  // així que les imatges optimitzades s'exporten com a fitxers estàtics.
  adapter: netlify({ imageCDN: process.env.PR_PREVIEW !== 'true' }),
  integrations: [mdx(), sitemap()],

  vite: {
    plugins: [tailwindcss()],
  },
});
