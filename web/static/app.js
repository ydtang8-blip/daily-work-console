const state = {
  tab: 'home',
  todos: [],
  skills: [],
  skillsCounts: {},
  settings: {},
  dash: null,
};

const PRI = { high: '高', medium: '中', low: '低' };
const STATUS = { pending: '待办', in_progress: '进行中', done: '已完成' };
const LOC = { core: '核心', top: '顶层', library: '图书馆' };

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `请求失败 ${res.status}`);
  }
  return data;
}

function toast(msg, type = 'ok') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast show ${type}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = 'toast hidden'), 2600);
}

function go(tab) {
  state.tab = tab;
  document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${tab}`));
  if (tab === 'home') loadDashboard();
  if (tab === 'todos') loadTodos();
  if (tab === 'logs') loadLogs();
  if (tab === 'improvements') loadImprovements();
  if (tab === 'projects') loadProjects();
  if (tab === 'skills') loadSkills('');
  if (tab === 'settings') loadSettings();
}

function openModal(title, bodyHtml) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHtml;
  document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}

document.getElementById('modal').addEventListener('click', (e) => {
  if (e.target.id === 'modal') closeModal();
});

function chip(pri) {
  return `<span class="chip p-${pri}">${PRI[pri] || pri}</span>`;
}

function dueBadge(t) {
  const badges = [];
  if (t.status === 'done') return '';
  const today = new Date().toISOString().slice(0, 10);
  if (t.notes && t.notes.includes('昨日结转')) badges.push('<span class="chip carry">昨日结转</span>');
  if (t.due_date && t.due_date < today) badges.push('<span class="chip due">已逾期</span>');
  if (t.due_date === today) badges.push('<span class="chip today">今天</span>');
  return badges.join('');
}

/* ---------------- 首页 ---------------- */

async function loadDashboard() {
  try {
    state.dash = await api('/api/dashboard');
  } catch (e) {
    toast(e.message, 'err');
    return;
  }
  const d = state.dash;
  document.getElementById('today-label').textContent = d.today;
  document.getElementById('badge-todos').textContent = d.overdue ? String(d.overdue) : '';
  document.getElementById('badge-imp').textContent = d.improvements_open ? String(d.improvements_open) : '';

const cards = [
    ['今日待办', d.todo_counts.pending + d.todo_counts.in_progress, ''],
    ['昨日结转', d.carried, d.carried ? 'warn' : ''],
    ['逾期未办', d.overdue, d.overdue ? 'warn' : ''],
    ['改进点待落实', d.improvements_open, ''],
    ['活跃项目', d.projects_active, ''],
  ];
  document.getElementById('home-cards').innerHTML = cards
    .map(([t, n, cls]) => `<div class="card ${cls}"><div class="card-num">${n}</div><div class="card-label">${t}</div></div>`)
    .join('');

  const todosEl = document.getElementById('home-todos');
  todosEl.innerHTML = d.today_todos.length
    ? d.today_todos.map(renderTodoRow).join('')
    : '<div class="empty">今天暂无待办 🎉</div>';

  const log = d.today_log;
  document.getElementById('home-log').innerHTML =
    (log.review ? `<p class="pre">${esc(log.review)}</p>` : '<div class="empty">今天还没写复盘</div>');

  document.getElementById('home-recent').innerHTML = d.recent_logs.length
    ? d.recent_logs.map((l) => `<div class="recent-item"><b>${esc(l.date)}</b><span class="pre clamp">${esc(l.review || '（空）')}</span></div>`).join('')
    : '<div class="empty">暂无记录</div>';
}

/* ---------------- 待办 ---------------- */

async function loadTodos() {
  const status = document.getElementById('todo-filter-status').value;
  const overdue = document.getElementById('todo-filter-overdue').value;
  let url = '/api/todos';
  const q = new URLSearchParams();
  if (status) q.set('status', status);
  if (overdue) q.set('overdue_only', '1');
  const qs = q.toString();
  if (qs) url += '?' + qs;
  try {
    state.todos = (await api(url)).todos;
  } catch (e) {
    toast(e.message, 'err');
    return;
  }
  const el = document.getElementById('todo-list');
  el.innerHTML = state.todos.length
    ? state.todos.map(renderTodoRow).join('')
    : '<div class="empty">没有待办，干得漂亮</div>';
}

function renderTodoRow(t) {
  const done = t.status === 'done';
  const meta = [t.project && `📁 ${t.project}`, t.due_date && `📅 ${t.due_date}${t.due_time ? ' ' + t.due_time : ''}`]
    .filter(Boolean)
    .join(' · ');
  return `
    <div class="todo-row ${done ? 'done' : ''}">
      <button class="check ${done ? 'checked' : ''}" onclick="toggleTodo(${t.id})" title="完成/恢复">${done ? '✓' : ''}</button>
      <div class="todo-main">
        <div class="todo-title">${esc(t.title)} ${dueBadge(t)}</div>
        <div class="meta">${meta ? esc(meta) : ''}</div>
        ${t.notes ? `<div class="notes">${esc(t.notes)}</div>` : ''}
      </div>
      <div class="todo-ops">
        ${chip(t.priority)}
        <button class="btn small" onclick="openTodoForm(${t.id})">编辑</button>
        <button class="btn small danger" onclick="deleteTodo(${t.id})">删</button>
      </div>
    </div>`;
}

function openTodoForm(id) {
  const t = state.todos.find((x) => x.id === id) || {
    title: '', priority: 'medium', status: 'pending', project: '', due_date: '', due_time: '', notes: '',
  };
  const today = new Date().toISOString().slice(0, 10);
  openModal(
    id ? '编辑待办' : '新增待办',
    `<div class="form">
      <label>内容<input type="text" id="f-title" value="${esc(t.title)}" placeholder="要做什么"></label>
      <label>优先级<select id="f-priority">
        ${['high', 'medium', 'low'].map((p) => `<option value="${p}" ${t.priority === p ? 'selected' : ''}>${PRI[p]}</option>`).join('')}
      </select></label>
      <label>状态<select id="f-status">
        ${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${t.status === k ? 'selected' : ''}>${v}</option>`).join('')}
      </select></label>
      <label>项目<input type="text" id="f-project" value="${esc(t.project)}" list="project-list-opt" placeholder="关联项目">
        <datalist id="project-list-opt"></datalist></label>
      <label>截止日期<input type="date" id="f-due" value="${t.due_date || today}"></label>
      <label>截止时间<input type="time" id="f-time" value="${t.due_time}"></label>
      <label>备注<textarea id="f-notes" rows="2">${esc(t.notes)}</textarea></label>
      <div class="form-actions">
        <button class="btn" onclick="closeModal()">取消</button>
        <button class="btn primary" onclick="saveTodo(${id || 0})">保存</button>
      </div>
    </div>`,
  );
  api('/api/projects').then((d) => {
    document.getElementById('project-list-opt').innerHTML = d.projects
      .map((p) => `<option value="${esc(p.name)}">`)
      .join('');
  });
}

