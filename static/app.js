const form = document.querySelector('#chat-form');
const input = document.querySelector('#prompt');
const messagesEl = document.querySelector('#messages');
const welcome = document.querySelector('#welcome');
const sendButton = document.querySelector('#send-button');
const imageButton = document.querySelector('#generate-image');
const modelLabel = document.querySelector('#model-label');
const webSearch = document.querySelector('#web-search');
const welcomeMascot = document.querySelector('#welcome-mascot');
const mascotFrames = [1, 2, 3, 4].map((frame) => `/static/mascot-${String(frame).padStart(2, '0')}.webp`);
const dots = [document.querySelector('#top-dot'), document.querySelector('#sidebar-dot')];
let history = [];
let activeSpeechButton = null;
let pollinationsReady = false;

if (welcomeMascot && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  let mascotFrame = 0;
  window.setInterval(() => {
    if (welcome.hidden) return;
    mascotFrame = (mascotFrame + 1) % mascotFrames.length;
    welcomeMascot.src = mascotFrames[mascotFrame];
  }, 1150);
}

function setConnection(connected, ready, model) {
  dots.forEach((dot) => dot.classList.toggle('online', connected && ready));
  dots.forEach((dot) => dot.classList.toggle('offline', !connected || !ready));
  modelLabel.textContent = !connected
    ? 'Ollama no está disponible'
    : ready ? `Modelo local: ${model}` : `Falta descargar ${model}`;
}

async function checkStatus() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    setConnection(data.connected, data.model_ready, data.model);
    pollinationsReady = Boolean(data.image_ready);
    imageButton.disabled = !pollinationsReady;
    imageButton.title = pollinationsReady
      ? 'Generación gratuita con Pollinations; el prompt se envía a ese servicio y puede tener límites de uso.'
      : 'La generación de imágenes no está disponible en este momento.';
  } catch {
    setConnection(false, false, 'Ollama');
    pollinationsReady = true;
    imageButton.disabled = false;
  }
}

