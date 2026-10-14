import { chromium } from 'playwright';
import fs from 'fs';

const BASE = process.env.BASE_URL || 'http://localhost:5173';
const API  = process.env.API_URL  || 'http://localhost:8000';
const USER = process.env.APP_USER || 'admin';
const PASS = process.env.APP_PASS || '';
const OUT = 'screenshots';
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();

const shot = async (name, full = true) => {
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  console.log('saved', name);
};
// Token lives only in memory: never page.goto() a protected route after login.
const nav = (label) =>
  page.getByRole('link', { name: label, exact: true }).first().click();
const clickAny = (re) =>
  page.getByRole('link', { name: re }).or(page.getByRole('button', { name: re })).first().click();

await page.goto(`${BASE}/login`);
const user = page.locator('input').first();
const pass = page.locator('input[type=password]');
const submit = page.getByRole('button', { name: /sign in|log in|login/i });
await shot('fig_16_01_login', false);
await user.fill(USER); await pass.fill('wrong-password'); await submit.click();
await page.waitForTimeout(800);
await shot('fig_16_01b_login_error', false);
await pass.fill(PASS); await submit.click();
await page.waitForURL((u) => !u.pathname.includes('login'));

await nav('Dashboard');     await shot('fig_16_02_dashboard');
await nav('Customers');     await shot('fig_16_03_customer_list');
await clickAny(/add customer|new customer/i);
                            await shot('fig_16_04_customer_form');
await nav('Products');      await shot('fig_16_05_product_list');
await clickAny(/add product|new product/i);
                            await shot('fig_16_06_product_form');
await nav('Invoices');      await shot('fig_16_09_invoice_list');
await clickAny(/new invoice|create invoice/i);
                            await shot('fig_16_07_invoice_form_blank');
await nav('Invoices');
await page.locator('a', { hasText: /(INV|SEED)-/ }).first().click();
                            await shot('fig_16_10_invoice_detail');
await nav('Aging Report');  await shot('fig_16_13_aging_report');

const admin = await ctx.newPage();
await admin.goto(`${API}/admin/login/`);
await admin.fill('#id_username', USER);
await admin.fill('#id_password', PASS);
await admin.click('input[type=submit]');
await admin.goto(`${API}/admin/billing/company/`);
await admin.locator('#result_list a').first().click();
await admin.waitForLoadState('networkidle');
await admin.screenshot({ path: `${OUT}/fig_16_14_company_admin.png`, fullPage: true });

await browser.close();
