import { test, expect } from '@playwright/test';
import { FamiliaSociaPage } from './pages/FamiliaSociaPage';

test.describe('Família Sòcia', () => {
  test('la pàgina es renderitza correctament', async ({ page }) => {
    const familiaSocia = new FamiliaSociaPage(page);
    await familiaSocia.goto();
    await expect(familiaSocia.title).toContainText('Fes-te família sòcia');
  });

  test('té el botó d\'alta que apunta a ampasoft', async ({ page }) => {
    const familiaSocia = new FamiliaSociaPage(page);
    await familiaSocia.goto();
    await expect(familiaSocia.altaButton).toBeVisible();
    const href = await familiaSocia.altaButton.getAttribute('href');
    expect(href).toContain('ampasoft.net');
  });

  test('conté la informació de la quota anual', async ({ page }) => {
    const familiaSocia = new FamiliaSociaPage(page);
    await familiaSocia.goto();
    await expect(page.locator('.content')).toContainText('45€');
  });
});
