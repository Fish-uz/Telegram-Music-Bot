const state = { view: 'overview', token: localStorage.getItem('allmusic_dashboard_token') || '', data: {} };
const content = document.querySelector('#content');
const titles = {
  overview: ['RESUMEN', 'Panel de control'], users: ['USUARIOS', 'Gestión de usuarios'],
  library: ['BIBLIOTECA', 'Biblioteca de Telegram'], system: ['SISTEMA', 'Diagnóstico del servicio'],
};

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 || response.status === 503) {
    document.querySelector('#auth-dialog').showModal();
    throw new Error('Autenticación requerida');
  }
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

const esc = (value) => String(value ?? '—').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
const displayUser = (username) => username ? `@${esc(username)}` : 'Sin usuario';
const date = (value) => value ? new Date(value).toLocaleString('es-VE', { dateStyle: 'medium', timeStyle: 'short' }) : 'Sin actividad';
const bytes = (value) => `${(Number(value || 0) / 1024 / 1024).toFixed(2)} MB`;
const metric = (label, value, note = '') => `<article class="card"><span class="metric-label">${label}</span><strong class="metric-value">${value}</strong><span class="metric-note">${note}</span></article>`;
function table(headers, rows) { return `<div class="table-wrap"><table><thead><tr>${headers.map((header) => `<th>${header}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`; }

async function overview() {
  const data = await api('/api/stats'); const summary = data.summary;
  const max = Math.max(1, ...data.top.map((item) => item[1]));
  content.innerHTML = `<div class="metrics">${metric('Usuarios', summary.total_users, 'registrados')}${metric('Descargas', summary.total_downloads, 'históricas')}${metric('Caché', summary.cached_songs, `${summary.cache_rate}% reutilización`)}${metric('Fallos', summary.failed_downloads, 'registrados')}</div><div class="grid-2"><section class="panel"><h2>Top global</h2><div class="bars">${data.top.map(([title, count], index) => `<div><div class="bar-label"><span>${index + 1}. ${esc(title)}</span><strong>${count}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${count / max * 100}%"></div></div></div>`).join('') || '<div class="empty">Sin descargas todavía</div>'}</div></section><section class="panel"><h2>Estado operacional</h2><div id="overview-system" class="system-grid"></div></section></div>`;
  document.querySelector('#overview-system').innerHTML = operationalItems(await api('/api/system'));
}

function filtered(items, query, fields) {
  const normalized = query.toLowerCase();
  return items.filter((item) => fields.some((field) => String(item[field] ?? '').toLowerCase().includes(normalized)));
}
async function users() { state.data.users = await api('/api/users'); renderUsers(state.data.users); }
function renderUsers(data) {
  content.innerHTML = `<div class="toolbar"><input id="search-users" placeholder="Buscar ID, usuario o canción…"><span class="result-count">${data.length} usuarios</span></div>${table(['Usuario', 'Descargas', 'Última canción descargada', 'Última actividad', 'Estado', 'Acción'], data.map((user) => `<tr data-user="${user.user_id}"><td><div class="user-identity"><strong>${displayUser(user.username)}</strong><small>ID ${user.user_id}</small></div></td><td><strong>${user.total_downloads}</strong></td><td class="song-cell" title="${esc(user.last_song_title || '')}">${esc(user.last_song_title || 'Aún no ha descargado')}</td><td>${date(user.last_download_date)}</td><td><span class="chip ${user.is_banned ? 'bad' : 'good'}">${user.is_banned ? 'Baneado' : 'Activo'}</span></td><td><button class="button compact ${user.is_banned ? 'success' : 'danger'}" data-ban-user="${user.user_id}" data-banned="${user.is_banned ? '1' : '0'}">${user.is_banned ? 'Desbanear' : 'Banear'}</button></td></tr>`))}`;
  document.querySelector('#search-users').oninput = (event) => renderUsers(filtered(state.data.users, event.target.value, ['user_id', 'username', 'last_song_title']));
  document.querySelectorAll('[data-user]').forEach((row) => { row.onclick = () => userDetail(row.dataset.user); });
  document.querySelectorAll('[data-ban-user]').forEach((button) => { button.onclick = (event) => { event.stopPropagation(); toggleBan(button); }; });
}
async function toggleBan(button) {
  const userId = button.dataset.banUser; const banned = button.dataset.banned === '1';
  button.disabled = true; button.textContent = 'Guardando…';
  try {
    await api(`/api/users/${userId}/ban`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ banned: !banned }) });
    state.data.users = state.data.users.map((user) => user.user_id === Number(userId) ? { ...user, is_banned: !banned } : user);
    renderUsers(state.data.users);
  } catch (error) {
    button.disabled = false; button.textContent = banned ? 'Desbanear' : 'Banear';
    window.alert(`No se pudo actualizar el usuario: ${error.message}`);
  }
}
async function userDetail(id) {
  const data = await api(`/api/users/${id}`); const user = data.info;
  document.querySelector('#detail-content').innerHTML = `<div class="detail-heading"><div class="user-avatar">${esc((user.username || '?')[0].toUpperCase())}</div><div><h2>${displayUser(user.username)}</h2><p>ID ${user.user_id} · ${user.total_downloads} descargas</p></div></div><div class="detail-latest"><span>Última canción descargada</span><strong>${esc(user.last_song_title || 'Aún no ha descargado')}</strong></div><h3>Historial</h3>${table(['Pista', 'Fecha', 'Origen'], data.history.map((item) => `<tr><td>${esc(item.title)}</td><td>${date(item.date)}</td><td>${item.cache_hit ? 'Caché' : 'Nueva'}</td></tr>`))}`;
  document.querySelector('#detail-dialog').showModal();
}

async function library() { state.data.songs = await api('/api/songs'); renderLibrary(state.data.songs); }
function renderLibrary(data) {
  content.innerHTML = `<div class="toolbar"><input id="search-songs" placeholder="Buscar canción o ID…"><span class="result-count">${data.length} canciones</span></div>${table(['Título', 'YouTube ID', 'Descargas', 'Último uso'], data.map((song) => `<tr><td>${esc(song.title)}</td><td><code>${song.video_id}</code></td><td>${song.download_count}</td><td>${date(song.last_used_at)}</td></tr>`))}`;
  document.querySelector('#search-songs').oninput = (event) => renderLibrary(filtered(state.data.songs, event.target.value, ['title', 'video_id']));
}

function operationalItems(system) {
  return Object.entries({ Bot: system.bot_online ? 'Online' : 'Offline', 'Descargas activas': system.active_downloads, 'En cola': system.queue_depth, 'yt-dlp': system.yt_dlp_version }).map(([label, value]) => `<div class="system-item"><span>${label}</span><strong>${esc(value)}</strong></div>`).join('');
}
async function system() {
  const data = await api('/api/system');
  content.innerHTML = `<div class="system-layout"><section class="panel"><div class="panel-title"><div><h2>Servicio AllMusic</h2><p>Estado en tiempo real del bot y su carga de trabajo.</p></div><span class="service-status ${data.bot_online ? 'online' : ''}">${data.bot_online ? 'Operativo' : 'Detenido'}</span></div><div class="system-grid">${operationalItems(data)}</div></section><section class="panel"><div class="panel-title"><div><h2>Entorno</h2><p>Versiones y almacenamiento usados por esta instancia.</p></div></div><div class="system-grid"><div class="system-item"><span>Sistema operativo</span><strong>${esc(data.platform)}</strong></div><div class="system-item"><span>Python</span><strong>${esc(data.python_version)}</strong></div><div class="system-item"><span>Base de datos</span><strong>${bytes(data.database_size_bytes)}</strong></div><div class="system-item"><span>Última comprobación</span><strong>${date(data.checked_at)}</strong></div></div></section></div>`;
}

async function render() {
  const [section, title] = titles[state.view];
  document.querySelector('#section-name').textContent = section; document.querySelector('#page-title').textContent = title;
  content.innerHTML = '<div class="loading">Cargando datos…</div>';
  try { await ({ overview, users, library, system }[state.view])(); }
  catch (error) { if (!/Autenticación/.test(error.message)) content.innerHTML = `<div class="empty">${esc(error.message)}</div>`; }
}
async function health() {
  try { const result = await api('/api/health'); document.querySelector('#status-dot').classList.toggle('online', result.bot); document.querySelector('#bot-status').textContent = result.bot ? 'Bot online' : 'Bot offline'; }
  catch { document.querySelector('#bot-status').textContent = 'Sin conexión'; }
}
document.querySelectorAll('#nav button').forEach((button) => { button.onclick = () => { document.querySelectorAll('#nav button').forEach((item) => item.classList.remove('active')); button.classList.add('active'); state.view = button.dataset.view; render(); }; });
document.querySelector('#refresh').onclick = render;
document.querySelector('#save-token').onclick = () => { state.token = document.querySelector('#token-input').value.trim(); localStorage.setItem('allmusic_dashboard_token', state.token); setTimeout(render); };
health(); render(); setInterval(health, 30000);
