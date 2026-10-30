// Dispara un deploy de producció des del botó "Desplegar canvis" del CMS.
// La URL del build hook viu a la variable d'entorn NETLIFY_BUILD_HOOK_URL
// (mai al client). Només s'accepta si la petició porta un JWT vàlid de
// Netlify Identity: Netlify el verifica i el deixa a context.clientContext.user.
export const handler = async (event, context) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }

  if (!context.clientContext?.user) {
    return { statusCode: 401, body: 'No autoritzat' };
  }

  const hookUrl = process.env.NETLIFY_BUILD_HOOK_URL;
  if (!hookUrl) {
    return { statusCode: 500, body: 'Falta NETLIFY_BUILD_HOOK_URL' };
  }

  const res = await fetch(hookUrl, { method: 'POST' });
  if (!res.ok) {
    return { statusCode: 502, body: 'No s\'ha pogut iniciar el desplegament' };
  }

  return { statusCode: 200, body: 'ok' };
};
