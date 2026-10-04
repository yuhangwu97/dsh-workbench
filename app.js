const pageLabels = { overview: '概览', chat: 'Chat', tasks: '任务', skills: 'Skills', knowledge: '知识库', workflows: '工作流', runs: '运行记录', approvals: '审批', packs: '场景包', artifacts: '产物' }
const uiPackColors = { 'after-sales': 'pack-green', engineering: 'pack-blue', operations: 'pack-orange' }
const uiSkillColors = { 'after-sales': 'glyph-green', engineering: 'glyph-blue', operations: 'glyph-orange' }
const statusClasses = { running: 'state-progress', review: 'state-review', approval: 'state-warning', waiting_approval: 'state-warning', completed: 'state-done', failed: 'state-warning', cancelled: 'state-review', rejected: 'state-review', queued: 'state-review' }
let packs = []
let skills = []
const taskStore = {}
const navItems = [...document.querySelectorAll('[data-page]')]
const sections = [...document.querySelectorAll('[data-view]')]
const breadcrumb = document.querySelector('#breadcrumb-current')
const taskDrawer = document.querySelector('.task-drawer')
const taskModal = document.querySelector('#new-task-modal')
const skillModal = document.querySelector('#skill-run-modal')
const authModal = document.querySelector('#auth-modal')
let apiOnline = false
let activeTaskId = null
let activeWorkflowId = null
const tenantId = localStorage.getItem('dsh-tenant-id') || 'tenant-demo'
const actorId = localStorage.getItem('dsh-actor-id') || 'user-wu-yuhang'
let authToken = localStorage.getItem('dsh-auth-token') || ''

function packFor(id) { return packs.find(item => item.id === id) || { id, name: id || '未知场景包', description: '', color: 'gray', skills: 0, workflows: 0, knowledge_bases: 0 } }
function skillFor(id) { return skills.find(item => item.id === id) || { id, name: id || '未知 Skill', description: '', pack_id: '', version: '', dependencies: [] } }
function packColor(id) { return uiPackColors[id] || 'pack-gray' }
function skillColor(packId) { return uiSkillColors[packId] || 'glyph-gray' }
function setText(selector, value) { const node = document.querySelector(selector); if (node) node.textContent = value }

