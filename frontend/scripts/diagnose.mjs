import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';

async function diagnose() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
  });

  const errors = [];
  context.on('page', (page) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(`[CONSOLE ERROR] ${msg.text()}`);
      }
    });
    page.on('pageerror', (err) => {
      errors.push(`[PAGE ERROR] ${err.message}`);
    });
    page.on('response', (resp) => {
      if (resp.status() >= 400) {
        errors.push(`[HTTP ${resp.status()}] ${resp.url()}`);
      }
    });
  });

  const page = await context.newPage();

  // 1. Open page at root
  console.log('=== Opening page at / ===');
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(2000);

  // 2. Get current URL after redirects
  const currentUrl = page.url();
  console.log(`Current URL: ${currentUrl}`);

  // 3. Check main content
  const mainHtml = await page.evaluate(() => {
    const main = document.querySelector('main');
    return main ? main.innerHTML : '<MAIN NOT FOUND>';
  });
  console.log(`Main HTML: ${mainHtml.substring(0, 500)}`);

  // 4. Check route.name
  const routeName = await page.evaluate(() => {
    const app = document.querySelector('#app');
    return app ? app.innerHTML.length : 'no app';
  });
  console.log(`App inner HTML length: ${routeName}`);

  // 5. Screenshot
  await page.screenshot({ path: '/tmp/diagnose.png', fullPage: true });
  console.log('Screenshot saved to /tmp/diagnose.png');

  // 6. Check for router-view content
  const routerViewContent = await page.evaluate(() => {
    const routerView = document.querySelector('router-view') || 
      document.querySelector('main')?.firstElementChild;
    return routerView ? routerView.outerHTML.substring(0, 300) : 'router-view not found';
  });
  console.log(`Router view content: ${routerViewContent}`);

  // 7. Try navigating to /cases directly
  console.log('\n=== Opening page at /cases ===');
  await page.goto(`${BASE}/cases`, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(2000);
  
  const casesUrl = page.url();
  console.log(`URL after /cases: ${casesUrl}`);
  
  const casesMain = await page.evaluate(() => {
    const main = document.querySelector('main');
    return main ? main.innerHTML.substring(0, 500) : '<MAIN NOT FOUND>';
  });
  console.log(`Main HTML at /cases: ${casesMain}`);

  // Print all errors
  if (errors.length > 0) {
    console.log('\n=== ERRORS ===');
    for (const err of errors) {
      console.log(err);
    }
  } else {
    console.log('\nNo errors found!');
  }

  await browser.close();
}

diagnose().catch(err => {
  console.error('Diagnose failed:', err);
  process.exit(1);
});
