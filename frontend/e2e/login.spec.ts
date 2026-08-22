import { expect, test } from '@playwright/test';

test('loads the authentication surface without exposing a bearer token', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Data-Berge OS/);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.getByLabel(/email/i)).toBeVisible();
  await expect(page.getByLabel(/^password$/i)).toBeVisible();
  const token = await page.evaluate(() => localStorage.getItem('db_token'));
  expect(token).toBeNull();
});
