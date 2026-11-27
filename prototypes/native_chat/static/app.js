const state = {
  personas: [],
  models: [],
  personaId: null,
  modelId: null,
  queue: Promise.resolve(),
};

const $ = (selector) => document.querySelector(selector);
const timeline = $('#timeline');
const input = $('#message-input');

function escapeText(node, text) {
  node.textContent = text == null ? '' : String(text);
  return node;
}

function timeLabel(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function bubbleRow(text, role) {
  const row = document.createElement('div');
  row.className = `row ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  escapeText(bubble, text);
  row.appendChild(bubble);
  return row;
}

function metaRow(text, role) {
  const meta = document.createElement('div');
  meta.className = `meta ${role}`;
  escapeText(meta, text);
  return meta;
}

function scrollBottom() {
  timeline.scrollTop = timeline.scrollHeight;
}

function appendUser(text, at = new Date().toISOString()) {
  timeline.appendChild(bubbleRow(text, 'user'));
  timeline.appendChild(metaRow(`${timeLabel(at)} 已送达`, 'user'));
  scrollBottom();
}

function snapshotSession() {
  return {
    personaId: state.personaId,
    modelId: state.modelId,
    includeContext: $('#context-toggle').checked,
  };
}

function sessionMatches(session) {
  return state.personaId === session.personaId && state.modelId === session.modelId;
}

async function appendAssistantBubbles(bubbles, label, at, session) {
  if (!sessionMatches(session)) return;
  const typing = document.createElement('div');
  typing.className = 'typing';
  typing.textContent = '正在输入…';
  timeline.appendChild(typing);
  scrollBottom();
  await new Promise((resolve) => setTimeout(resolve, 260));
  typing.remove();
  if (!sessionMatches(session)) return;
  for (const item of bubbles) {
    if (!sessionMatches(session)) return;
    timeline.appendChild(bubbleRow(item.text, 'assistant'));
    scrollBottom();
    await new Promise((resolve) => setTimeout(resolve, 160));
  }
  if (!sessionMatches(session)) return;
  timeline.appendChild(metaRow(`${label || ''} ${timeLabel(at)}`.trim(), 'assistant'));
  const metas = timeline.querySelectorAll('.meta.user');
  if (metas.length) metas[metas.length - 1].textContent = `${timeLabel(at)} 已读`;
  scrollBottom();
}

function renderSelectors() {
  const personaList = $('#persona-list');
  personaList.innerHTML = '';
  for (const persona of state.personas) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `persona-button${persona.id === state.personaId ? ' active' : ''}`;
    button.innerHTML = `<strong></strong><span></span>`;
    button.querySelector('strong').textContent = persona.display_name;
    button.querySelector('span').textContent = `${persona.english_name} · ${persona.faction}`;
    button.addEventListener('click', () => {
      state.personaId = persona.id;
      renderSelectors();
      renderHeader();
      loadHistory();
    });
    personaList.appendChild(button);
  }

  const modelList = $('#model-list');
  modelList.innerHTML = '';
  for (const model of state.models) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `model-button${model.id === state.modelId ? ' active' : ''}`;
    button.innerHTML = `<strong></strong><span></span>`;
    button.querySelector('strong').textContent = model.label + (model.configured ? '' : '（演示兜底）');
    button.querySelector('span').textContent = model.model_name;
    button.addEventListener('click', () => {
      state.modelId = model.id;
      renderSelectors();
      renderHeader();
      loadHistory();
    });
    modelList.appendChild(button);
  }
}

function renderHeader() {
  const persona = state.personas.find((item) => item.id === state.personaId);
  const model = state.models.find((item) => item.id === state.modelId);
  $('#chat-title').textContent = persona ? persona.display_name : '请选择角色';
  $('#chat-subtitle').textContent = model ? `${model.label} · 单聊` : '';
}

function renderContext(context) {
  const slots = $('#context-slots');
  slots.innerHTML = '';
  const labels = { time_period: '时段', weather: '天气', schedule: '日程', energy: '精力' };
  for (const [key, label] of Object.entries(labels)) {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = context[key] || '';
    slots.append(dt, dd);
  }
}

async function loadHistory() {
  if (!state.personaId || !state.modelId) return;
  const session = snapshotSession();
  timeline.innerHTML = '<div class="day-divider">今天</div>';
  const response = await fetch(`/api/history?character_id=${encodeURIComponent(session.personaId)}&model_id=${encodeURIComponent(session.modelId)}`);
  const data = await response.json();
  if (!sessionMatches(session)) return;
  timeline.innerHTML = '<div class="day-divider">今天</div>';
  for (const item of data.items || []) {
    if (item.role === 'user') {
      timeline.appendChild(bubbleRow(item.text, 'user'));
      timeline.appendChild(metaRow(`${timeLabel(item.at)} 已读`, 'user'));
    } else {
      for (const text of item.bubbles || []) timeline.appendChild(bubbleRow(text, 'assistant'));
      timeline.appendChild(metaRow(`${item.model_id || ''} ${timeLabel(item.at)}`.trim(), 'assistant'));
    }
  }
  scrollBottom();
}

function payload(message, session) {
  return {
    character_id: session.personaId,
    model_id: session.modelId,
    message,
    include_context: session.includeContext,
  };
}

async function sendChat(message, session) {
  if (sessionMatches(session)) appendUser(message);
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload(message, session)),
  });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
  await appendAssistantBubbles(data.reply.bubbles, data.reply.model_label, new Date().toISOString(), session);
}

function compareCard(result) {
  const card = document.createElement('div');
  card.className = 'compare-card';
  const title = document.createElement('h3');
  title.textContent = result.model_label;
  if (!result.configured) {
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = '演示兜底';
    title.appendChild(badge);
  }
  card.appendChild(title);
  if (!result.ok) {
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = result.error;
    card.appendChild(error);
    return card;
  }
  for (const item of result.bubbles) {
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = item.text;
    card.appendChild(bubble);
  }
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = `${result.elapsed_ms} ms`;
  card.appendChild(meta);
  return card;
}

async function sendCompare(message, session) {
  if (sessionMatches(session)) appendUser(message);
  const panel = $('#compare-panel');
  const results = $('#compare-results');
  if (sessionMatches(session)) {
    panel.classList.remove('hidden');
    results.innerHTML = '<div class="typing">两个模型都在输入…</div>';
  }
  const response = await fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      character_id: session.personaId,
      message,
      include_context: session.includeContext,
    }),
  });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
  if (!sessionMatches(session)) return;
  results.innerHTML = '';
  for (const result of Object.values(data.results || {})) results.appendChild(compareCard(result));
  const current = data.results?.[session.modelId];
  if (current?.ok) await appendAssistantBubbles(current.bubbles, current.model_label, new Date().toISOString(), session);
}

function enqueue(kind) {
  const message = input.value.trim();
  if (!message || !state.personaId) return;
  const session = snapshotSession();
  input.value = '';
  state.queue = state.queue.then(async () => {
    try {
      if (kind === 'compare') await sendCompare(message, session);
      else await sendChat(message, session);
    } catch (error) {
      if (!sessionMatches(session)) return;
      const row = document.createElement('div');
      row.className = 'error';
      row.textContent = error.message;
      timeline.appendChild(row);
      scrollBottom();
    }
  });
}

async function boot() {
  const response = await fetch('/api/bootstrap');
  const data = await response.json();
  state.personas = data.personas || [];
  state.models = data.models || [];
  state.personaId = state.personas[0]?.id || null;
  state.modelId = state.models[0]?.id || null;
  renderSelectors();
  renderHeader();
  renderContext(data.context || {});
  await loadHistory();
}

$('#composer').addEventListener('submit', (event) => {
  event.preventDefault();
  enqueue('chat');
});
$('#compare-button').addEventListener('click', () => enqueue('compare'));
$('#close-compare').addEventListener('click', () => $('#compare-panel').classList.add('hidden'));

boot().catch((error) => {
  timeline.innerHTML = '';
  const row = document.createElement('div');
  row.className = 'error';
  row.textContent = `启动失败：${error.message}`;
  timeline.appendChild(row);
});
