import assert from 'node:assert/strict';
import { readFile, access } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import ts from 'typescript';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = await readFile(resolve(root, 'src/lib/traits.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { TRAITS, primaryPersonaFromTraits } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('existing saved selection IDs and backend persona mappings remain compatible', () => {
  assert.deepEqual(Object.fromEntries(TRAITS.map(t => [t.id, t.mapsTo])), {
    cheerful: 'witty_friend', friendly: 'witty_friend', immersive: 'hype_commentator',
    calm: 'dry_comic', playful: 'witty_friend', supportive: 'warm_supporter',
  });
  const valid = ['witty_friend', 'hype_commentator', 'dry_comic', 'warm_supporter'];
  assert.equal(primaryPersonaFromTraits(['supportive', 'cheerful'], valid), 'warm_supporter');
  assert.equal(primaryPersonaFromTraits(['supportive', 'cheerful', 'friendly'], valid), 'witty_friend');
  assert.equal(primaryPersonaFromTraits(['calm'], ['witty_friend']), null);
  assert.equal(primaryPersonaFromTraits(['unknown'], valid), null);
});

test('all six persona cards resolve to bundled desktop artwork', async () => {
  assert.equal(new Set(TRAITS.map(t => t.image)).size, 6);
  await Promise.all(TRAITS.map(t => access(resolve(root, 'public', t.image.slice(1)))));
});

test('favicon uses the same speech-bubble outline as the app header', async () => {
  const header = await readFile(resolve(root, 'public/brand/app-header.svg'), 'utf8');
  const icon = await readFile(resolve(root, 'public/favicon.svg'), 'utf8');
  const firstPath = svg => svg.match(/<path\b[^>]*\bd="([^"]+)"/)[1];
  assert.equal(firstPath(header), firstPath(icon));
  const html = await readFile(resolve(root, 'index.html'), 'utf8');
  assert.match(html, /rel="icon" type="image\/svg\+xml" href="\/favicon.svg"/);
  await Promise.all(['favicon-32.png', 'apple-touch-icon.png', 'favicon.ico', 'brand/generate-face.svg'].map(name => access(resolve(root, 'public', name))));
});
