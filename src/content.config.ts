import { defineCollection, z } from 'astro:content';
import { glob, file } from 'astro/loaders';

const noticies = defineCollection({
	loader: glob({ base: './src/content/noticies', pattern: '**/*.{md,mdx}' }),
	schema: z.object({
		title: z.string(),
		description: z.string(),
		pubDate: z.coerce.date(),
		heroImage: z.string().optional(),
	}),
});

const pages = defineCollection({
	loader: glob({ base: './src/content/pages', pattern: '**/*.{md,mdx}' }),
	schema: z.object({
		title: z.string(),
		description: z.string(),
		email: z.string().optional(),
		phone: z.string().optional(),
		address: z.string().optional(),
	}),
});

const comissions = defineCollection({
	loader: glob({ base: './src/content/comissions', pattern: '**/*.{md,mdx}' }),
	schema: z.object({
		title: z.string(),
		description: z.string(),
		icon: z.string().optional(),
		order: z.number().default(0),
	}),
});

export const collections = { noticies, pages, comissions };

