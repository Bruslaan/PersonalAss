import test from 'node:test';
import assert from 'node:assert/strict';
import {VoiceControl, CommandQueue, isStop} from '../app/voice.js';

class Recognition {
  static instances = [];
  constructor() { Recognition.instances.push(this); }
  start() { this.onstart?.(); }
  abort() { this.onend?.(); }
}
function fixture() {
  const commands = [], stops = [], messages = [], timers = new Map();
  let next = 0;
  const control = new VoiceControl({Recognition, onCommand: text => commands.push(text),
    onStop: () => stops.push('stop'), onStatus: (message, active) => messages.push({message, active}),
    onTranscript: () => {}, setTimer: (fn, ms) => { timers.set(++next, {fn, ms}); return next; },
    clearTimer: id => timers.delete(id)});
  const fire = ms => {
    for (const [id, timer] of [...timers]) if (timer.ms === ms) { timers.delete(id); timer.fn(); }
  };
  const result = (entries, resultIndex = 0) => {
    const results = entries.map(([text, final]) => Object.assign([{transcript: text}], {isFinal: final}));
    control.recognition.onresult({results, resultIndex});
  };
  return {control, commands, stops, messages, fire, result};
}

test('only exact stop phrases interrupt, not quoted/embedded search words', () => {
  for (const text of ['Stopp!', 'stop', 'Bitte stopp.', 'Abbrechen bitte']) assert.ok(isStop(text));
  for (const text of ['Suche eine Stop-Motion-Kamera', 'Ist ein Stopp nötig?', 'nicht stoppen']) assert.equal(isStop(text), false);
});
test('final utterance sent once after pause, interim does not send', () => {
  const f = fixture(); f.control.enable();
  f.result([['Suche eine Kamera', false]]); f.fire(1400);
  assert.deepEqual(f.commands, []);
  f.result([['Suche eine Kamera', true]]);
  f.result([['Suche eine Kamera', true]]);
  f.fire(1400);
  assert.deepEqual(f.commands, ['Suche eine Kamera']);
});
test('separate final fragments form one instruction; continuing speech delays send', () => {
  const f = fixture(); f.control.enable();
  f.result([['Suche eine Kamera', true]]);
  f.control.recognition.onspeechstart(); f.fire(1400);
  assert.deepEqual(f.commands, []);
  f.result([['Suche eine Kamera', true], ['bis 300 Euro', true]], 1);
  f.fire(1400);
  assert.deepEqual(f.commands, ['Suche eine Kamera bis 300 Euro']);
});
test('interim stop cancels unsent draft, final stop is not sent as task or repeated', () => {
  const f = fixture(); f.control.enable();
  f.result([['Suche eine Kamera', true]]);
  f.result([['Suche eine Kamera', true], ['Stopp', false]], 1);
  assert.deepEqual(f.stops, ['stop']);
  f.result([['Suche eine Kamera', true], ['Stopp!', true]], 1);
  f.fire(1400);
  assert.deepEqual(f.stops, ['stop']); assert.deepEqual(f.commands, []);
});
test('microphone off discards pending speech and ignores late recognition events', () => {
  const f = fixture(); f.control.enable();
  const recognition = f.control.recognition;
  f.result([['Suche eine Kamera', true]]);
  f.control.disable(); f.fire(1400); f.fire(350);
  recognition.onresult({resultIndex: 0, results: [Object.assign([{transcript:'Stopp'}], {isFinal:true})]});
  assert.deepEqual(f.commands, []); assert.deepEqual(f.stops, []);
  assert.equal(f.control.enabled, false);
});
test('recognition resumes after normal end and detects stop in the new session', () => {
  const f = fixture(); f.control.enable();
  f.control.recognition.onend(); f.fire(350);
  f.result([['Stopp', true]]);
  assert.deepEqual(f.stops, ['stop']);
});
test('denied microphone disables recognition without restart loop', () => {
  const f = fixture(); f.control.enable();
  f.control.recognition.onerror({error:'not-allowed'}); f.fire(350);
  assert.equal(f.control.enabled, false);
  assert.match(f.messages.at(-1).message, /abgelehnt/);
});
test('unsupported browser reports failure instead of pretending to listen', () => {
  const f = fixture(); f.control.Recognition = undefined; f.control.enable();
  assert.equal(f.control.enabled, false); assert.match(f.messages.at(-1).message, /unterstützt keine/);
});
test('stop is sent after a slow pending start; no late start can escape stop', async () => {
  const calls = [], errors = [];
  let release, began;
  const started = new Promise(resolve => began = resolve);
  const gate = new Promise(resolve => release = resolve);
  const queue = new CommandQueue({getModel: () => 'gpt-6.1-sol', onSent: () => {}, onError: e => errors.push(e),
    post: async path => { calls.push(path); if (path === '/api/start') { began(); await gate; } }});
  queue.command('Suche Kamera');
  await started;
  const stopped = queue.stop();
  release(); await stopped;
  assert.deepEqual(calls, ['/api/start', '/api/stop']); assert.equal(queue.pending, 0); assert.deepEqual(errors, []);
});
test('stop invalidates queued tasks; replacement stops first then sends selected model', async () => {
  const calls = [], errors = [];
  const queue = new CommandQueue({getModel: () => 'gpt-6.1-sol', onSent: () => {}, onError: e => errors.push(e),
    post: async (path, data) => calls.push({path, data})});
  queue.command('Alter Auftrag'); await queue.stop();
  assert.deepEqual(calls.map(call => call.path), ['/api/stop']);
  await queue.command('Dieses Angebot öffnen', true);
  assert.deepEqual(calls.slice(1).map(call => call.path), ['/api/stop', '/api/start']);
  assert.equal(calls.at(-1).data.model, 'gpt-6.1-sol'); assert.deepEqual(errors, []);
});
test('failed stop prevents a replacement start and reports error', async () => {
  const calls = [], errors = [];
  const queue = new CommandQueue({getModel: () => 'gpt-6.1-sol', onSent: () => {}, onError: e => errors.push(e),
    post: async path => { calls.push(path); throw Error('offline'); }});
  await queue.command('Neuer Auftrag', true);
  assert.deepEqual(calls, ['/api/stop']); assert.match(errors[0].message, /offline/);
});
