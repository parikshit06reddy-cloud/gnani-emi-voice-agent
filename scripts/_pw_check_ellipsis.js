const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
  await page.goto('http://localhost:8000/index.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  const info = await page.evaluate(() => {
    const rows = document.querySelectorAll('table tbody tr');
    const headers = Array.from(document.querySelectorAll('table thead th')).map(th => th.textContent.trim());
    const dispositionIdx = headers.findIndex(h => /disposition/i.test(h));
    const out = [];
    rows.forEach((row) => {
      const cells = row.querySelectorAll('td');
      const last = dispositionIdx >= 0 ? cells[dispositionIdx] : null;
      if (last) {
        const style = getComputedStyle(last);
        out.push({
          text: last.textContent,
          title: last.getAttribute('title'),
          scrollWidth: last.scrollWidth,
          clientWidth: last.clientWidth,
          overflow: style.overflow,
          textOverflow: style.textOverflow,
          whiteSpace: style.whiteSpace,
          isTruncated: last.scrollWidth > last.clientWidth,
        });
      }
    });
    return out;
  });
  console.log(JSON.stringify(info, null, 2));
  await browser.close();
})();
