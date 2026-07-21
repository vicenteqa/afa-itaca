import { type Page, type Locator } from '@playwright/test';

export class FamiliaSociaPage {
  readonly title: Locator;
  readonly altaButton: Locator;

  constructor(private page: Page) {
    this.title = page.locator('.hero h1');
    this.altaButton = page.getByRole('link', { name: /Alta de família sòcia/ });
  }

  async goto() {
    await this.page.goto('/familia-socia');
  }
}
