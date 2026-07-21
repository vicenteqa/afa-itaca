import { test, expect } from '@playwright/test';
import { NoticiesPage } from './pages/NoticiesPage';

const CATALAN_MONTHS = [
  'gener', 'febrer', 'març', 'abril', 'maig', 'juny',
  'juliol', 'agost', 'setembre', 'octubre', 'novembre', 'desembre',
];

test.describe('Notícies', () => {
  test('les dates es mostren en català', async ({ page }) => {
    const noticies = new NoticiesPage(page);
    await noticies.goto();

    const dates = noticies.dates;
    const count = await dates.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const text = (await dates.nth(i).textContent()) ?? '';
      const hasCatalanMonth = CATALAN_MONTHS.some((m) => text.includes(m));
      expect(hasCatalanMonth, `Data "${text}" no és en català`).toBe(true);
    }
  });

  test('mostra almenys 5 notícies', async ({ page }) => {
    const noticies = new NoticiesPage(page);
    await noticies.goto();
    await expect(page.locator('.posts-list h2')).toHaveCount(8);
  });
});