function addMessage(role, text) {
  const row = document.createElement('div');
  row.className = `message ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? '◉' : '✳';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  const body = document.createElement('div');
  body.className = 'message-body';
  body.append(bubble);
  row.append(avatar, body);
  messagesEl.append(row);
  row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  return { row, body };
}

function showError(text) {
  const { row } = addMessage('assistant', text);
  row.classList.add('error-message');
}

function addReadButton(messageBody, text) {
  const button = document.createElement('button');
  button.className = 'read-button';
  button.type = 'button';
  button.textContent = '▶ Leer respuesta';
  button.addEventListener('click', () => {
    if (!('speechSynthesis' in window)) {
      button.textContent = 'Lectura no disponible en este navegador';
      return;
    }
    if (window.speechSynthesis.speaking && activeSpeechButton === button) {
      window.speechSynthesis.cancel();
      button.textContent = '▶ Leer respuesta';
      activeSpeechButton = null;
      return;
    }
    window.speechSynthesis.cancel();
    if (activeSpeechButton) activeSpeechButton.textContent = '▶ Leer respuesta';
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'es-CO';
    utterance.rate = 0.96;
    const spanishVoice = window.speechSynthesis.getVoices().find((voice) =>
      /^es(-CO|-MX|-ES)?$/i.test(voice.lang),
    );
    if (spanishVoice) utterance.voice = spanishVoice;
    activeSpeechButton = button;
    button.textContent = '■ Detener lectura';
    utterance.onend = utterance.onerror = () => {
      button.textContent = '▶ Leer respuesta';
      if (activeSpeechButton === button) activeSpeechButton = null;
    };
    window.speechSynthesis.speak(utterance);
  });
  messageBody.append(button);
}

async function addRelatedImage(messageBody, question, answer) {
  const card = document.createElement('section');
  card.className = 'related-image related-images';
  card.setAttribute('aria-label', 'Imágenes relacionadas');
  card.textContent = 'Buscando imágenes relacionadas…';
  messageBody.append(card);
  try {
    const endpoint = new URL('https://api.openverse.org/v1/images/');
    endpoint.searchParams.set('q', question.trim().slice(0, 200));
    endpoint.searchParams.set('page_size', '12');
    endpoint.searchParams.set('mature', 'false');
    const response = await fetch(endpoint);
    if (!response.ok) throw new Error('El catálogo de imágenes no respondió.');
    const data = await response.json();
    const images = (data.results || []).filter((item) =>
      (item.thumbnail || item.url) && (item.foreign_landing_url || item.detail_url),
    ).slice(0, 4);
    if (!images.length) throw new Error('No encontré imágenes para esta búsqueda.');

    card.replaceChildren();
    const heading = document.createElement('div');
    heading.className = 'image-heading';
    heading.textContent = 'Imágenes relacionadas';
    const grid = document.createElement('div');
    grid.className = 'related-images-grid';
    images.forEach((item) => {
      const figure = document.createElement('figure');
      figure.className = 'related-image-item';
      const link = document.createElement('a');
      link.href = item.foreign_landing_url || item.detail_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      const preview = document.createElement('img');
      preview.src = item.thumbnail || item.url;
      preview.alt = item.title || question;
      preview.loading = 'lazy';
      preview.referrerPolicy = 'no-referrer';
      link.append(preview);
      const caption = document.createElement('figcaption');
      const details = [item.title || 'Imagen relacionada', item.creator, item.license].filter(Boolean);
      caption.textContent = details.join(' · ');
      figure.append(link, caption);
      grid.append(figure);
    });
    card.append(heading, grid);
  } catch (error) {
    card.textContent = `${error.message || 'No se pudieron cargar imágenes relacionadas.'} Revisa tu conexión e inténtalo otra vez.`;
    card.classList.add('image-unavailable');
  }
}

function addSources(messageBody, sources, searchEnabled) {
  if (!searchEnabled) return;
  if (!sources.length) {
    const note = document.createElement('div');
    note.className = 'search-note';
    note.textContent = 'No se pudieron obtener fuentes web. La respuesta se generó con el modelo local.';
    messageBody.append(note);
    return;
  }
  const list = document.createElement('div');
  list.className = 'source-list';
  const heading = document.createElement('strong');
  heading.className = 'source-heading';
  heading.textContent = 'Fuentes consultadas';
  list.append(heading);
  sources.forEach((source, index) => {
    const link = document.createElement('a');
    link.href = source.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = `[${index + 1}] ${source.title}`;
    list.append(link);
  });
  messageBody.append(list);
}

async function createImage(requestedPrompt = '') {
  const prompt = (requestedPrompt || input.value).trim();
  if (!prompt || imageButton.disabled) return;
  welcome.hidden = true;
  addMessage('user', `🎨 Crear imagen: ${prompt}`);
  input.value = '';
  input.style.height = 'auto';
  imageButton.disabled = true;
  sendButton.disabled = true;
  const { body } = addMessage('assistant', '');
  const card = document.createElement('div');
  card.className = 'generated-image';
  const heading = document.createElement('div');
  heading.className = 'image-heading';
  heading.textContent = 'Creando imagen con Pollinations…';
  const preview = document.createElement('img');
  preview.alt = prompt;
  const imageUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?model=flux&width=1024&height=1024&nologo=true&private=true&safe=true`;
  const openImage = document.createElement('a');
  openImage.href = imageUrl;
  openImage.target = '_blank';
  openImage.rel = 'noopener noreferrer';
  openImage.textContent = 'Abrir imagen para guardarla';
  preview.addEventListener('load', () => {
    heading.textContent = 'Imagen generada con Pollinations';
    clearTimeout(imageTimeout);
    imageButton.disabled = !pollinationsReady;
  }, { once: true });
  preview.addEventListener('error', () => {
    heading.textContent = 'Pollinations no pudo generar la imagen. Comprueba tu conexión o inténtalo más tarde.';
    card.classList.add('image-unavailable');
    preview.remove();
    openImage.remove();
    clearTimeout(imageTimeout);
    imageButton.disabled = !pollinationsReady;
  }, { once: true });
  imageButton.disabled = true;
  const imageTimeout = setTimeout(() => {
    if (!preview.complete) {
      heading.textContent = 'Pollinations está tardando. Intenta nuevamente en un momento.';
      card.classList.add('image-unavailable');
      preview.remove();
      openImage.remove();
      imageButton.disabled = !pollinationsReady;
    }
  }, 180000);
  card.append(heading, preview, openImage);
  body.append(card);
  try {
    preview.src = imageUrl;
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
}

async function sendMessage(text) {
  const prompt = text.trim();
  if (!prompt || sendButton.disabled) return;
  if (isImageRequest(prompt)) {
    await createImage(prompt);
    return;
  }
  welcome.hidden = true;
  addMessage('user', prompt);
  history.push({ role: 'user', content: prompt });
  input.value = '';
  input.style.height = 'auto';
  sendButton.disabled = true;
  const searchEnabled = webSearch.checked;
  const thinking = document.createElement('div');
  thinking.className = 'typing';
  thinking.textContent = searchEnabled ? 'Buscando fuentes e imágenes y preparando respuesta…' : 'La IA está pensando…';
  messagesEl.append(thinking);
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history, search_web: searchEnabled }),
    });
    const data = await response.json();
    thinking.remove();
    if (!response.ok) throw new Error(data.detail || 'No se pudo generar la respuesta.');
    history.push({ role: 'assistant', content: data.answer });
    const { body } = addMessage('assistant', data.answer);
    addReadButton(body, data.answer);
    addSources(body, data.sources || [], searchEnabled);
    if (searchEnabled) addRelatedImage(body, prompt, data.answer);
  } catch (error) {
    thinking.remove();
    history.pop();
    showError(error.message || 'No se pudo conectar con la IA local.');
    checkStatus();
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
}

function isImageRequest(text) {
  const asksForImage = /\b(genera(?:r|s)?|crea(?:r|s)?|haz(?:me)?|hacer|dibuja(?:r|s)?|ilustra(?:r|s)?|pinta(?:r|s)?|produce|producir|dame|muestra|quiero|necesito|puedes|generate|create|draw)\b/i.test(text);
  const namesImage = /\b(imagen(?:es)?|foto(?:graf[ií]a)?s?|ilustraci[oó]n|dibujo|arte digital|p[oó]ster|logo)\b/i.test(text);
  const asksForExplanation = /\b(c[oó]mo|qu[eé] es|qu[eé] significa|expl[ií]ca|ens[eé]ñame|aprende|tutorial)\b/i.test(text);
  return asksForImage && namesImage && !asksForExplanation;
}

function resetChat() {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  activeSpeechButton = null;
  history = [];
  messagesEl.replaceChildren();
  welcome.hidden = false;
  input.value = '';
  input.focus();
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  sendMessage(input.value);
});
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
});
document.querySelector('#new-chat').addEventListener('click', resetChat);
document.querySelector('#clear-chat').addEventListener('click', resetChat);
imageButton.addEventListener('click', createImage);
document.querySelectorAll('.suggestion').forEach((button) => {
  button.addEventListener('click', () => sendMessage(button.dataset.prompt || ''));
});
checkStatus();
