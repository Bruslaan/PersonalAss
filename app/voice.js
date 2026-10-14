// Browser speech recognition; injectable dependencies keep microphone tests offline.
export function isStop(text) {
  const words = text.toLocaleLowerCase('de-DE').replace(/[.!?,;:]/g, '').trim().replace(/\s+/g, ' ');
  return /^(?:bitte )?(?:stopp|stop|abbrechen)(?: bitte)?$/.test(words);
}

export class VoiceControl {
  constructor({Recognition, onCommand, onStop, onStatus, onTranscript,
               setTimer = setTimeout, clearTimer = clearTimeout}) {
    Object.assign(this, {Recognition, onCommand, onStop, onStatus, onTranscript, setTimer, clearTimer});
    this.enabled = false;
    this.recognition = null;
    this.pending = '';
    this.timer = null;
    this.restartTimer = null;
  }
  cancelDraft() {
    this.clearTimer(this.timer);
    this.timer = null;
    this.pending = '';
  }
  disable(message = 'Mikrofon aus.') {
    this.enabled = false;
    this.cancelDraft();
    this.clearTimer(this.restartTimer);
    const recognition = this.recognition;
    this.recognition = null;
    recognition?.abort();
    this.onStatus(message, false);
  }
  enable() {
    if (this.enabled) return;
    if (!this.Recognition) {
      this.onStatus('Dieser Browser unterstützt keine Spracherkennung. Bitte einen unterstützten Browser verwenden oder Text eingeben.', false);
      return;
    }
    this.enabled = true;
    this.listen();
  }
  schedule() {
    this.clearTimer(this.timer);
    if (!this.pending) return;
    this.timer = this.setTimer(() => {
      if (!this.enabled) return;
      const text = this.pending.trim();
      this.pending = '';
      this.timer = null;
      if (text) this.onCommand(text);
    }, 1400);
  }
  listen() {
    if (!this.enabled) return;
    const recognition = new this.Recognition();
    this.recognition = recognition;
    recognition.lang = 'de-DE';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    const finalIndexes = new Set(), stoppedIndexes = new Set();
    const current = () => this.enabled && this.recognition === recognition;
    recognition.onstart = () => { if (current()) this.onStatus('Mikrofon aktiv – sprich deinen Auftrag. „Stopp“ unterbricht.', true); };
    recognition.onspeechstart = () => { if (current()) this.clearTimer(this.timer); };
    recognition.onspeechend = () => { if (current()) this.schedule(); };
    recognition.onresult = event => {
      if (!current()) return;
      const partial = [];
      for (let index = event.resultIndex; index < event.results.length; index++) {
        const result = event.results[index], text = result[0].transcript.trim();
        if (finalIndexes.has(index)) continue;
        // Stop on an interim recognition too: don't wait for final punctuation/silence.
        if (isStop(text)) {
          if (!stoppedIndexes.has(index)) {
            stoppedIndexes.add(index);
            this.cancelDraft();
            this.onTranscript(text);
            this.onStop();
          }
          if (result.isFinal) finalIndexes.add(index);
          continue;
        }
        if (stoppedIndexes.has(index)) {
          if (result.isFinal) finalIndexes.add(index);
          continue;
        }
        if (result.isFinal) {
          finalIndexes.add(index);
          this.pending = [this.pending, text].filter(Boolean).join(' ');
          this.schedule();
        } else {
          partial.push(text);
          this.clearTimer(this.timer);
        }
      }
      this.onTranscript([this.pending, ...partial].filter(Boolean).join(' '));
    };
    recognition.onerror = event => {
      if (!current()) return;
      if (event.error === 'no-speech') return;
      const messages = {
        'not-allowed': 'Mikrofonzugriff abgelehnt. Bitte in den Browser-/Systemeinstellungen erlauben und erneut einschalten.',
        'service-not-allowed': 'Spracherkennungsdienst nicht verfügbar oder nicht erlaubt.',
        'audio-capture': 'Kein nutzbares Mikrofon gefunden. Bitte Mikrofon und Systemeinstellungen prüfen.',
        'network': 'Spracherkennung hat einen Netzwerkfehler. Bitte Mikrofon erneut einschalten.',
        'language-not-supported': 'Deutsche Spracherkennung ist in diesem Browser nicht verfügbar.'
      };
      this.disable(messages[event.error] || 'Spracherkennung beendet: ' + event.error + '. Bitte erneut einschalten.');
    };
    recognition.onend = () => {
      if (!current()) return;
      this.recognition = null;
      this.onStatus('Mikrofon verbindet erneut … „Stopp“ ist währenddessen nicht verfügbar.', true);
      this.restartTimer = this.setTimer(() => this.listen(), 350);
    };
    this.onStatus('Mikrofon wird eingeschaltet …', true);
    try { recognition.start(); }
    catch { this.disable('Spracherkennung konnte nicht starten. Bitte erneut einschalten.'); }
  }
}

// Order mutations so a stop following a slow start cannot arrive before that start.
// A version cancels queued commands when a newer voice command or stop replaces them.
export class CommandQueue {
  constructor({post, getModel, onError, onSent}) {
    Object.assign(this, {post, getModel, onError, onSent});
    this.tail = Promise.resolve();
    this.version = 0;
    this.pending = 0;
  }
  enqueue(operation) {
    this.pending++;
    const request = this.tail.then(operation).catch(error => this.onError(error));
    this.tail = request.finally(() => { this.pending--; });
    return this.tail;
  }
  command(text, replace = false) {
    const version = ++this.version, model = this.getModel();
    return this.enqueue(async () => {
      if (version !== this.version) return;
      if (replace) await this.post('/api/stop', {});
      if (version !== this.version) return;
      await this.post('/api/start', {task: text, model});
      this.onSent(text);
    });
  }
  stop() {
    ++this.version;
    return this.enqueue(() => this.post('/api/stop', {}));
  }
  reset() {
    ++this.version;
    return this.enqueue(() => this.post('/api/reset', {}));
  }
}
