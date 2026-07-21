import { type Page, type Locator } from '@playwright/test';

export class HeaderComponent {
  readonly ctaButton: Locator;
  private readonly comissionsToggle: Locator;
  private readonly dropdownMenu: Locator;

  constructor(private page: Page) {
    this.ctaButton = page.locator('a.nav-cta-button');
    this.comissionsToggle = page.locator('button.dropdown-toggle');
    this.dropdownMenu = page.locator('.dropdown-menu');
  }

  async openComissionsDropdown() {
    await this.comissionsToggle.hover();
    await this.dropdownMenu.waitFor({ state: 'visible' });
  }

  dropdownItems() {
    return this.dropdownMenu.locator('a');
  }
}
