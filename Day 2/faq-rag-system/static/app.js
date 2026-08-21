const form = document.querySelector('#askForm');
const input = document.querySelector('#question');
const sendButton = document.querySelector('#sendButton');
const conversation = document.querySelector('#conversation');
const suggestions = document.querySelector('#suggestions');

function addMessage(text, role, sources = []) {
  const item = document.createElement('div');
  item.className = `message ${role}-message`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  const content = document.createElement('p');
  content.textContent = text;
  if (role === 'assistant') {
    const avatar = document.createElement('div');
    avatar.className = 'avatar'; avatar.textContent = 'A';
    const speaker = document.createElement('p');
    speaker.className = 'speaker'; speaker.textContent = 'ATLAS';
    bubble.append(speaker, content); item.append(avatar, bubble);
  } else { bubble.append(content); item.append(bubble); }
  if (sources.length) {
    const sourceList = document.createElement('div'); sourceList.className = 'sources';
    sources.forEach(({title}) => { const tag = document.createElement('span'); tag.className = 'source'; tag.textContent = title; sourceList.append(tag); });
    bubble.append(sourceList);
  }
  conversation.append(item); conversation.scrollTop = conversation.scrollHeight;
  return item;
}

function addTyping() {
  const item = addMessage('', 'assistant');
  item.querySelector('.bubble').insertAdjacentHTML('beforeend', '<div class="typing"><i></i><i></i><i></i></div>');
  return item;
}

async function ask(question) {
  addMessage(question, 'user'); input.value = ''; resize();
  suggestions.hidden = true; sendButton.disabled = true;
  const typing = addTyping();
  try {
    const response = await fetch('/api/ask', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question}) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Something went wrong.');
    typing.remove(); addMessage(data.answer, 'assistant', data.sources);
  } catch (error) {
    typing.remove(); const item = addMessage(error.message, 'assistant'); item.querySelector('.bubble').classList.add('error');
  } finally { sendButton.disabled = false; input.focus(); }
}

form.addEventListener('submit', event => { event.preventDefault(); const value = input.value.trim(); if (value) ask(value); });
input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
input.addEventListener('input', resize);
suggestions.addEventListener('click', event => { if (event.target.matches('button')) ask(event.target.textContent); });
function resize() { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 120)}px`; }

fetch('/api/status').then(r => r.json()).then(data => {
  const status = document.querySelector('.status');
  document.querySelector('#statusText').textContent = data.message;
  if (data.ready) status.classList.add('ready');
}).catch(() => { document.querySelector('#statusText').textContent = 'Service unavailable'; });