async function apiRequest(path, options = {}) {
  const { headers: customHeaders = {}, ...requestOptions } = options
  const response = await fetch(path, { ...requestOptions, headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': tenantId, 'X-Actor-ID': actorId, ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}), ...customHeaders } })
  if (!response.ok) { const error = new Error(`${response.status} ${response.statusText}`); error.status = response.status; throw error }
  return response.json()
}
function requestAuth() { if (!authModal?.open) authModal?.showModal(); authModal?.querySelector('#auth-token')?.focus() }
function normalizeTask(raw) {
  const pack = packFor(raw.pack_id)
  const skill = skillFor(raw.skill_id)
  return { ...raw, pack: raw.pack_id, title: raw.name, skill: skill.name, state: raw.status_label || '待运行', stateClass: statusClasses[raw.status] || 'state-review', copy: raw.copy || pack.description || '任务已创建，等待执行。' }
}
function taskInput(raw) {
  return raw?.input_snapshot || raw?.input || '尚未提供额外输入。'
}
function showToast(message) {
  const region = document.querySelector('.toast-region')
  const toast = document.createElement('div')
  toast.className = 'toast'; toast.textContent = message; region.append(toast)
  window.setTimeout(() => toast.remove(), 3200)
}
function setPage(page) {
  const target = pageLabels[page] ? page : 'overview'
  navItems.forEach(item => item.classList.toggle('active', item.dataset.page === target))
  sections.forEach(section => section.classList.toggle('active', section.dataset.view === target))
  breadcrumb.textContent = pageLabels[target]
  window.history.replaceState(null, '', `#${target}`)
  window.scrollTo({ top: 0, behavior: 'smooth' })
  closeTask()
}
navItems.forEach(item => item.addEventListener('click', () => setPage(item.dataset.page)))
document.querySelectorAll('[data-page-link]').forEach(item => item.addEventListener('click', () => setPage(item.dataset.pageLink)))

function bindTaskTrigger(element) { element.addEventListener('click', () => openTask(element.dataset.task)) }
function renderDrawerDetail(detail) {
  const runs = detail?.runs || []
  const artifacts = detail?.artifacts || []
  const trace = document.querySelector('.run-trace')
  if (trace) {
    trace.replaceChildren()
    const steps = [
      ['提交运行请求', runs.length ? '完成' : '等待'],
      ['调用 DSH Runtime', runs[0]?.status === 'running' ? '进行中' : runs[0]?.status === 'completed' ? '完成' : '等待'],
      ['生成结构化结果', runs[0]?.status === 'completed' ? '完成' : '等待']
    ]
    steps.forEach(([label, state], index) => {
      const row = document.createElement('div'); const dot = document.createElement('span'); dot.className = `trace-dot ${state === '完成' ? 'done' : state === '进行中' ? 'active' : ''}`
      const name = document.createElement('span'); name.textContent = label
      const status = document.createElement('small'); status.textContent = state
      row.append(dot, name, status); trace.append(row)
    })
  }
  const artifactList = document.querySelector('.artifact-list')
  if (artifactList) {
    artifactList.replaceChildren()
    if (!artifacts.length) { const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = '运行完成后，结构化结果和证据包会出现在这里。'; artifactList.append(empty) }
    artifacts.forEach(item => { const row = document.createElement('div'); const name = document.createElement('strong'); name.textContent = item.name; const desc = document.createElement('span'); desc.textContent = item.description || item.type; row.append(name, desc); artifactList.append(row) })
  }
}
async function openTask(key) {
  let task = taskStore[key]
  if (!task) { showToast(apiOnline ? '任务数据不存在' : '当前离线，无法读取任务详情'); return }
  let detail = null
  if (apiOnline && typeof key === 'string' && key.startsWith('TK-')) {
    try { detail = await apiRequest(`/api/v1/tasks/${encodeURIComponent(key)}`); task = normalizeTask(detail.task); taskStore[key] = task } catch (error) { console.info('Could not load task detail', error) }
  }
  activeTaskId = task.id
  const pack = packFor(task.pack)
  document.querySelector('#drawer-title').textContent = task.title || pack.title
  document.querySelector('#drawer-state').textContent = task.state || '待运行'
  document.querySelector('#drawer-state').className = `state-pill ${task.stateClass || 'state-review'}`
  document.querySelector('.drawer-id').textContent = task.id
  document.querySelector('#drawer-pack').textContent = pack.name
  document.querySelector('#drawer-pack-dot').className = `pack-color ${packColor(task.pack)}`
  document.querySelector('#drawer-skill').textContent = task.skill || '—'
  document.querySelector('#drawer-copy').textContent = task.copy || pack.description || '—'
  const approveButton = taskDrawer.querySelector('[data-action="approve"]')
  if (approveButton) approveButton.hidden = !['approval', 'waiting_approval'].includes(task.status)
  const inputPreview = document.querySelector('#drawer-input')
  if (inputPreview) { inputPreview.replaceChildren(); const value = document.createElement('p'); value.textContent = taskInput(task); inputPreview.append(value) }
  if (detail) renderDrawerDetail(detail)
  setDrawerTab('overview')
  taskDrawer.classList.add('open'); taskDrawer.setAttribute('aria-hidden', 'false')
  document.querySelector('.close-drawer')?.focus({ preventScroll: true })
}
function closeTask() { taskDrawer.classList.remove('open'); taskDrawer.setAttribute('aria-hidden', 'true') }
document.querySelectorAll('[data-task]').forEach(bindTaskTrigger)
document.querySelectorAll('[data-close-drawer]').forEach(item => item.addEventListener('click', closeTask))
document.addEventListener('keydown', event => { if (event.key === 'Escape') { closeTask(); skillModal?.close(); taskModal?.close(); authModal?.close() } })

function setDrawerTab(tab) {
  document.querySelectorAll('[data-drawer-tab]').forEach(button => { const active = button.dataset.drawerTab === tab; button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active)) })
  document.querySelectorAll('[data-drawer-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.drawerPanel === tab))
}
document.querySelectorAll('[data-drawer-tab]').forEach(button => button.addEventListener('click', () => setDrawerTab(button.dataset.drawerTab)))

function renderTaskRows(serverTasks) {
  const tablePanel = document.querySelector('.table-panel')
  const tableHead = tablePanel.querySelector('.table-head')
  tablePanel.replaceChildren(tableHead)
  const inbox = document.querySelector('.task-list'); inbox.replaceChildren()
  if (!serverTasks.length) {
    const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = apiOnline ? '当前没有任务。' : '后端 API 不可用，任务列表未加载。'
    inbox.append(empty)
    const tableEmpty = document.createElement('p'); tableEmpty.className = 'drawer-copy'; tableEmpty.textContent = empty.textContent; tablePanel.append(tableEmpty)
    return
  }
  serverTasks.forEach(raw => {
    const task = normalizeTask(raw); taskStore[task.id] = task
    const pack = packFor(task.pack)
    const tableRow = document.createElement('button'); tableRow.className = 'table-row'; tableRow.type = 'button'; tableRow.dataset.task = task.id
    tableRow.innerHTML = `<span><strong>${task.title}</strong><small>${task.id}</small></span><span class="table-pack"><i class="pack-color ${packColor(task.pack)}"></i>${pack.name}</span><span class="state-pill ${task.stateClass}">${task.state}</span><span>${task.updated}</span><span>›</span>`
    tablePanel.append(tableRow); bindTaskTrigger(tableRow)
    const inboxRow = document.createElement('button'); inboxRow.className = 'task-row'; inboxRow.type = 'button'; inboxRow.dataset.task = task.id
    const statusClass = task.status === 'completed' ? 'status-done' : task.status === 'approval' || task.status === 'waiting_approval' || task.status === 'failed' ? 'status-warning' : task.status === 'review' || task.status === 'cancelled' ? 'status-review' : 'status-progress'
    inboxRow.innerHTML = `<span class="task-status ${statusClass}"></span><span class="task-main"><strong>${task.title}</strong><small>${pack.name} · ${task.skill}</small></span><span class="task-time">${task.updated}</span><span class="row-chevron">›</span>`
    inbox.append(inboxRow); bindTaskTrigger(inboxRow)
  })
}
function runLabel(status) {
  return { queued: '排队中', running: '运行中', completed: '已完成', waiting_approval: '等待审批', approval: '等待审批', failed: '失败', rejected: '已拒绝' }[status] || status
}
function renderRunRows(serverRuns) {
  const table = document.querySelector('.runs-table')
  if (!table) return
  const head = table.querySelector('.table-head'); table.replaceChildren(head)
  if (!serverRuns.length) { const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = apiOnline ? '当前没有运行记录。' : '后端 API 不可用，运行记录未加载。'; table.append(empty); return }
  serverRuns.forEach(run => {
    const row = document.createElement('button'); row.className = 'table-row'; row.type = 'button'
    const task = run.task_id ? taskStore[run.task_id] : null
    if (task) row.dataset.task = run.task_id
    const title = task?.title || (run.workflow_id ? `Workflow · ${run.workflow_id}` : run.skill_id || 'Skill Run')
    const skill = skillFor(run.skill_id).name || 'Workflow'
    const stateClass = statusClasses[run.status] || 'state-review'
    row.innerHTML = `<span><strong>${run.id}</strong><small>${title}</small></span><span>${skill}</span><span class="state-pill ${stateClass}">${runLabel(run.status)}</span><span>${run.duration || run.message || '刚刚'}</span><span>›</span>`
    table.append(row)
    if (task) bindTaskTrigger(row)
  })
}
function renderArtifactCards(artifactMap) {
  const grid = document.querySelector('.artifact-grid')
  if (!grid) return
  const artifacts = Object.entries(artifactMap || {}).flatMap(([taskId, items]) => items.map(item => ({ ...item, task_id: taskId })))
  grid.replaceChildren()
  if (!artifacts.length) { const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = '完成 Task 后，Artifact 会出现在这里。'; grid.append(empty); return }
  artifacts.forEach(item => {
    const card = document.createElement('article'); card.className = 'artifact-card'
    const icon = document.createElement('div'); icon.className = `artifact-icon ${item.type === 'evidence' ? 'artifact-icon-green' : item.type === 'plan' ? 'artifact-icon-blue' : ''}`; icon.textContent = String(item.type || 'FILE').slice(0, 5).toUpperCase()
    const body = document.createElement('div'); const title = document.createElement('h3'); title.textContent = item.name; const description = document.createElement('p'); description.textContent = `${taskStore[item.task_id]?.title || item.task_id} · ${item.description || item.type}`; const meta = document.createElement('span'); meta.textContent = `run ${item.run_id || '—'}`; body.append(title, description, meta)
    const open = document.createElement('button'); open.className = 'icon-button'; open.type = 'button'; open.textContent = '↓'; open.setAttribute('aria-label', `下载 ${item.name}`); open.addEventListener('click', () => { const blob = new Blob([JSON.stringify(item, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = item.name; link.click(); URL.revokeObjectURL(url) })
    card.append(icon, body, open); grid.append(card)
  })
}
function renderKnowledgeSources(sources) {
  const table = document.querySelector('.knowledge-table'); if (!table) return
  const head = table.querySelector('.table-head'); table.replaceChildren(head)
  ;(sources || []).forEach(source => {
    const row = document.createElement('button'); row.className = 'table-row'; row.type = 'button'; row.dataset.action = 'open-knowledge'
    const pack = packFor(source.pack_id)
    row.innerHTML = `<span><strong>${source.name || source.id}</strong><small>${source.id} · ${source.documents || 0} docs</small></span><span class="table-pack"><i class="pack-color ${packColor(source.pack_id)}"></i>${pack.name}</span><span>${source.documents || 0}</span><span class="state-pill ${source.status === 'ready' ? 'state-done' : 'state-review'}">${source.status === 'ready' ? '已就绪' : source.status || '索引中'}</span><span>›</span>`
    row.addEventListener('click', () => { setPage('knowledge'); showToast(`已打开知识源：${source.name || source.id}`) }); table.append(row)
  })
}
function renderWorkflowList(workflows) {
  const list = document.querySelector('.workflow-list'); if (!list) return
  const head = list.querySelector('.panel-heading'); list.replaceChildren(head)
  const items = workflows || []
  const count = list.querySelector('.evidence-count'); if (count) count.textContent = String(items.length)
  if (!items.length) { activeWorkflowId = null; const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = apiOnline ? '当前没有已注册工作流。' : '后端 API 不可用，工作流未加载。'; list.append(empty); renderWorkflowDetail(null); return }
  activeWorkflowId = items[0].id
  items.forEach(workflow => {
    const item = document.createElement('button'); item.className = 'workflow-item'; item.type = 'button'
    const pack = packFor(workflow.pack_id); const marker = packColor(workflow.pack_id).replace('pack-', 'mark-'); item.innerHTML = `<span class="workflow-mark ${marker}"></span><span><strong>${escapeHTML(workflow.name || workflow.id)}</strong><small>${workflow.steps || 0} steps · ${escapeHTML(workflow.status || 'draft')}</small></span><span>›</span>`
    item.addEventListener('click', () => { activeWorkflowId = workflow.id; renderWorkflowDetail(workflow); showToast(`已选择工作流：${workflow.name || workflow.id}`) }); list.append(item)
  })
  renderWorkflowDetail(items[0])
}
function renderWorkflowDetail(workflow) {
  const canvas = document.querySelector('.workflow-canvas'); if (!canvas) return
  const title = canvas.querySelector('.workflow-canvas-head h2'); const overline = canvas.querySelector('.workflow-canvas-head .overline'); const state = canvas.querySelector('#workflow-state'); const steps = canvas.querySelector('.workflow-steps'); const footer = canvas.querySelector('.workflow-footer')
  if (!workflow) { if (overline) overline.textContent = 'WORKFLOW'; if (title) title.textContent = '连接后显示流程'; if (state) { state.textContent = 'Offline'; state.className = 'state-pill state-review' }; if (steps) steps.replaceChildren(); if (footer) footer.replaceChildren(...['—', '—', '—'].map(value => { const node = document.createElement('span'); node.textContent = value; return node })); return }
  const pack = packFor(workflow.pack_id)
  if (overline) overline.textContent = pack.name || workflow.pack_id || 'WORKFLOW'
  if (title) title.textContent = workflow.name || workflow.id
  if (state) { state.textContent = workflow.status || 'draft'; state.className = `state-pill ${workflow.status === 'published' ? 'state-done' : 'state-review'}` }
  if (steps) {
    const labels = Array.isArray(workflow.step_labels) ? workflow.step_labels : []
    steps.replaceChildren()
    const count = Number(workflow.steps || labels.length || 0)
    for (let index = 0; index < count; index += 1) {
      if (index) { const connector = document.createElement('span'); connector.className = 'step-connector'; steps.append(connector) }
      const step = document.createElement('div'); step.className = 'workflow-step'; const number = document.createElement('span'); number.className = 'step-number'; number.textContent = String(index + 1); const body = document.createElement('div'); const strong = document.createElement('strong'); strong.textContent = labels[index] || `Step ${index + 1}`; const small = document.createElement('small'); small.textContent = workflow.id || 'manifest workflow'; body.append(strong, small); step.append(number, body); steps.append(step)
    }
  }
  if (footer) footer.replaceChildren(...[workflow.id || '—', `${workflow.steps || 0} steps`, workflow.status || 'draft'].map(value => { const node = document.createElement('span'); node.textContent = value; return node }))
}
function renderPackCards(items) {
  const grid = document.querySelector('.pack-grid'); if (!grid) return
  grid.replaceChildren()
  items.forEach((pack, index) => {
    const card = document.createElement('button'); card.className = `pack-card${index === 0 ? ' selected' : ''}`; card.type = 'button'; card.dataset.selectPack = pack.id
    card.innerHTML = `<div class="pack-card-top"><span class="pack-color ${packColor(pack.id)}"></span><span class="pack-status">${pack.status || 'enabled'}</span><span class="card-arrow">↗</span></div><h3>${escapeHTML(pack.name)}</h3><p>${escapeHTML(pack.description || '')}</p><div class="pack-meta"><span>${pack.skills || 0} Skills</span><span>${pack.workflows || 0} Workflows</span><span>${pack.version ? `v${escapeHTML(pack.version)}` : 'manifest'}</span></div>`
    card.addEventListener('click', () => { setActivePack(pack.id); showToast(`已切换场景包：${pack.name}`) }); grid.append(card)
  })
}
function renderPackLibrary(items) {
  const library = document.querySelector('.pack-library'); if (!library) return
  library.replaceChildren()
  items.forEach(pack => {
    const card = document.createElement('article'); card.className = `library-card library-card-${packColor(pack.id).replace('pack-', '')}`
    card.innerHTML = `<div class="library-accent"></div><div class="library-content"><div class="library-top"><span class="pack-color ${packColor(pack.id)}"></span><span>${escapeHTML(pack.status || 'enabled')}</span></div><h2>${escapeHTML(pack.name)}</h2><p>${escapeHTML(pack.description || '')}</p><div class="library-stats"><div><strong>${pack.skills || 0}</strong><span>Skills</span></div><div><strong>${pack.workflows || 0}</strong><span>Workflows</span></div><div><strong>${pack.knowledge_bases || 0}</strong><span>Knowledge bases</span></div></div><button class="secondary-button" data-select-pack="${escapeHTML(pack.id)}">打开场景包</button></div>`
    card.querySelector('[data-select-pack]')?.addEventListener('click', () => { setActivePack(pack.id); showToast(`已打开场景包：${pack.name}`) }); library.append(card)
  })
}
function renderSkillCards(items) {
  const grid = document.querySelector('.skill-grid'); if (!grid) return
  grid.replaceChildren()
  items.forEach(skill => {
    const card = document.createElement('article'); card.className = 'skill-card'; card.dataset.skillId = skill.id
    const pack = packFor(skill.pack_id)
    card.innerHTML = `<div class="skill-card-head"><span class="skill-glyph ${skillColor(skill.pack_id)}">◇</span><span class="verified">${escapeHTML(skill.trust || 'verified')}</span><button class="icon-button" type="button" aria-label="Skill menu">⋯</button></div><h3>${escapeHTML(skill.name)}</h3><p>${escapeHTML(skill.description || '')}</p><div class="skill-deps">${(skill.dependencies || []).map(item => `<span>${escapeHTML(item)}</span>`).join('')}</div><div class="skill-card-foot"><span>v${escapeHTML(skill.version || '—')} · ${escapeHTML(pack.status || 'enabled')}</span><button class="small-button" data-run-skill>试运行</button></div>`
    card.querySelector('[data-run-skill]')?.addEventListener('click', event => { event.stopPropagation(); openSkillRun(card) }); grid.append(card)
  })
}
function renderActivityList(runs) {
  const list = document.querySelector('.activity-list'); if (!list) return
  list.replaceChildren()
  runs.slice(0, 4).forEach(run => {
    const item = document.createElement('div'); item.className = 'activity-item'; const color = skillColor(skillFor(run.skill_id).pack_id).replace('glyph-', 'icon-')
    item.innerHTML = `<span class="activity-icon ${color}">${run.status === 'completed' ? '✓' : run.status === 'failed' ? '!' : '↗'}</span><div><strong>${escapeHTML(skillFor(run.skill_id).name || run.skill_id || 'Workflow')}</strong><p>${escapeHTML(runLabel(run.status))} · ${escapeHTML(run.message || run.duration || '—')}</p></div><time>${escapeHTML(run.created_at || '—')}</time>`; list.append(item)
  })
}
function renderCatalogControls() {
  const chatPack = document.querySelector('#chat-pack'); if (chatPack) { chatPack.replaceChildren(...packs.map(pack => new Option(pack.name, pack.id))) }
  const taskPack = document.querySelector('#new-task-pack'); if (taskPack) { taskPack.replaceChildren(...packs.map(pack => new Option(pack.name, pack.id))); renderTaskSkillOptions(taskPack.value) }
}
function renderTaskSkillOptions(packId) {
  const select = document.querySelector('#new-task-skill'); if (!select) return
  const options = skills.filter(skill => skill.pack_id === packId); select.replaceChildren(...options.map(skill => new Option(skill.name, skill.id)))
}
function clearDataViews() {
  document.querySelector('.pack-grid')?.replaceChildren(); document.querySelector('.task-list')?.replaceChildren(); document.querySelector('.activity-list')?.replaceChildren(); document.querySelector('.skill-grid')?.replaceChildren(); document.querySelector('.pack-library')?.replaceChildren(); document.querySelector('.artifact-grid')?.replaceChildren()
  for (const selector of ['.knowledge-table', '.workflow-list', '.runs-table']) { const node = document.querySelector(selector); if (node) { const head = node.querySelector('.table-head, .panel-heading'); node.replaceChildren(); if (head) node.append(head) } }
  document.querySelector('.approval-list')?.replaceChildren()
  Object.keys(taskStore).forEach(key => delete taskStore[key])
  activeWorkflowId = null
  const emptyState = (selector, message) => { const node = document.querySelector(selector); if (!node) return; const empty = document.createElement('p'); empty.className = 'drawer-copy offline-empty'; empty.textContent = message; node.append(empty) }
  emptyState('.pack-grid', 'Offline · 场景包目录未加载。'); emptyState('.task-list', 'Offline · 任务列表未加载。'); emptyState('.activity-list', 'Offline · 运行记录未加载。'); emptyState('.skill-grid', 'Offline · Skill 目录未加载。'); emptyState('.pack-library', 'Offline · 场景包目录未加载。'); emptyState('.artifact-grid', 'Offline · 产物目录未加载。'); emptyState('.knowledge-table', 'Offline · 知识源未加载。'); emptyState('.workflow-list', 'Offline · 工作流未加载。'); emptyState('.runs-table', 'Offline · 运行记录未加载。'); emptyState('.approval-list', 'Offline · 审批队列未加载。')
  renderWorkflowDetail(null)
}
function setApiAvailability(online) {
  apiOnline = online
  document.querySelectorAll('[data-requires-api]').forEach(node => { node.disabled = !online; node.title = online ? '' : '后端 API 不可用' })
  renderRuntime(online ? { mode: 'demo' } : { mode: 'unavailable', offline: true })
}
function escapeHTML(value) { return String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character])) }
function renderApprovalList(approvals) {
  const list = document.querySelector('.approval-list'); if (!list) return
  list.replaceChildren()
  if (!(approvals || []).length) { const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = '当前没有待处理审批。'; list.append(empty); return }
  approvals.forEach(approval => {
    const isToolApproval = approval.type === 'tool'
    const resourceId = isToolApproval ? approval.id : approval.task_id
    const resourceLabel = isToolApproval ? `Tool · ${approval.tool || approval.id}` : approval.task_id || approval.id
    const item = document.createElement('article'); item.className = 'approval-item'; item.innerHTML = `<div class="approval-item-head"><span class="state-pill ${approval.status === 'pending' ? 'state-warning' : 'state-done'}">${approval.status === 'pending' ? '待处理' : approval.status}</span></div><h3>${escapeHTML(resourceLabel)}</h3><p>${escapeHTML(approval.reason || (isToolApproval ? '工具调用需要人工确认' : '业务动作需要人工确认'))}</p>`
    if (approval.status === 'pending') {
      const actions = document.createElement('div'); actions.className = 'approval-actions'
      const reject = document.createElement('button'); reject.className = 'secondary-button'; reject.dataset.action = 'reject-approval'; reject.dataset.approvalTask = resourceId; reject.dataset.approvalType = isToolApproval ? 'tool' : 'task'; reject.textContent = '拒绝'
      const approve = document.createElement('button'); approve.className = 'primary-button'; approve.dataset.action = 'approve-approval'; approve.dataset.approvalTask = resourceId; approve.dataset.approvalType = isToolApproval ? 'tool' : 'task'; approve.textContent = '批准并继续'
      actions.append(reject, approve); item.append(actions)
      ;[reject, approve].forEach(button => button.addEventListener('click', async () => {
        const decision = button.dataset.action === 'approve-approval' ? 'approve' : 'reject';
        const route = isToolApproval ? `/api/v1/tool-approvals/${encodeURIComponent(resourceId)}/${decision}` : `/api/v1/approvals/${encodeURIComponent(resourceId)}/${decision}`
        try { await apiRequest(route, { method: 'POST', body: '{}' }); await bootstrapFromApi(); showToast(decision === 'approve' ? '审批已通过。' : '已拒绝本次业务动作。') } catch (error) { showToast('审批接口暂时不可用') }
      }))
    }
    list.append(item)
  })
}
function renderRuntime(runtime) {
  const environment = document.querySelector('.environment'); if (!environment) return
  const mode = runtime?.mode || 'unavailable'; const label = runtime?.offline ? 'Offline · API unavailable' : mode === 'native' ? 'Native Harness' : mode === 'sidecar' ? 'Harness Sidecar' : mode === 'demo' ? 'Demo runtime' : 'Harness unavailable'
  environment.innerHTML = `<span class="status-dot ${mode === 'unavailable' ? 'pack-orange' : 'dot-green'}"></span>${label}`
}

async function bootstrapFromApi() {
  try {
    const [dashboard, runtime, remotePacks, remoteSkills] = await Promise.all([apiRequest('/api/v1/dashboard'), apiRequest('/api/v1/runtime'), apiRequest('/api/v1/scenario-packs'), apiRequest('/api/v1/skills')])
    packs = Array.isArray(remotePacks) ? remotePacks : []
    skills = Array.isArray(remoteSkills) ? remoteSkills : []
    setApiAvailability(true)
    renderPackCards(packs); renderPackLibrary(packs); renderSkillCards(skills); renderCatalogControls()
    renderRuntime(runtime)
    renderTaskRows(dashboard.tasks || []); renderRunRows(dashboard.runs || []); renderActivityList(dashboard.runs || []); renderArtifactCards(dashboard.artifacts || {})
    renderKnowledgeSources(dashboard.knowledge); renderWorkflowList(dashboard.workflows); renderApprovalList([...(dashboard.approvals || []), ...(dashboard.tool_approvals || [])])
    const metricValues = document.querySelectorAll('.metric-value'); if (metricValues[0]) metricValues[0].textContent = dashboard.metrics?.open_tasks ?? '—'; if (metricValues[1]) metricValues[1].textContent = dashboard.metrics?.runs_week ?? dashboard.metrics?.runs_this_week ?? '—'; if (metricValues[2]) metricValues[2].innerHTML = `${dashboard.metrics?.completion_rate ?? '—'}<span class="metric-unit">%</span>`; if (metricValues[3]) metricValues[3].textContent = dashboard.metrics?.waiting_approval ?? '—'
    setText('[data-nav-count="tasks"]', dashboard.tasks?.length ?? 0); setText('[data-nav-count="skills"]', skills.length); setText('[data-nav-count="approvals"]', String((dashboard.approvals || []).filter(item => item.status === 'pending').length + (dashboard.tool_approvals || []).filter(item => item.status === 'pending').length)); setText('[data-filter-count="tasks"]', dashboard.tasks?.length ?? 0); setText('[data-filter-count="skills"]', skills.length); setText('[data-filter-count="knowledge"]', dashboard.knowledge?.length ?? 0)
    const approvalCount = document.querySelector('.approval-summary strong'); if (approvalCount) approvalCount.textContent = String((dashboard.approvals || []).filter(item => item.status === 'pending').length + (dashboard.tool_approvals || []).filter(item => item.status === 'pending').length)
  } catch (error) {
    if (error.status === 401) requestAuth()
    else { packs = []; skills = []; setApiAvailability(false); clearDataViews(); showToast('后端 API 不可用，当前处于离线状态'); console.info('API unavailable; dynamic data cleared', error) }
  }
}
let refreshTimer
function startLiveRefresh() {
  window.clearInterval(refreshTimer)
  refreshTimer = window.setInterval(() => { if (apiOnline && !document.hidden) bootstrapFromApi() }, 5000)
}

function openNewTask(prefill = '') { const input = taskModal.querySelector('#new-task-input'); input.value = prefill; taskModal.querySelector('#new-task-name').focus(); taskModal.showModal() }
document.querySelectorAll('[data-new-task]').forEach(item => item.addEventListener('click', () => openNewTask()))
document.querySelector('#new-task-pack')?.addEventListener('change', event => renderTaskSkillOptions(event.target.value))
document.querySelector('#new-task-form')?.addEventListener('submit', async event => {
  event.preventDefault()
  if (!apiOnline) { showToast('后端 API 不可用，无法创建任务'); return }
  const name = document.querySelector('#new-task-name').value.trim() || '未命名任务'
  const input = document.querySelector('#new-task-input').value.trim()
  const packKey = document.querySelector('#new-task-pack').value; const skillId = document.querySelector('#new-task-skill').value; const skill = skillFor(skillId).name
  let task
  try { task = normalizeTask(await apiRequest('/api/v1/tasks', { method: 'POST', body: JSON.stringify({ name, pack_id: packKey, skill_id: skillId, input }) })) } catch (error) { setApiAvailability(false); showToast('后端 API 不可用，任务未创建'); return }
  taskStore[task.id] = task; await bootstrapFromApi(); taskModal.close(); setPage('tasks'); showToast(`任务已创建：${name}`)
})
function insertTaskRows(key, task) {
  const pack = packFor(task.pack)
  const tableRow = document.createElement('button'); tableRow.className = 'table-row'; tableRow.type = 'button'; tableRow.dataset.task = key
  tableRow.innerHTML = `<span><strong>${task.title}</strong><small>${task.id}</small></span><span class="table-pack"><i class="pack-color ${packColor(task.pack)}"></i>${pack.name}</span><span class="state-pill ${task.stateClass || 'state-review'}">${task.state}</span><span>刚刚</span><span>›</span>`
  document.querySelector('.table-panel').append(tableRow); bindTaskTrigger(tableRow)
  const inboxRow = document.createElement('button'); inboxRow.className = 'task-row'; inboxRow.type = 'button'; inboxRow.dataset.task = key
  inboxRow.innerHTML = `<span class="task-status status-review"></span><span class="task-main"><strong>${task.title}</strong><small>${pack.name} · ${task.skill}</small></span><span class="task-time">刚刚</span><span class="row-chevron">›</span>`
  document.querySelector('.task-list').prepend(inboxRow); bindTaskTrigger(inboxRow)
}

function openSkillRun(button) { const card = button.closest('.skill-card'); const skill = skillFor(card?.dataset.skillId); document.querySelector('#skill-run-title').textContent = skill.name; document.querySelector('#skill-run-name').value = skill.id; skillModal.showModal() }
document.querySelectorAll('[data-run-skill]').forEach(item => item.addEventListener('click', event => { event.stopPropagation(); openSkillRun(item) }))
document.querySelector('#skill-run-form')?.addEventListener('submit', async event => {
  event.preventDefault(); const name = document.querySelector('#skill-run-name').value; const input = document.querySelector('#skill-run-input').value
  if (!apiOnline) { showToast('后端 API 不可用，无法运行 Skill'); return }
  try { await apiRequest('/api/v1/skill-runs', { method: 'POST', body: JSON.stringify({ skill_id: name, input }) }); skillModal.close(); showToast(`${skillFor(name).name} 已加入运行队列`) } catch (error) { setApiAvailability(false); showToast('后端 API 不可用，运行未提交') }
})
document.querySelector('#auth-form')?.addEventListener('submit', async event => {
  event.preventDefault()
  authToken = document.querySelector('#auth-token').value.trim()
  if (!authToken) return
  localStorage.setItem('dsh-auth-token', authToken)
  authModal.close()
  await bootstrapFromApi()
})

function setActivePack(packKey) {
  document.querySelectorAll('[data-select-pack]').forEach(card => card.classList.toggle('selected', card.dataset.selectPack === packKey))
  const pack = packFor(packKey); const activePack = document.querySelector('.active-pack'); if (!activePack) return
  activePack.querySelector('.pack-color').className = `pack-color ${packColor(pack.id)}`; activePack.querySelector('strong').textContent = pack.name
  activePack.querySelector('small').textContent = `${pack.workflows || 0} workflows · ${pack.skills || 0} skills`
  localStorage.setItem('dsh-active-pack', packKey)
}
document.querySelectorAll('[data-select-pack]').forEach(item => item.addEventListener('click', () => { setActivePack(item.dataset.selectPack); showToast(`已切换场景包：${packFor(item.dataset.selectPack).name}`) }))
document.querySelector('[data-pack-menu]')?.addEventListener('click', () => { setPage('packs'); showToast('已打开场景包库') })

function filterRows(input, selector) { const query = input.value.trim().toLowerCase(); document.querySelectorAll(selector).forEach(row => { row.hidden = query && !row.textContent.toLowerCase().includes(query) }) }
document.querySelector('[data-task-search]')?.addEventListener('input', event => filterRows(event.target, '.table-row'))
document.querySelector('[data-skill-search]')?.addEventListener('input', event => filterRows(event.target, '.skill-card'))
document.querySelectorAll('.filter-button').forEach(button => button.addEventListener('click', () => { button.parentElement.querySelectorAll('.filter-button').forEach(item => item.classList.remove('active')); button.classList.add('active') }))
document.querySelectorAll('[data-command-search]').forEach(item => item.addEventListener('click', () => { setPage('tasks'); const input = document.querySelector('[data-task-search]'); setTimeout(() => input?.focus(), 100) }))

document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', async () => {
  const action = button.dataset.action
  if (action === 'approve' || action === 'approve-approval') {
    const approvalTaskId = activeTaskId || button.dataset.approvalTask
    if (apiOnline && approvalTaskId) { try { await apiRequest(`/api/v1/approvals/${encodeURIComponent(approvalTaskId)}/approve`, { method: 'POST', body: '{}' }); await bootstrapFromApi(); showToast('审批已通过，任务进入运行队列。') } catch (error) { showToast('审批接口暂时不可用') } } else { showToast('后端 API 不可用，审批未提交。'); return }
    closeTask(); setPage('approvals')
  }
  if (action === 'reject-approval') {
    const approvalTaskId = button.dataset.approvalTask || activeTaskId
    if (apiOnline && approvalTaskId) { try { await apiRequest(`/api/v1/approvals/${encodeURIComponent(approvalTaskId)}/reject`, { method: 'POST', body: '{}' }); await bootstrapFromApi(); showToast('已拒绝本次业务动作。') } catch (error) { showToast('拒绝接口暂时不可用'); return } } else showToast('已拒绝本次业务动作。')
    setPage('approvals')
  }
  if (action === 'open-task') { closeTask(); setPage('tasks') }
  if (action === 'new-task') {
    const fromChat = button.dataset.fromChat === 'true'
    const latestUserMessage = [...document.querySelectorAll('#chat-messages .message-user p')].at(-1)?.textContent || ''
    openNewTask(fromChat ? latestUserMessage : '')
  }
  if (action === 'run-task') {
    if (!activeTaskId) { showToast('请先选择一个 Task'); return }
    if (apiOnline) {
      try {
        await apiRequest(`/api/v1/tasks/${encodeURIComponent(activeTaskId)}/runs`, { method: 'POST', body: '{}' })
        showToast('Task 已进入运行队列，结果会自动回写到 Artifact。')
        window.setTimeout(async () => {
          try { const detail = await apiRequest(`/api/v1/tasks/${encodeURIComponent(activeTaskId)}`); const task = normalizeTask(detail.task); taskStore[activeTaskId] = task; document.querySelector('#drawer-state').textContent = task.state; document.querySelector('#drawer-state').className = `state-pill ${task.stateClass}`; document.querySelector('#drawer-copy').textContent = task.copy; const inputPreview = document.querySelector('#drawer-input'); if (inputPreview) { inputPreview.replaceChildren(); const value = document.createElement('p'); value.textContent = taskInput(task); inputPreview.append(value) }; renderDrawerDetail(detail); await bootstrapFromApi() } catch (error) { console.info('Could not refresh task detail', error) }
        }, 1000)
      } catch (error) { showToast('Task 运行接口暂时不可用') }
    } else showToast('后端 API 不可用，Task 未运行')
  }
  if (action === 'open-knowledge') { setPage('knowledge'); showToast('已打开证据源目录') }
  if (action === 'new-knowledge') showToast('资料上传已准备，下一步接入解析和索引任务。')
  if (action === 'new-workflow') showToast('工作流编辑器已准备，下一步接入节点编排。')
  if (action === 'run-workflow') {
    if (apiOnline && activeWorkflowId) { try { await apiRequest(`/api/v1/workflows/${encodeURIComponent(activeWorkflowId)}/runs`, { method: 'POST', body: '{}' }); showToast('工作流已加入运行队列。') } catch (error) { showToast('Workflow 接口暂时不可用') } }
    else showToast('后端 API 不可用或尚未选择工作流，Workflow 未运行')
  }
  if (action === 'new-skill') showToast('Skill 创建流程已准备，下一步接入 Manifest 和评测用例。')
  if (action === 'import-pack') showToast('场景包导入已准备，下一步接入 manifest.yaml 校验。')
  if (action === 'export-runs' || action === 'export-artifacts') showToast('导出任务已准备，下一步生成 CSV / JSON 文件。')
}))

