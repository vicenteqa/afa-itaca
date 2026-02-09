import { getCollection } from 'astro:content';
import rss from '@astrojs/rss';
import { SITE_DESCRIPTION, SITE_TITLE } from '../consts';

export async function GET(context) {
	const noticies = await getCollection('noticies');
	return rss({
		title: SITE_TITLE,
		description: SITE_DESCRIPTION,
		site: context.site,
		items: noticies.map((noticia) => ({
			...noticia.data,
			link: `/noticies/${noticia.id}/`,
		})),
	});
}
