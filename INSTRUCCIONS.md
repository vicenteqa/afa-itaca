# Instruccions d'ús del Web de l'AFA Ítaca

## Contingut creat

S'ha creat un website complet per a l'AFA Ítaca amb les següents seccions:

### Pàgines principals

1. **Inici** (`/`) - Pàgina principal amb accés ràpid a totes les seccions
2. **L'AFA** (`/lafa`) - Informació sobre l'associació
3. **Comissions** (`/comissions`) - Les 9 comissions de l'AFA:
   - Menjador
   - Acollida Matinal
   - Extraescolars
   - Formació Familiar
   - Medi Ambient
   - Patis
   - Festes
   - Casals d'Estiu
   - Comunicació
4. **Notícies** (`/noticies`) - Blog amb les últimes novetats
5. **Contacte** (`/contacte`) - Formulari de contacte i informació

### Contingut d'exemple

- 5 notícies d'exemple amb contingut realista
- 9 comissions amb tota la informació
- 2 pàgines estàtiques (L'AFA, Contacte)

## Com executar el projecte

### Desenvolupament local

```bash
npm install          # Instal·lar dependències (primera vegada)
npm run dev          # Iniciar servidor de desenvolupament
```

El web estarà disponible a `http://localhost:4321`

### Build per a producció

```bash
npm run build        # Crear build de producció
npm run preview      # Previsualitzar el build
```

## Netlify CMS - Editar contingut sense codi

### Configuració inicial de Netlify CMS

1. **Desplegar el web a Netlify**:
   - Connecta el repositori GitHub a Netlify
   - Configura el build: `npm run build`
   - Carpeta de publicació: `dist`

2. **Activar Netlify Identity**:
   - A la configuració de Netlify, ves a "Identity"
   - Fes clic a "Enable Identity"
   - A "Settings and usage", configura:
     - Registration preferences: "Invite only" (només per invitació)
     - External providers: Pots afegir Google, etc.

3. **Activar Git Gateway**:
   - A "Identity" > "Services" > "Git Gateway"
   - Fes clic a "Enable Git Gateway"

### Com accedir a l'editor (Netlify CMS)

Un cop configurat:

1. Ves a `https://elteuweb.com/admin` (canvia per la teva URL)
2. Inicia sessió amb el teu compte de Netlify Identity
3. Ja pots editar el contingut!

### Convidar editors

1. A Netlify, ves a "Identity" > "Invite users"
2. Introdueix l'email de la persona que vols convidar
3. Rebrà un email per crear el seu compte
4. Podrà accedir a `/admin` per editar contingut

### Què poden editar els editors?

**Des de l'interfície de Netlify CMS** (sense tocar codi):

- **Notícies**: Crear, editar i eliminar notícies del blog
- **Pàgines**: Editar contingut de L'AFA i Contacte
- **Comissions**: Editar o afegir noves comissions

### Com crear una notícia nova

1. Accedeix a `/admin`
2. Fes clic a "Notícies" al menú lateral
3. Fes clic a "New Notícies"
4. Omple els camps:
   - **Títol**: Títol de la notícia
   - **Descripció**: Resum breu
   - **Data de Publicació**: Data i hora
   - **Imatge Principal**: Opcional
   - **Contingut**: Text complet amb format Markdown
5. Fes clic a "Publish" per publicar o "Save" per guardar com a esborrany

### Com editar una pàgina

1. Accedeix a `/admin`
2. Fes clic a "Pàgines"
3. Selecciona la pàgina que vols editar (L'AFA o Contacte)
4. Modifica el contingut
5. Fes clic a "Publish"

## Personalització

### Canviar colors

Edita el fitxer `src/styles/global.css` i modifica les variables CSS:

```css
:root {
  --accent: 136, 58, 234;      /* Color principal */
  --accent-dark: 49, 10, 101;  /* Color fosc */
  /* ... altres colors ... */
}
```

### Afegir el teu logo

Substitueix el fitxer `public/favicon.svg` pel teu logo.

### Actualitzar informació de contacte

Edita la pàgina de Contacte des de Netlify CMS o directament a `src/content/pages/contacte.md`.

### Modificar xarxes socials

Edita `src/components/Header.astro` i canvia l'enllaç d'Instagram (línia 18):

```astro
<a href="https://www.instagram.com/el_teu_usuari/" target="_blank">
```

## Formulari de contacte

El formulari de contacte està configurat per funcionar amb Netlify Forms automàticament quan despleguis a Netlify. Els missatges arribaran a la secció "Forms" del teu panell de Netlify.

## Suport i ajuda

- **Documentació d'Astro**: https://docs.astro.build
- **Documentació de Netlify CMS**: https://www.netlifycms.org/docs/
- **Documentació de Netlify**: https://docs.netlify.com

## Estructura de carpetes

```
afa-itaca/
├── public/
│   ├── admin/          # Netlify CMS
│   ├── uploads/        # Imatges i documents pujats
│   └── fonts/          # Fonts personalitzades
├── src/
│   ├── components/     # Components reutilitzables
│   ├── content/        # Tot el contingut del web
│   │   ├── noticies/   # Notícies del blog
│   │   ├── comissions/ # Comissions de l'AFA
│   │   └── pages/      # Pàgines estàtiques
│   ├── layouts/        # Plantilles de pàgina
│   ├── pages/          # Rutes del web
│   └── styles/         # Estils globals
└── package.json        # Dependències del projecte
```

## Notes importants

1. **Sempre fes un backup** abans de fer canvis importants
2. **Prova els canvis en local** abans de desplegar a producció
3. **Git**: Tots els canvis des de Netlify CMS es guarden automàticament al repositori Git
4. **Imatges**: Intenta que les imatges no siguin massa grans (màx 1-2 MB)
5. **Accés a /admin**: Només persones convidades poden accedir

## Checklist abans de publicar

- [ ] Desplegar a Netlify
- [ ] Activar Netlify Identity
- [ ] Activar Git Gateway
- [ ] Convidar editors
- [ ] Canviar logo i favicon
- [ ] Actualitzar informació de contacte
- [ ] Provar el formulari de contacte
- [ ] Eliminar contingut d'exemple (blog posts placeholder)
- [ ] Afegir contingut real

Bona sort amb el vostre nou web! 🎉
