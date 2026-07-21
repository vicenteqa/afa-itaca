import { test, expect } from '@playwright/test';
import { HomePage } from './pages/HomePage';

const EXPECTED_COMISSIONS = [
  'Espai de Migdia',
  'Extraescolars',
  'Festes',
  'Acollida Matinal',
  'Formació i Famílies',
  'Medi Ambient',
  'Patis',
  'Comunicació',
  'Casals',
];

test.describe('Navegació', () => {
  test('el botó CTA del header apunta a /familia-socia', async ({ page }) => {
    const home = new HomePage(page);
    await home.goto();
    await expect(home.header.ctaButton).toHaveAttribute('href', '/familia-socia');
  });

  test('el desplegable de comissions conté totes les comissions', async ({ page }) => {
    const home = new HomePage(page);
    await home.goto();
    await home.header.openComissionsDropdown();

    const items = home.header.dropdownItems();
    const texts = await items.allTextContents();
    for (const expected of EXPECTED_COMISSIONS) {
      expect(texts).toContain(expected);
    }
  });

  test('/about retorna 404', async ({ request }) => {
    const response = await request.get('/about');
    expect(response.status()).toBe(404);
  });
});
