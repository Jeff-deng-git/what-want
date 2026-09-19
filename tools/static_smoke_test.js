/* Smoke test for the GitHub Pages static mode.
   Runs index.html in jsdom with ?static=1 and checks that chapter cards render.
*/
const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = require('path');

const indexPath = path.resolve(__dirname, '..', 'index.html');
const html = fs.readFileSync(indexPath, 'utf-8');

function createWindow(url) {
  return new JSDOM(html, {
    url,
    runScripts: 'dangerously',
    resources: 'usable',
    beforeParse(window) {
      // Polyfill browser globals missing in jsdom
      window.Response = Response;
      // Resolve relative URLs against the jsdom document location, then delegate to Node fetch.
      window.fetch = (input, init) => {
        const url2 = typeof input === 'string' ? new URL(input, window.location.href).href : input;
        return fetch(url2, init);
      };
    },
  }).window;
}

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  // Test 1: landing page lists all chapters
  const landingWin = createWindow('http://localhost:8090/?static=1');
  await sleep(2000);
  const cards = landingWin.document.querySelectorAll('.ch-card');
  const grid = landingWin.document.querySelector('.ch-grid');
  const error = landingWin.document.querySelector('.error');
  console.log('landing cards:', cards.length);
  console.log('grid present:', !!grid);
  if (error) console.log('error text:', error.textContent.slice(0, 200));
  if (cards.length < 4) {
    console.error('FAIL: expected at least 4 chapter cards');
    process.exit(1);
  }

  // Test 2: reader page renders chapter content
  const readerWin = createWindow('http://localhost:8090/?static=1&chapter=ch01');
  await sleep(2000);
  const bookContent = readerWin.document.querySelector('#bookContent');
  console.log('bookContent present:', !!bookContent);
  if (bookContent) console.log('bookContent length:', bookContent.textContent.length);
  if (!bookContent || bookContent.textContent.length < 50) {
    console.error('FAIL: chapter content did not render');
    process.exit(1);
  }

  console.log('PASS');
  process.exit(0);
})();
