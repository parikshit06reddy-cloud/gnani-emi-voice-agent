const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
  await page.setViewportSize({ width: 1500, height: 1100 });

  // --- Index page ---
  await page.goto('http://localhost:8000/index.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/home/user/workspace/gnani-emi-voice-agent/docs/screenshots/dashboard-list.png', fullPage: true });
  console.log('index screenshot saved');

  // --- Detail page for the language-switch Spanish PTP call ---
  const callId = 'CALL-20260728-0008';
  await page.goto(`http://localhost:8000/detail.html?call_id=${callId}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // Try to read audio duration
  let duration = null;
  try {
    await page.waitForSelector('audio', { timeout: 5000 });
    duration = await page.evaluate(async () => {
      const audio = document.querySelector('audio');
      if (!audio) return null;
      audio.preload = 'metadata';
      audio.load();
      if (audio.readyState >= 1 && !isNaN(audio.duration) && audio.duration > 0) {
        return audio.duration;
      }
      return await new Promise((resolve) => {
        const onLoaded = () => { resolve(audio.duration); };
        audio.addEventListener('loadedmetadata', onLoaded, { once: true });
        setTimeout(() => resolve(audio.duration || null), 6000);
      });
    });
  } catch (e) {
    console.log('audio element wait error:', e.message);
  }
  console.log('AUDIO_DURATION_SECONDS:', duration);

  await page.screenshot({ path: '/home/user/workspace/gnani-emi-voice-agent/docs/screenshots/dashboard-detail.png', fullPage: true });
  console.log('detail screenshot saved for', callId);

  await browser.close();
})();
