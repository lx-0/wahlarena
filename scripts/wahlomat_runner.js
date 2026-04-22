/**
 * Wahl-O-Mat runner: drives the live Bundestagswahl 2025 Wahl-O-Mat in a headless browser,
 * submits LLM answers, and captures the official party alignment result page.
 *
 * Usage:
 *   node wahlomat_runner.js --answers path/to/answers.json --out path/to/run_dir
 *
 * answers.json format: array of 38 values, each -1 (disagree), 0 (neutral), or 1 (agree)
 * Output: results.json (party scores) + screenshot.png
 */

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const WAHLOMAT_URL = 'https://www.wahl-o-mat.de/bundestagswahl2025/app/main_app.html';
const PLAYWRIGHT_DEPS = '/paperclip/.playwright-deps';

// All 28 parties in order (index matches cb_parteien_N)
const PARTY_NAMES = [
  'SPD', 'CDU / CSU', 'GRÜNE', 'FDP', 'AfD', 'Die Linke', 'SSW',
  'FREIE WÄHLER', 'Tierschutzpartei', 'dieBasis', 'Die PARTEI',
  'Die Gerechtigkeitspartei - Team Todenhöfer', 'PIRATEN', 'Volt', 'ÖDP',
  'Verjüngungsforschung', 'PdH', 'Bündnis C', 'BP', 'MLPD',
  'MENSCHLICHE WELT', 'PdF', 'SGP', 'BüSo', 'BÜNDNIS DEUTSCHLAND',
  'BSW', 'MERA25', 'WerteUnion'
];

// Parse args
const args = process.argv.slice(2);
const getArg = (flag) => {
  const idx = args.indexOf(flag);
  return idx !== -1 ? args[idx + 1] : null;
};

const answersFile = getArg('--answers');
const outDir = getArg('--out');

if (!answersFile || !outDir) {
  console.error('Usage: node wahlomat_runner.js --answers <file> --out <dir>');
  process.exit(1);
}

const answers = JSON.parse(fs.readFileSync(answersFile, 'utf8'));
if (!Array.isArray(answers) || answers.length !== 38) {
  console.error('answers.json must be an array of 38 values (-1, 0, or 1)');
  process.exit(1);
}

fs.mkdirSync(outDir, { recursive: true });

// Set LD_LIBRARY_PATH for missing system libs
process.env.LD_LIBRARY_PATH = `${PLAYWRIGHT_DEPS}:${process.env.LD_LIBRARY_PATH || ''}`;

async function parseResults(page) {
  const text = await page.locator('body').textContent();
  const results = [];

  // Extract "Ergebnis von Partei NAME (XX,X %)" patterns
  const re = /Ergebnis von Partei\s+(.+?)\s+\((\d+(?:[,.]\d+)?)\s*%\)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const name = m[1].trim();
    const pct = parseFloat(m[2].replace(',', '.'));
    results.push({ party: name, score_pct: pct });
  }

  // Sort by score descending
  results.sort((a, b) => b.score_pct - a.score_pct);
  return results;
}

async function selectPartiesBatch(page, indices) {
  const labels = await page.locator('.party-selection__list-item .party-selection__label').all();
  for (const i of indices) {
    if (i < labels.length) {
      await labels[i].click();
      await page.waitForTimeout(150);
    }
  }
}

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const allResults = {};

  // Run in batches of 8 to get all 28 parties
  const BATCH_SIZE = 8;
  const batches = [];
  for (let i = 0; i < PARTY_NAMES.length; i += BATCH_SIZE) {
    batches.push(Array.from({ length: Math.min(BATCH_SIZE, PARTY_NAMES.length - i) }, (_, j) => i + j));
  }

  for (let batchIdx = 0; batchIdx < batches.length; batchIdx++) {
    const batch = batches[batchIdx];
    console.log(`\nBatch ${batchIdx + 1}/${batches.length}: parties ${batch.map(i => PARTY_NAMES[i]).join(', ')}`);

    const page = await browser.newPage();

    try {
      await page.goto(WAHLOMAT_URL, { waitUntil: 'networkidle', timeout: 30000 });
      console.log('  Page loaded');

      // Step 1: Click Start
      await page.locator('button.button--big:has-text("Start")').click();
      await page.waitForTimeout(1500);
      console.log('  Clicked Start');

      // Step 2: Answer all 38 theses
      for (let i = 0; i < 38; i++) {
        await page.evaluate(({ idx, choice }) => {
          wom_change_position(idx, choice);
        }, { idx: i, choice: answers[i] });
        await page.waitForTimeout(100);
      }
      console.log('  Answered 38 theses');

      // Step 3: Skip weighting, go to party selection
      await page.waitForTimeout(1000);
      await page.locator('button.btn--paging:has-text("weiter zur Auswahl")').click();
      await page.waitForTimeout(2000);
      console.log('  Navigated to party selection');

      // Step 4: Select this batch of parties
      await selectPartiesBatch(page, batch);
      const selected = await page.evaluate(() =>
        document.querySelectorAll('.party-selection__list-item.is-selected').length
      );
      console.log(`  Selected ${selected} parties`);

      // Step 5: Navigate to results
      await page.locator('button.wom_next').click();
      await page.waitForTimeout(3000);
      console.log('  Navigated to results');

      // Step 6: Parse results
      const batchResults = await parseResults(page);
      console.log('  Results:', batchResults.map(r => `${r.party}: ${r.score_pct}%`).join(', '));

      for (const r of batchResults) {
        allResults[r.party] = r.score_pct;
      }

      // Screenshot for this batch
      await page.screenshot({
        path: path.join(outDir, `results_batch${batchIdx + 1}.png`),
        fullPage: false
      });

    } catch (err) {
      console.error(`  Error in batch ${batchIdx + 1}:`, err.message);
    } finally {
      await page.close();
    }
  }

  await browser.close();

  // Write combined results
  const sortedResults = Object.entries(allResults)
    .map(([party, score_pct]) => ({ party, score_pct }))
    .sort((a, b) => b.score_pct - a.score_pct);

  const outputData = {
    timestamp: new Date().toISOString(),
    answers_file: answersFile,
    party_count: sortedResults.length,
    results: sortedResults
  };

  const outFile = path.join(outDir, 'results.json');
  fs.writeFileSync(outFile, JSON.stringify(outputData, null, 2));
  console.log(`\nResults written to ${outFile}`);
  console.log('\nTop 5:');
  sortedResults.slice(0, 5).forEach((r, i) => {
    console.log(`  ${i + 1}. ${r.party}: ${r.score_pct}%`);
  });
})();