async function saveTodo(id) {
  const body = {
    title: document.getElementById('f-title').value.trim(),
    priority: document.getElementById('f-priority').value,
    status: document.getElementById('f-status').value,
    project: document.getElementById('f-project').value.trim(),
    due_date: document.getElementById('f-due').value,
    due_time: document.getElementById('f-time').value,
    notes: document.getElementById('f-notes').value.trim(),
  };
  if (!body.title) {
    toast('内容不能为空', 'err');
    return;
  }
  try {
    if (id) await api(`/api/todos/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    else await api('/api/todos', { method: 'POST', body: JSON.stringify(body) });
    closeModal();
    loadTodos();
    toast('已保存');
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function toggleTodo(id) {
  try {
    await api(`/api/todos/${id}/toggle`, { method: 'POST' });
    loadTodos();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function deleteTodo(id) {
  if (!confirm('删除这条待办？')) return;
  try {
    await api(`/api/todos/${id}`, { method: 'DELETE' });
    loadTodos();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function rolloverTodos() {
  if (!confirm('把昨天及更早的未完成待办顺延到今天？')) return;
  try {
    const r = await api('/api/todos/rollover', { method: 'POST' });
    toast(`已结转 ${r.rolled} 条到今日`);
    loadTodos();
  } catch (e) {
    toast(e.message, 'err');
  }
}

/* ---------------- 复盘 ---------------- */

function setLogDate() {
  const el = document.getElementById('log-date');
  if (!el.value) el.value = new Date().toISOString().slice(0, 10);
}

function renderActivity(events) {
  const el = document.getElementById('activity-panel');
  if (!events || !Object.keys(events).length) {
    el.className = 'muted hint';
    el.innerHTML = '今日还没采集过。点「采集今日活动」。';
    return;
  }
  const sec = (title, list) => list && list.length
    ? `<div class="activity-sec"><b>${title}（${list.length}）</b>${list.slice(0, 12).map((e) => `<div class="activity-item"><span class="t">${esc(e.time || '--')}</span> ${esc(e.title)}</div>`).join('')}${list.length > 12 ? `<div class="muted">…共 ${list.length} 条</div>` : ''}</div>`
    : '';
  el.className = 'activity';
  el.innerHTML = sec('Git 提交', events.git) + sec('文件改动', events.files) + sec('终端命令', events.terminal);
}

async function collectActivity() {
  const btn = event.currentTarget;
  btn.disabled = true;
  btn.textContent = '采集中…';
  try {
    const r = await api('/api/activity/collect', { method: 'POST' });
    renderActivity(r.events);
    toast(`已采集 ${r.count} 条活动，AI 复盘会引用`);
  } catch (e) {
    toast(e.message, 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = '采集今日活动';
  }
}

async function loadActivity(date) {
  try {
    const d = await api(`/api/activity/${date}`);
    renderActivity(d.events);
  } catch (e) {
    /* 忽略 */
  }
}

async function loadLogs() {
  setLogDate();
  const date = document.getElementById('log-date').value;
  const log = await api(`/api/logs/${date}`);
  document.getElementById('log-review').value = log.review || '';
  document.getElementById('log-done').value = log.done_items || '';
  document.getElementById('log-imp').value = log.improvements || '';
  document.getElementById('log-unfinished').value = log.unfinished || '';
  document.getElementById('log-notes').value = log.notes || '';
  loadActivity(date);
  const list = (await api('/api/logs')).logs;
  document.getElementById('log-list').innerHTML = list.length
    ? list
        .map((l) => `<div class="recent-item"><b>${esc(l.date)}</b><span class="pre clamp">${esc(l.review || '（空）')}</span><button class="btn small" onclick="jumpLog('${l.date}')">打开</button></div>`)
        .join('')
    : '<div class="empty">暂无记录</div>';
}

function jumpLog(date) {
  document.getElementById('log-date').value = date;
  loadLogs();
}

async function saveLog() {
  const body = {
    date: document.getElementById('log-date').value,
    review: document.getElementById('log-review').value.trim(),
    done_items: document.getElementById('log-done').value.trim(),
    improvements: document.getElementById('log-imp').value.trim(),
    unfinished: document.getElementById('log-unfinished').value.trim(),
    notes: document.getElementById('log-notes').value.trim(),
  };
  try {
    await api('/api/logs', { method: 'POST', body: JSON.stringify(body) });
    toast('已保存');
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function aiGenerateReview() {
  const btn = event.currentTarget;
  btn.disabled = true;
  btn.textContent = 'AI 生成中…';
  try {
    const r = await api('/api/reviews/ai', { method: 'POST' });
    document.getElementById('log-review').value = r.review || '';
    if (r.done_items && !document.getElementById('log-done').value.trim()) document.getElementById('log-done').value = r.done_items;
    if (r.improvements && !document.getElementById('log-imp').value.trim()) document.getElementById('log-imp').value = r.improvements;
    if (r.unfinished && !document.getElementById('log-unfinished').value.trim()) document.getElementById('log-unfinished').value = r.unfinished;
    toast('AI 复盘草稿已生成，改改再保存');
  } catch (e) {
    toast(e.message, 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = 'AI 生成复盘';
  }
}

async function copyLogToImprovements() {
  const lines = document.getElementById('log-imp').value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
  for (const line of lines) {
    const [title, ...rest] = line.split('：');
    await api('/api/improvements', {
      method: 'POST',
      body: JSON.stringify({ title: title.slice(0, 80), detail: rest.join('：') || title, source: '复盘' }),
    });
  }
  toast(`已转存 ${lines.length} 条改进点`);
}

async function copyLogToTodos() {
  const lines = document.getElementById('log-unfinished').value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
  for (const line of lines) {
    await api('/api/todos', {
      method: 'POST',
      body: JSON.stringify({ title: line, priority: 'medium', project: '', due_date: '' }),
    });
  }
  toast(`已转存 ${lines.length} 条待办`);
}

/* ---------------- 改进点 ---------------- */

async function loadImprovements() {
  const filter = document.getElementById('imp-filter').value;
  const url = '/api/improvements' + (filter ? `?status=${filter}` : '');
  const data = await api(url);
  const el = document.getElementById('imp-list');
  el.innerHTML = data.improvements.length
    ? data.improvements
        .map(
          (i) => `<div class="imp-row ${i.status === 'done' ? 'done' : ''}">
          <button class="check ${i.status === 'done' ? 'checked' : ''}" onclick="toggleImp(${i.id})">${i.status === 'done' ? '✓' : ''}</button>
          <div class="todo-main">
            <div class="todo-title">${esc(i.title)}</div>
            ${i.detail ? `<div class="notes">${esc(i.detail)}</div>` : ''}
            ${i.source ? `<div class="meta">来源：${esc(i.source)} · ${esc(i.created_at)}</div>` : ''}
          </div>
          <div class="todo-ops">
            <button class="btn small" onclick="openImpForm(${i.id})">编辑</button>
            <button class="btn small danger" onclick="deleteImp(${i.id})">删</button>
          </div>
        </div>`,
        )
        .join('')
    : '<div class="empty">暂无改进点</div>';
}

function openImpForm(id) {
  const i = state.improvements?.find((x) => x.id === id) || { title: '', detail: '', source: '' };
  openModal(
    id ? '编辑改进点' : '新增改进点',
    `<div class="form">
      <label>标题<input type="text" id="f-imp-title" value="${esc(i.title)}"></label>
      <label>说明<textarea id="f-imp-detail" rows="3">${esc(i.detail)}</textarea></label>
      <label>来源<input type="text" id="f-imp-source" value="${esc(i.source)}"></label>
      <div class="form-actions">
        <button class="btn" onclick="closeModal()">取消</button>
        <button class="btn primary" onclick="saveImp(${id || 0})">保存</button>
      </div>
    </div>`,
  );
}

async function saveImp(id) {
  const body = {
    title: document.getElementById('f-imp-title').value.trim(),
    detail: document.getElementById('f-imp-detail').value.trim(),
    source: document.getElementById('f-imp-source').value.trim(),
  };
  if (!body.title) {
    toast('标题不能为空', 'err');
    return;
  }
  try {
    if (id) await api(`/api/improvements/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    else await api('/api/improvements', { method: 'POST', body: JSON.stringify(body) });
    closeModal();
    loadImprovements();
    toast('已保存');
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function toggleImp(id) {
  try {
    await api(`/api/improvements/${id}/toggle`, { method: 'POST' });
    loadImprovements();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function deleteImp(id) {
  if (!confirm('删除这条改进点？')) return;
  try {
    await api(`/api/improvements/${id}`, { method: 'DELETE' });
    loadImprovements();
  } catch (e) {
    toast(e.message, 'err');
  }
}

/* ---------------- 项目 ---------------- */

async function loadProjects() {
  const data = await api('/api/projects');
  state.projects = data.projects;
  const el = document.getElementById('project-list');
  el.innerHTML = data.projects.length
    ? data.projects
        .map(
          (p) => `<div class="project-card">
          <div class="project-head">
            <div>
              <b>${esc(p.name)}</b>
              <span class="chip st-${p.status}">${p.status === 'active' ? '进行中' : p.status === 'paused' ? '暂停' : '已完成'}</span>
            </div>
            <div class="progress"><div class="bar" style="width:${p.progress}%"></div><span>${p.progress}%</span></div>
          </div>
          ${p.current_task ? `<div class="meta">当前：${esc(p.current_task)}</div>` : ''}
          ${p.next_steps ? `<div class="notes">下一步：${esc(p.next_steps)}</div>` : ''}
          ${p.notes ? `<div class="notes muted">${esc(p.notes)}</div>` : ''}
          <div class="project-ops">
            <button class="btn small" onclick="nextToTodo(${p.id})">→ 下一步转待办</button>
            <button class="btn small" onclick="openProjectForm(${p.id})">编辑</button>
            <button class="btn small" onclick="cycleProjectStatus(${p.id})">${p.status === 'active' ? '暂停' : '恢复'}</button>
            <button class="btn small danger" onclick="deleteProject(${p.id})">删</button>
          </div>
        </div>`,
        )
        .join('')
    : '<div class="empty">暂无项目</div>';
}

function openProjectForm(id) {
  const p = state.projects.find((x) => x.id === id) || {
    name: '', status: 'active', progress: 0, current_task: '', next_steps: '', notes: '',
  };
  openModal(
    id ? '编辑项目' : '新增项目',
    `<div class="form">
      <label>项目名<input type="text" id="f-p-name" value="${esc(p.name)}"></label>
      <label>状态<select id="f-p-status">
        ${['active', 'paused', 'done'].map((s) => `<option value="${s}" ${p.status === s ? 'selected' : ''}>${s === 'active' ? '进行中' : s === 'paused' ? '暂停' : '已完成'}</option>`).join('')}
      </select></label>
      <label>进度<input type="range" id="f-p-progress" min="0" max="100" value="${p.progress}" oninput="document.getElementById('p-prog-val').textContent=this.value+'%'"> <span id="p-prog-val">${p.progress}%</span></label>
      <label>当前任务<textarea id="f-p-current" rows="2">${esc(p.current_task)}</textarea></label>
      <label>下一步（每行一项）<textarea id="f-p-next" rows="3">${esc(p.next_steps)}</textarea></label>
      <label>备注<textarea id="f-p-notes" rows="2">${esc(p.notes)}</textarea></label>
      <div class="form-actions">
        <button class="btn" onclick="closeModal()">取消</button>
        <button class="btn primary" onclick="saveProject(${id || 0})">保存</button>
      </div>
    </div>`,
  );
}

async function saveProject(id) {
  const body = {
    name: document.getElementById('f-p-name').value.trim(),
    status: document.getElementById('f-p-status').value,
    progress: Number(document.getElementById('f-p-progress').value),
    current_task: document.getElementById('f-p-current').value.trim(),
    next_steps: document.getElementById('f-p-next').value.trim(),
    notes: document.getElementById('f-p-notes').value.trim(),
  };
  if (!body.name) {
    toast('项目名不能为空', 'err');
    return;
  }
  try {
    if (id) await api(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    else await api('/api/projects', { method: 'POST', body: JSON.stringify(body) });
    closeModal();
    loadProjects();
    toast('已保存');
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function cycleProjectStatus(id) {
  const p = state.projects.find((x) => x.id === id);
  const next = p.status === 'active' ? 'paused' : 'active';
  try {
    await api(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify({ status: next }) });
    loadProjects();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function deleteProject(id) {
  if (!confirm('删除这个项目？')) return;
  try {
    await api(`/api/projects/${id}`, { method: 'DELETE' });
    loadProjects();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function nextToTodo(pid) {
  try {
    const todo = await api(`/api/todos/from-project/${pid}`, { method: 'POST' });
    toast(`已生成待办：${todo.title}`);
  } catch (e) {
    toast(e.message, 'err');
  }
}

/* ---------------- 技能库 ---------------- */

async function loadSkills(q) {
  const data = await api('/api/skills?q=' + encodeURIComponent(q));
  state.skills = data.skills;
  state.skillsCounts = data.counts;
  document.getElementById('skills-counts').textContent =
    `（核心 ${data.counts.core} / 顶层 ${data.counts.top} / 图书馆 ${data.counts.library} / 共 ${data.counts.total}）`;
  document.getElementById('skills-filter').innerHTML = ['', 'core', 'top', 'library']
    .map(
      (f) => `<button class="chip-btn ${!q && f === '' ? 'on' : ''}" data-f="${f}" onclick="filterSkills('${f}')">${
        f === '' ? '全部' : LOC[f]
      }</button>`,
    )
    .join('');
  renderSkills(q, '');
}

let activeSkillFilter = '';

function filterSkills(f) {
  activeSkillFilter = f;
  renderSkills(document.getElementById('skills-q').value, f);
}

function renderSkills(q, f) {
  const el = document.getElementById('skills-list');
  let list = state.skills;
  if (f) list = list.filter((s) => s.location === f);
  if (!list.length) {
    el.innerHTML = '<div class="empty">没有匹配的技能</div>';
    return;
  }
  el.innerHTML = list
    .map(
      (s) => `<div class="skill-item">
        <div class="skill-head">
          <span class="chip loc-${s.location}">${LOC[s.location]}</span>
          <b>${esc(s.name)}</b>
        </div>
        <div class="notes clamp2">${esc(s.description || '（无描述）')}</div>
        <button class="btn small" onclick="openSkill('${esc(s.path.replace(/\\/g, '\\\\'))}')">查看</button>
      </div>`,
    )
    .join('');
}

async function openSkill(path) {
  try {
    const res = await fetch('/api/skill-content?path=' + encodeURIComponent(path));
    const data = await res.json();
    openModal('SKILL.md', `<pre class="skill-view">${esc(data.content)}</pre>`);
  } catch (e) {
    toast(e.message, 'err');
  }
}

document.getElementById('skills-q').addEventListener('input', (e) => {
  clearTimeout(e.target._t);
  e.target._t = setTimeout(() => loadSkills(e.target.value), 250);
});

/* ---------------- 设置 ---------------- */

async function loadSettings() {
  const s = await api('/api/settings');
  document.getElementById('set-channel').value = s.channel || 'pushdeer';
  document.getElementById('set-title').value = s.pushplus_title || '工作台提醒';
  document.getElementById('set-skills-path').value = s.skills_path || '';
  document.getElementById('set-activity-dirs').value = s.activity_dirs || '';
  document.getElementById('set-port').value = s.port || '8789';
  document.getElementById('set-token').placeholder = s.has_pushplus_token ? '已配置（留空不变）' : '未配置';
  document.getElementById('set-pushdeer').placeholder = s.has_pushdeer_key ? '已配置（留空不变）' : '未配置';
  document.getElementById('set-bark').placeholder = s.has_bark_key ? '已配置（留空不变）' : '未配置';
  document.getElementById('set-deepseek').placeholder = s.has_deepseek_key ? '已配置（留空不变）' : '未配置';
}

async function saveSettings() {
  const body = {};
  const token = document.getElementById('set-token').value;
  if (token) body.pushplus_token = token;
  const pd = document.getElementById('set-pushdeer').value;
  if (pd) body.pushdeer_key = pd;
  const bk = document.getElementById('set-bark').value;
  if (bk) body.bark_key = bk;
  const dsk = document.getElementById('set-deepseek').value;
  if (dsk) body.deepseek_key = dsk;
  body.channel = document.getElementById('set-channel').value;
  body.pushplus_title = document.getElementById('set-title').value.trim() || '工作台提醒';
  body.skills_path = document.getElementById('set-skills-path').value.trim();
  body.activity_dirs = document.getElementById('set-activity-dirs').value.trim();
  body.port = document.getElementById('set-port').value.trim() || '8789';
  await api('/api/settings', { method: 'POST', body: JSON.stringify(body) });
  document.getElementById('set-token').value = '';
  document.getElementById('set-pushdeer').value = '';
  document.getElementById('set-bark').value = '';
  document.getElementById('set-deepseek').value = '';
  toast('已保存（改端口需重启）');
  loadSettings();
}

async function testReminder() {
  try {
    await api('/api/reminders/test', { method: 'POST' });
    toast('测试消息已发送，看手机通知');
  } catch (e) {
    toast(e.message, 'err');
  }
}

/* ---------------- 初始化 ---------------- */

document.querySelectorAll('.tab').forEach((b) =>
  b.addEventListener('click', () => go(b.dataset.tab)),
);

document.getElementById('log-date').addEventListener('change', loadLogs);
document.getElementById('todo-filter-status').addEventListener('change', loadTodos);
document.getElementById('todo-filter-overdue').addEventListener('change', loadTodos);
document.getElementById('imp-filter').addEventListener('change', loadImprovements);

async function init() {
  const health = await api('/api/health').catch(() => null);
  document.getElementById('health-dot').classList.add('ok');
  go('home');
}

init();