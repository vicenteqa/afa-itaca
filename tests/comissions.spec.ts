import { test, expect } from '@playwright/test';
import { ComissioPage } from './pages/ComissioPage';

test.describe('Comissions', () => {
  test('/comissions/casals menciona Needsports', async ({ page }) => {
    const comissio = new ComissioPage(page);
    await comissio.goto('casals');
    await expect(comissio.content).toContainText('Needsports');
  });

  test('/comissions/casals menciona Jocs i Taula', async ({ page }) => {
    const comissio = new ComissioPage(page);
    await comissio.goto('casals');
    await expect(comissio.content).toContainText('Jocs i Taula');
  });

  test('/comissions/extraescolars té la secció de documents', async ({ page }) => {
    const comissio = new ComissioPage(page);
    await comissio.goto('extraescolars');
    await expect(comissio.content.getByRole('link', { name: /Autorització i normativa/ })).toBeVisible();
    await expect(comissio.content.getByRole('link', { name: /Autoritzacions/ })).toBeVisible();
  });

  test('/comissions/menjador és accessible', async ({ page }) => {
    const comissio = new ComissioPage(page);
    await comissio.goto('menjador');
    await expect(comissio.title).toContainText('Espai de Migdia');
  });
});
