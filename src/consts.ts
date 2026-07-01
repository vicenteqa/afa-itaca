// Place any global data in this file.
// You can import this data from anywhere in your site by using the `import` keyword.

export const SITE_TITLE = 'AFA Ítaca';
export const SITE_DESCRIPTION = 'Associació de Famílies d\'Alumnes de l\'Escola Ítaca - Vilanova i la Geltrú';

const enabledValues = new Set(['1', 'true', 'yes', 'on']);

export const SHOW_HOME_INSTAGRAM_FEED = enabledValues.has(
	(import.meta.env.SHOW_HOME_INSTAGRAM_FEED ?? '').toLowerCase()
);
