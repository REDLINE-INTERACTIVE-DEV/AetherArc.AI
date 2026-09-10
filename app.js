const $ = (id) => document.getElementById(id);
const backend = window.location.origin.replace(/\/$/, '');
let token = localStorage.getItem('aether_token') || '';
let mode = 'login';

const FEATURES = [
  ['🧠','ManagerAI','Your default AI manager. It understands the task, delegates work, combines specialist reports, and gives you one final answer.'],
  ['💡','ReasonAI','Breaks down difficult problems, checks assumptions, compares approaches, and helps with decisions.'],
  ['💻','CodeAI','Builds, debugs, explains, and improves software. It can also work with connected developer tools when configured.'],
  ['🔎','ResearchAI','Researches current information, news, and public websites, then turns the evidence into useful findings.'],
  ['🎨','Image generation','Turns image ideas into generated artwork when the image-generation service is configured.'],
  ['🗂️','Saved history','Accounts can keep conversations and history. Guest chats are temporary and are not saved.']
];

function setStatus(message, ok = false) {
  const el = $('authNote');
  if (!el) return;
  el.textContent = message;
  el.dataset.ok = ok ? '1' : '0';
}

function renderFeatures() {
  if ($('featureGrid')) return;
  const card = document.querySelector('.auth-card');
  if (!card) return;
  const section = document.createElement('section');
  section.className = 'feature-section';
  section.innerHTML = `<div class="feature-heading"><span>WHAT AETHER CAN DO</span><h2>One AI team. Different specialists.</h2><p>ManagerAI is the front door, while the specialist AIs handle the parts they are built for.</p></div><div id="featureGrid" class="feature-grid">${FEATURES.map(([icon,name,desc]) => `<article class="feature"><div class="feature-icon">${icon}</div><h3>${name}</h3><p>${desc}</p></article>`).join('')}</div>`;
  card.appendChild(section);
}

function switchMode(next) {
  mode = next;
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.mode === next));
  $('authBtn').textContent = next === 'login' ? 'Log in to Aether' : 'Create my Aether account';
  $('authTitle').textContent = next === 'login' ? 'Welcome back' : 'Create your Aether account';
  $('authSubtitle').textContent = next === 'login' ? 'Your AI team is ready.' : 'Create an account to keep your conversations and history.';
  setStatus('');
}

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${backend}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.message || `Request failed (${res.status})`);
  return data;
}

function openApp() {
  localStorage.setItem('aether_token', token);
  $('auth').classList.add('hidden');
  $('app').classList.remove('hidden');
  setTimeout(() => window.location.reload(), 0);
}

async function authSubmit() {
  const email = $('email').value.trim();
  const password = $('password').value;
  if (!email || !password) return setStatus('Enter your email and password first.');
  if (password.length < 6) return setStatus('Use a password with at least 6 characters.');
  const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
  const btn = $('authBtn');
  btn.disabled = true;
  setStatus(mode === 'login' ? 'Signing you in…' : 'Creating your account…');
  try {
    const data = await api(endpoint, { method: 'POST', body: JSON.stringify({ email, password }) });
    token = data.token;
    setStatus(mode === 'login' ? 'Logged in. Opening Aether…' : 'Account created. Opening Aether…', true);
    openApp();
  } catch (e) {
    setStatus(e.message);
  } finally { btn.disabled = false; }
}

async function guestLogin() {
  $('guestBtn').disabled = true;
  setStatus('Starting a temporary guest session…');
  try {
    const data = await api('/api/auth/guest', { method: 'POST', body: JSON.stringify({ name: 'Guest' }) });
    token = data.token;
    setStatus('Guest session ready. Opening Aether…', true);
    openApp();
  } catch (e) {
    setStatus(e.message);
  } finally { $('guestBtn').disabled = false; }
}

async function oauth(provider) {
  try {
    const p = await api('/api/auth/providers');
    if (!p[provider]) {
      setStatus(`${provider[0].toUpperCase()+provider.slice(1)} sign-in is not configured on this Aether server yet. Email login or Guest mode is ready now.`);
      return;
    }
    setStatus(`${provider[0].toUpperCase()+provider.slice(1)} sign-in is enabled, but its OAuth redirect still needs to be wired into Aether.`);
  } catch (e) { setStatus(e.message); }
}

function bind() {
  document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => switchMode(b.dataset.mode)));
  $('authBtn')?.addEventListener('click', authSubmit);
  $('guestBtn')?.addEventListener('click', guestLogin);
  $('googleBtn')?.addEventListener('click', () => oauth('google'));
  $('githubBtn')?.addEventListener('click', () => oauth('github'));
  $('password')?.addEventListener('keydown', e => { if (e.key === 'Enter') authSubmit(); });
  $('newChat')?.addEventListener('click', () => { $('messages').innerHTML = ''; $('input').focus(); });
  $('logout')?.addEventListener('click', () => { localStorage.removeItem('aether_token'); location.reload(); });
  document.querySelectorAll('[data-q]').forEach(b => b.addEventListener('click', () => { $('input').value = b.dataset.q; $('input').focus(); }));
}

async function bootApp() {
  if (!token) return;
  try {
    const cfg = await api('/api/config');
    const status = $('modelStatus');
    if (status) status.textContent = cfg.model_connected ? `AI online · ${cfg.model || 'model connected'}` : 'AI provider not configured';
    const history = await api('/api/history');
    if ($('historyState')) $('historyState').textContent = history.saved ? `${history.history.length} saved` : 'Guest';
  } catch (e) {
    localStorage.removeItem('aether_token');
    token = '';
  }
}

renderFeatures();
bind();
bootApp();
