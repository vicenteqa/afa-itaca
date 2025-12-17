# Configuración de Decap CMS con GitHub OAuth

## Paso 1: Crear OAuth App en GitHub

1. Ve a [GitHub Settings → Developer settings → OAuth Apps](https://github.com/settings/developers)
2. Click en **"New OAuth App"**
3. Completa los campos:

   **Application name:** `AFA Ítaca CMS`

   **Homepage URL:** `https://tu-dominio.com` (la URL donde estará alojado tu sitio)

   **Authorization callback URL:** `https://api.netlify.com/auth/done`

   **Application description:** (opcional) `CMS para gestionar contenido de AFA Ítaca`

4. Click en **"Register application"**
5. **Guarda el Client ID** que aparece
6. Click en **"Generate a new client secret"**
7. **Guarda el Client Secret** (solo se muestra una vez)

## Paso 2: Configurar autenticación en tu hosting

### Opción A: Si usas Netlify (recomendado)

1. Sube tu sitio a Netlify
2. Ve a: **Site settings → Access control → OAuth**
3. Click en **"Install provider"** → Selecciona **GitHub**
4. Pega tu **Client ID** y **Client Secret**
5. Click en **"Install"**

¡Listo! Accede a `tu-sitio.netlify.app/admin` y logueate con GitHub.

### Opción B: Si usas Vercel, Cloudflare Pages u otro hosting

Necesitarás un proxy OAuth. Hay dos opciones:

**1. Usar el servicio de Netlify solo para OAuth (gratis):**
   - Crea un sitio vacío en Netlify
   - Configura OAuth en ese sitio (pasos arriba)
   - Mantén `https://api.netlify.com/auth/done` como callback URL
   - Tu CMS funcionará pero la autenticación pasará por Netlify

**2. Desplegar tu propio proxy OAuth (más complejo):**
   - Usa [netlify-cms-oauth-provider](https://github.com/vencax/netlify-cms-github-oauth-provider)
   - Despliégalo en Heroku, Railway o similar
   - Actualiza el callback URL en GitHub a tu proxy
   - Añade `base_url` en `config.yml`:
     ```yaml
     backend:
       name: github
       repo: vicenteqa/afa-itaca
       branch: main
       base_url: https://tu-proxy-oauth.herokuapp.com
     ```

## Paso 3: Usar el CMS

1. Accede a `https://tu-dominio.com/admin`
2. Click en **"Login with GitHub"**
3. Autoriza la aplicación
4. ¡Ya puedes editar contenido!

## Gestión de permisos

Para que alguien pueda editar contenido:
- Debe tener una cuenta de GitHub
- Debe tener permisos de **write** en el repositorio `vicenteqa/afa-itaca`
- Añádelo como colaborador en: `https://github.com/vicenteqa/afa-itaca/settings/access`

## Qué puede gestionar el CMS

✅ **Notícies** - Blog posts / noticias
✅ **Documents** - PDFs, calendarios, menús, normativas
✅ **Pàgines** - L'AFA, Documents d'Interés, Contacte
✅ **Comissions** - Comisiones y sus descripciones

Todos los cambios se guardan automáticamente como commits en GitHub.

## Troubleshooting

**Error al hacer login:** Verifica que el callback URL en GitHub sea exactamente `https://api.netlify.com/auth/done`

**No puedo editar:** Verifica que tu usuario de GitHub tenga permisos de write en el repo

**Los cambios no aparecen:** El sitio debe reconstruirse después de cada cambio. Configura auto-deploy en tu hosting.
