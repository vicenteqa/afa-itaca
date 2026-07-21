import { type Page, type Locator } from '@playwright/test';
import { HeaderComponent } from './HeaderComponent';

export class HomePage {
  readonly header: HeaderComponent;
  readonly heroTitle: Locator;
  readonly newsCards: Locator;
  readonly menuLink: Locator;

  constructor(private page: Page) {
    this.header = new HeaderComponent(page);
    this.heroTitle = page.locator('.hero h1');
    this.newsCards = page.locator('.news-card');
    this.menuLink = page.locator('#menu-link');
  }

  async goto() {
    await this.page.goto('/');
  }
}
