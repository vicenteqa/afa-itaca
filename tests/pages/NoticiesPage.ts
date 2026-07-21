import { type Page, type Locator } from '@playwright/test';

export class NoticiesPage {
  readonly articles: Locator;
  readonly dates: Locator;

  constructor(private page: Page) {
    this.articles = page.locator('article');
    this.dates = page.locator('time');
  }

  async goto() {
    await this.page.goto('/noticies');
  }
}