function updateEvidence(matches = []) {
  const list = document.querySelector('.evidence-list'); if (!list) return
  const note = list.querySelector('.evidence-note') || document.createElement('div'); note.className = 'evidence-note'; note.innerHTML = '<span class="status-dot dot-green"></span><p>证据会在 Task 和 Artifact 中保留引用。</p>'
  list.replaceChildren()
  if (!matches.length) { const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = '当前场景包没有找到可引用证据。'; list.append(empty, note); const count = document.querySelector('.evidence-count'); if (count) count.textContent = '0'; return }
  matches.forEach(item => { const button = document.createElement('button'); button.className = 'evidence-item'; button.type = 'button'; button.dataset.action = 'open-knowledge'; button.innerHTML = `<span class="evidence-type">${item.type}</span><span><strong>${item.title}</strong><small>${item.detail}</small></span><span>›</span>`; button.addEventListener('click', () => { setPage('knowledge'); showToast('已打开证据源目录') }); list.append(button) })
  list.append(note)
  const count = document.querySelector('.evidence-count'); if (count) count.textContent = String(matches.length)
}

document.querySelector('#chat-form')?.addEventListener('submit', async event => {
  event.preventDefault()
  const input = document.querySelector('#chat-input'); const message = input.value.trim()
  if (!message) return
  const messages = document.querySelector('#chat-messages')
  messages.insertAdjacentHTML('beforeend', `<div class="chat-message message-user"><div class="chat-avatar avatar-user">YW</div><div><p>${message.replace(/[<>]/g, '')}</p><small>刚刚</small></div></div>`)
  input.value = ''; messages.scrollTop = messages.scrollHeight
  let reply = '后端 API 不可用，消息未发送。'
  const packId = document.querySelector('#chat-pack').value
  if (apiOnline) { try {
    const result = await apiRequest('/api/v1/chat/messages', { method: 'POST', body: JSON.stringify({ message, pack_id: packId }) })
    updateEvidence(result.matches)
    reply = result.reply
  } catch (error) { reply = error.status === 503 ? '当前没有可用的 Harness runtime，请先配置运行时。' : '消息未发送，当前运行服务暂时不可用。' } }
  messages.insertAdjacentHTML('beforeend', `<div class="chat-message message-assistant"><div class="chat-avatar">D</div><div><p>${reply.replace(/[<>]/g, '')}</p><small>已记录上下文 · 已检索证据 · 可转为 Task</small></div></div>`)
  messages.scrollTop = messages.scrollHeight
})

const savedPack = localStorage.getItem('dsh-active-pack')
const initialPage = window.location.hash.slice(1); if (pageLabels[initialPage]) setPage(initialPage)
bootstrapFromApi().then(() => { if (savedPack && packs.some(pack => pack.id === savedPack)) setActivePack(savedPack); startLiveRefresh() })
