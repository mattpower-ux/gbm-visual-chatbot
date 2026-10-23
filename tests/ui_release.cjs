// Isolated UI smoke test: synthetic responses only, no production access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const { chromium } = require('playwright');
const py = fs.readFileSync('app/admin_ui.py', 'utf8');
const adminHtml = py.slice(py.indexOf('HTML = r"""') + 11, py.lastIndexOf('"""'));
let issued = 0;
let queries = [];
const fixture = {
  days: 30, questions: 4, sessions: 3, excluded: { test: 1 }, truncated: false,
  note: 'Synthetic test data. Early editorial signals require reporting.',
  logging: { stored: 5, pending: 1, failed: 1, last_error: 'Sheets delivery failed; check configuration.', sheets_configured: true },
  themes: [{ topic: 'Heat pumps', questions: 4, sessions: 3, weak_answers: 1, signal: 'Repeated across sessions',
    angle: 'Which heat pump tradeoffs are readers struggling to resolve?', constraints: { Cost: 3, Climate: 2 },
    examples: [{question: 'Can I afford a cold-climate heat pump?', id: 'test', date: '2026-10-22'}],
    coverage: [{url: 'https://www.greenbuildermedia.com/blog/heat-pumps', count: 2}] }],
  journeys: [[{question:'Which heat pump works in my climate?'},{question:'Does it require a new panel?'}]]
};
const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  if (req.url === '/admin') { res.setHeader('Content-Type','text/html'); return res.end(adminHtml); }
  if (req.url === '/') { res.setHeader('Content-Type','text/html'); return res.end(`<html><body><script src="/widget.js" data-api-base="http://127.0.0.1:${server.address().port}"></script></body></html>`); }
  if (req.url === '/widget.js') { res.setHeader('Content-Type','application/javascript'); return res.end(fs.readFileSync('widget/embed.js')); }
  if (req.url.startsWith('/api/admin/editorial-report')) return res.end(JSON.stringify(fixture));
  if (req.url === '/api/chat-session') { issued++; return res.end(JSON.stringify({session_id:'web-stable-fixture',token:'signed-fixture',expires_at:Date.now()/1000+3600})); }
  if (req.url === '/chat') {
    let raw = ''; for await (const chunk of req) raw += chunk;
    assert.equal(req.headers['x-chat-token'],'signed-fixture'); queries.push(JSON.parse(raw));
    return res.end(JSON.stringify({answer:'Published heat pump advice.',visual_summary:'Published heat pump advice.',sources:[],cards:[],magazines:[],videos:[],podcasts:[],key_insights:[],hot_take:null}));
  }
  res.end(JSON.stringify({logs:[],corrections:[],status:{},inbox:[],processing:[],done:[],failed:[]}));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser = await chromium.launch({channel:'chrome',headless:true});
    const page = await browser.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.route('**/*', route => route.request().url().startsWith(origin) ? route.continue() : route.abort());
    fs.mkdirSync('.test-output',{recursive:true});
    for (const [name,width,height] of [['desktop',1280,900],['mobile',390,844]]) {
      await page.setViewportSize({width,height});
      await page.goto(origin+'/admin');
      await page.locator('#editorial-generate').click();
      await page.getByText('Which heat pump tradeoffs are readers struggling to resolve?',{exact:true}).waitFor();
      assert.match(await page.locator('#editorial-status').innerText(),/4 questions across 3 sessions/);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path:`.test-output/editorial-${name}.png`});
    }
    await page.setViewportSize({width:1280,height:900});
    await page.goto(origin+'/');
    await page.locator('.gbm-launcher').click();
    for (const question of ['Which heat pump?', 'What about the cost?']) {
      await page.locator('.gbm-input').fill(question);
      await page.locator('.gbm-send').click();
      await page.getByText('Published heat pump advice.',{exact:true}).first().waitFor();
      await page.waitForFunction(() => !document.querySelector('.gbm-send').disabled);
    }
    await page.reload();
    await page.locator('.gbm-launcher').click();
    await page.locator('.gbm-input').fill('And installation?');
    await page.locator('.gbm-send').click();
    await page.waitForFunction(() => !document.querySelector('.gbm-send').disabled);
    assert.equal(issued,1);
    assert.equal(queries.length,3);
    assert(queries.every(q=>q.session_id==='web-stable-fixture'));
    assert.deepEqual(errors,[]);
    console.log('PASS: desktop/mobile report, no overflow, stable session across queries and reload, signed header.');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode=1; });
