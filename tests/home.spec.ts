import { test, expect } from '@playwright/test';
import { HomePage } from './pages/HomePage';

test.describe('Pàgina d\'inici', () => {
  test('mostra el títol de benvinguda', async ({ page }) => {
    const home = new HomePage(page);
    await home.goto();
    await expect(home.heroTitle).toContainText('Benvinguts');
  });

  test('mostra notícies recents', async ({ page }) => {
    const home = new HomePage(page);
    await home.goto();
    await expect(home.newsCards).toHaveCount(3);
  });

  test('el link del Menú del Mes no apunta al WordPress antic', async ({ page }) => {
    const home = new HomePage(page);
    await home.goto();
    const href = await home.menuLink.getAttribute('href');
    expect(href).not.toContain('afaitaca.org');
    expect(href).toContain('menjador.jpg');
  });
});
