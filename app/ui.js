import {VoiceControl, CommandQueue} from './voice.js';
const find = id => document.getElementById(id);
const start = find('start'), stop = find('stop'), reset = find('reset'), model = find('model');
const status = find('status'), setup = find('setup'), history = find('history'), task = find('task');
const mic = find('mic'), voiceStatus = find('voice-status'), transcript = find('transcript');
let modelsLoaded = false, historyJSON = '', state = null, refreshing = false;

function renderHistory(turns) {
  const value = JSON.stringify(turns);
  if (value === historyJSON) return;
  historyJSON = value;
  history.replaceChildren();
  for (const turn of turns) {
    const user = document.createElement('p'), label = document.createElement('strong');
    label.textContent = 'Du: ';
    user.append(label, document.createTextNode(turn.task));
    const answer = document.createElement('pre');
    answer.textContent = turn.result || (turn.state === 'running' ? 'Auftrag läuft …' : 'Auftrag unterbrochen.');
    history.append(user, answer);
  }
}
function controls() {
  const busy = state?.state === 'running' || queue.pending > 0;
  start.disabled = !state || busy || !state.key_configured || !state.browser_connected;
  stop.disabled = !state || !busy;
  reset.disabled = busy || !state;
  model.disabled = busy || !modelsLoaded;
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const response = await fetch('/api/status', {cache: 'no-store'});
    if (!response.ok) throw Error('Status nicht erreichbar');
    state = await response.json();
    if (!modelsLoaded) {
      for (const item of state.models) {
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = item.label;
        model.append(option);
      }
      model.value = state.default_model;
      modelsLoaded = true;
    }
    controls();
    status.textContent = state.message + (state.step ? ' · Schritt ' + state.step : '');
    setup.textContent = !state.key_configured ? 'API-Schlüssel fehlt: In Railway → PersonalAss → Variables → OPENAI_API_KEY hinterlegen und deployen.' : 'Modell: ' + state.model + (state.browser_connected ? ' · Browser verbunden' : ' · Browser startet');
    renderHistory(state.turns || []);
  } catch (error) {
    state = null;
    status.textContent = error.message;
    controls();
  } finally { refreshing = false; }
}
async function post(path, data) {
  const response = await fetch(path, {method: 'POST', headers: {
    'Content-Type': 'application/json', 'X-Cloud-Browser': '1'
  }, body: JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Anfrage fehlgeschlagen');
  state = result;
  status.textContent = result.message;
  renderHistory(result.turns || []);
  return result;
}
const queue = new CommandQueue({post, getModel: () => model.value,
  onError: error => { status.textContent = error.message; voiceStatus.textContent = 'Auftrag nicht gesendet/gestoppt: ' + error.message; },
  onSent: text => { if (task.value.trim() === text) task.value = ''; }
});
function track(promise) {
  controls();
  promise.finally(() => { controls(); refresh(); });
}
function submit(text, replace = false) {
  text = text.trim();
  if (!text || text.length > 2000) {
    voiceStatus.textContent = 'Bitte einen Auftrag mit 1 bis 2000 Zeichen sprechen oder eingeben.';
    return;
  }
  task.value = text;
  if (!state?.key_configured || !state.browser_connected || !modelsLoaded) {
    voiceStatus.textContent = 'Auftrag steht im Textfeld. API-Schlüssel und Browserverbindung prüfen, dann erneut senden.';
    return;
  }
  status.textContent = replace ? 'Laufender Auftrag wird ersetzt …' : 'Auftrag wird gesendet …';
  track(queue.command(text, replace));
}
function interrupt() {
  voice.cancelDraft();
  transcript.textContent = 'Stopp';
  status.textContent = 'Stopp wird an den Cloud-Assistenten gesendet …';
  track(queue.stop());
}
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const voice = new VoiceControl({Recognition,
  onCommand: text => submit(text, state?.state === 'running' || queue.pending > 0),
  onStop: interrupt,
  onStatus: (message, active) => {
    voiceStatus.textContent = message;
    mic.textContent = active ? 'Mikrofon ausschalten' : 'Mikrofon einschalten';
    mic.setAttribute('aria-pressed', String(active));
  },
  onTranscript: text => { transcript.textContent = text; }
});
if (!Recognition || !window.isSecureContext) {
  mic.disabled = true;
  voiceStatus.textContent = !window.isSecureContext ? 'Mikrofon benötigt HTTPS oder localhost.' : 'Spracherkennung ist in diesem Browser nicht verfügbar. Texteingabe bleibt möglich.';
}
mic.onclick = () => voice.enabled ? voice.disable() : voice.enable();
start.onclick = () => submit(task.value);
stop.onclick = interrupt;
reset.onclick = () => { voice.cancelDraft(); track(queue.reset()); };
window.addEventListener('pagehide', () => voice.disable());
refresh();
setInterval(refresh, 2000);

const liveToggle = find('live-toggle'), liveFrame = find('live-frame');
liveToggle.onclick = () => {
  const open = liveFrame.hidden;
  liveFrame.hidden = !open;
  liveToggle.setAttribute('aria-expanded', String(open));
  liveToggle.textContent = open ? 'Liveansicht ausblenden' : 'Liveansicht hier anzeigen';
  if (open) liveFrame.src = '/vnc.html?autoconnect=true&resize=scale&path=websockify';
  else liveFrame.removeAttribute('src');
};
