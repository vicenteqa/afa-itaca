import { type Page, type Locator } from '@playwright/test';

export class ComissioPage {
  readonly title: Locator;
  readonly content: Locator;

  constructor(private page: Page) {
    this.title = page.locator('.hero h1');
    this.content = page.locator('.content');
  }

  async goto(slug: string) {
    await this.page.goto(`/comissions/${slug}`);
  }
}
