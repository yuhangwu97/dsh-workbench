const pageLabels = { overview: '概览', chat: 'Chat', tasks: '任务', skills: 'Skills', knowledge: '知识库', workflows: '工作流', runs: '运行记录', approvals: '审批', packs: '场景包', artifacts: '产物' }
const packData = {
  'after-sales': { name: '售后诊断', color: 'pack-green', skill: '设备故障诊断', title: '设备 #3021 故障诊断', state: '进行中', stateClass: 'state-progress', copy: '已找到 3 条相关历史案例，建议检查冷却泵电源和过滤器状态。' },
  engineering: { name: '研发助手', color: 'pack-blue', skill: 'Issue 调查', title: 'RemoteHelpDesk #1842', state: '待确认', stateClass: 'state-review', copy: '已整理代码上下文和复现路径，建议先确认 API 兼容性，再进入修改计划。' },
  operations: { name: '运营告警', color: 'pack-orange', skill: '告警处置', title: '支付服务 P95 延迟', state: '需审批', stateClass: 'state-warning', copy: '已聚合 4 条重复告警，影响支付 API。建议按照支付服务 Runbook 升级值班负责人。' }
}
const tasks = { diagnosis: { pack: 'after-sales', id: 'TK-20261004-0021' }, issue: { pack: 'engineering', id: 'TK-20261004-0018' }, alert: { pack: 'operations', id: 'TK-20261004-0016' }, report: { pack: 'after-sales', id: 'TK-20261003-0091' } }
const skillData = { '设备故障诊断': 'equipment-diagnosis', 'Issue 调查': 'issue-investigation', '告警处置': 'alert-triage', '故障码分析': 'equipment-diagnosis', '维修建议': 'equipment-diagnosis', '代码上下文分析': 'issue-investigation', '测试计划生成': 'issue-investigation', '告警聚合': 'alert-triage', 'Runbook 匹配': 'alert-triage' }
const statusClasses = { running: 'state-progress', review: 'state-review', approval: 'state-warning', waiting_approval: 'state-warning', completed: 'state-done', failed: 'state-warning', cancelled: 'state-review', rejected: 'state-review', queued: 'state-review' }
const skillOptions = { '售后诊断': ['设备故障诊断', '故障码分析', '维修建议'], '研发助手': ['Issue 调查', '代码上下文分析', '测试计划生成'], '运营告警': ['告警处置', '告警聚合', 'Runbook 匹配'] }
const navItems = [...document.querySelectorAll('[data-page]')]
const sections = [...document.querySelectorAll('[data-view]')]
const breadcrumb = document.querySelector('#breadcrumb-current')
const taskDrawer = document.querySelector('.task-drawer')
const taskModal = document.querySelector('#new-task-modal')
const skillModal = document.querySelector('#skill-run-modal')
const authModal = document.querySelector('#auth-modal')
let apiOnline = false
let activeTaskId = null
const tenantId = localStorage.getItem('dsh-tenant-id') || 'tenant-demo'
const actorId = localStorage.getItem('dsh-actor-id') || 'user-wu-yuhang'
let authToken = localStorage.getItem('dsh-auth-token') || ''

async function apiRequest(path, options = {}) {
  const { headers: customHeaders = {}, ...requestOptions } = options
  const response = await fetch(path, { ...requestOptions, headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': tenantId, 'X-Actor-ID': actorId, ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}), ...customHeaders } })
  if (!response.ok) { const error = new Error(`${response.status} ${response.statusText}`); error.status = response.status; throw error }
  return response.json()
}
function requestAuth() { if (!authModal?.open) authModal?.showModal(); authModal?.querySelector('#auth-token')?.focus() }
function normalizeTask(raw) {
  const pack = packData[raw.pack_id] || packData['after-sales']
  const skill = Object.entries(skillData).find(([, id]) => id === raw.skill_id)?.[0] || pack.skill
  return { ...raw, pack: raw.pack_id, title: raw.name, skill, state: raw.status_label || '待运行', stateClass: statusClasses[raw.status] || 'state-review', copy: raw.copy || pack.copy }
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
  let task = tasks[key] || tasks.diagnosis
  let detail = null
  if (apiOnline && typeof key === 'string' && key.startsWith('TK-')) {
    try { detail = await apiRequest(`/api/v1/tasks/${encodeURIComponent(key)}`); task = normalizeTask(detail.task); tasks[key] = task } catch (error) { console.info('Could not load task detail', error) }
  }
  activeTaskId = task.id
  const pack = packData[task.pack]
  document.querySelector('#drawer-title').textContent = task.title || pack.title
  document.querySelector('#drawer-state').textContent = task.state || pack.state
  document.querySelector('#drawer-state').className = `state-pill ${task.stateClass || pack.stateClass}`
  document.querySelector('.drawer-id').textContent = task.id
  document.querySelector('#drawer-pack').textContent = pack.name
  document.querySelector('#drawer-pack-dot').className = `pack-color ${pack.color}`
  document.querySelector('#drawer-skill').textContent = task.skill || pack.skill
  document.querySelector('#drawer-copy').textContent = task.copy || pack.copy
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
  serverTasks.forEach(raw => {
    const task = normalizeTask(raw); tasks[task.id] = task
    const pack = packData[task.pack]
    const tableRow = document.createElement('button'); tableRow.className = 'table-row'; tableRow.type = 'button'; tableRow.dataset.task = task.id
    tableRow.innerHTML = `<span><strong>${task.title}</strong><small>${task.id}</small></span><span class="table-pack"><i class="pack-color ${pack.color}"></i>${pack.name}</span><span class="state-pill ${task.stateClass}">${task.state}</span><span>${task.updated}</span><span>›</span>`
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
  serverRuns.forEach(run => {
    const row = document.createElement('button'); row.className = 'table-row'; row.type = 'button'
    const task = run.task_id ? tasks[run.task_id] : null
    if (task) row.dataset.task = run.task_id
    const title = task?.title || (run.workflow_id ? `Workflow · ${run.workflow_id}` : run.skill_id || 'Skill Run')
    const skill = Object.entries(skillData).find(([, id]) => id === run.skill_id)?.[0] || 'Workflow'
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
    const body = document.createElement('div'); const title = document.createElement('h3'); title.textContent = item.name; const description = document.createElement('p'); description.textContent = `${tasks[item.task_id]?.title || item.task_id} · ${item.description || item.type}`; const meta = document.createElement('span'); meta.textContent = `run ${item.run_id || 'seed'}`; body.append(title, description, meta)
    const open = document.createElement('button'); open.className = 'icon-button'; open.type = 'button'; open.textContent = '↓'; open.setAttribute('aria-label', `下载 ${item.name}`); open.addEventListener('click', () => { const blob = new Blob([JSON.stringify(item, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = item.name; link.click(); URL.revokeObjectURL(url) })
    card.append(icon, body, open); grid.append(card)
  })
}
function renderKnowledgeSources(sources) {
  const table = document.querySelector('.knowledge-table'); if (!table) return
  const head = table.querySelector('.table-head'); table.replaceChildren(head)
  ;(sources || []).forEach(source => {
    const row = document.createElement('button'); row.className = 'table-row'; row.type = 'button'; row.dataset.action = 'open-knowledge'
    const pack = packData[source.pack_id] || packData['after-sales']
    row.innerHTML = `<span><strong>${source.name || source.id}</strong><small>${source.id} · ${source.documents || 0} docs</small></span><span class="table-pack"><i class="pack-color ${pack.color}"></i>${pack.name}</span><span>${source.documents || 0}</span><span class="state-pill ${source.status === 'ready' ? 'state-done' : 'state-review'}">${source.status === 'ready' ? '已就绪' : source.status || '索引中'}</span><span>›</span>`
    row.addEventListener('click', () => { setPage('knowledge'); showToast(`已打开知识源：${source.name || source.id}`) }); table.append(row)
  })
}
function renderWorkflowList(workflows) {
  const list = document.querySelector('.workflow-list'); if (!list) return
  const head = list.querySelector('.panel-heading'); list.replaceChildren(head)
  ;(workflows || []).forEach(workflow => {
    const item = document.createElement('button'); item.className = 'workflow-item'; item.type = 'button'
    const pack = packData[workflow.pack_id] || packData['after-sales']; item.innerHTML = `<span class="workflow-mark ${pack.color === 'pack-green' ? 'mark-green' : pack.color === 'pack-blue' ? 'mark-blue' : 'mark-orange'}"></span><span><strong>${workflow.name || workflow.id}</strong><small>${workflow.steps || 0} steps · ${workflow.status || 'draft'}</small></span><span>›</span>`
    item.addEventListener('click', () => showToast(`已选择工作流：${workflow.name || workflow.id}`)); list.append(item)
  })
}
function renderApprovalList(approvals) {
  const list = document.querySelector('.approval-list'); if (!list) return
  list.replaceChildren()
  if (!(approvals || []).length) { const empty = document.createElement('p'); empty.className = 'drawer-copy'; empty.textContent = '当前没有待处理审批。'; list.append(empty); return }
  approvals.forEach(approval => {
    const item = document.createElement('article'); item.className = 'approval-item'; item.innerHTML = `<div class="approval-item-head"><span class="state-pill ${approval.status === 'pending' ? 'state-warning' : 'state-done'}">${approval.status === 'pending' ? '待处理' : approval.status}</span></div><h3>${approval.task_id || approval.id}</h3><p>${approval.reason || '业务动作需要人工确认'}</p>`
    if (approval.status === 'pending') {
      const actions = document.createElement('div'); actions.className = 'approval-actions'
      const reject = document.createElement('button'); reject.className = 'secondary-button'; reject.dataset.action = 'reject-approval'; reject.dataset.approvalTask = approval.task_id; reject.textContent = '拒绝'
      const approve = document.createElement('button'); approve.className = 'primary-button'; approve.dataset.action = 'approve-approval'; approve.dataset.approvalTask = approval.task_id; approve.textContent = '批准并继续'
      actions.append(reject, approve); item.append(actions)
      ;[reject, approve].forEach(button => button.addEventListener('click', async () => {
        const decision = button.dataset.action === 'approve-approval' ? 'approve' : 'reject';
        try { await apiRequest(`/api/v1/approvals/${encodeURIComponent(approval.task_id)}/${decision}`, { method: 'POST', body: '{}' }); await bootstrapFromApi(); showToast(decision === 'approve' ? '审批已通过。' : '已拒绝本次业务动作。') } catch (error) { showToast('审批接口暂时不可用') }
      }))
    }
    list.append(item)
  })
}
function renderRuntime(runtime) {
  const environment = document.querySelector('.environment'); if (!environment) return
  const mode = runtime?.mode || 'unavailable'; const label = mode === 'native' ? 'Native Harness' : mode === 'sidecar' ? 'Harness Sidecar' : mode === 'demo' ? 'Demo runtime' : 'Harness unavailable'
  environment.innerHTML = `<span class="status-dot ${mode === 'unavailable' ? 'pack-orange' : 'dot-green'}"></span>${label}`
}

async function bootstrapFromApi() {
  try {
    const [dashboard, runtime] = await Promise.all([apiRequest('/api/v1/dashboard'), apiRequest('/api/v1/runtime')])
    apiOnline = true
    renderRuntime(runtime)
    renderTaskRows(dashboard.tasks); renderRunRows(dashboard.runs); renderArtifactCards(dashboard.artifacts)
    renderKnowledgeSources(dashboard.knowledge); renderWorkflowList(dashboard.workflows); renderApprovalList(dashboard.approvals)
    document.querySelectorAll('.metric-value')[0].textContent = dashboard.metrics.open_tasks
    document.querySelectorAll('.metric-value')[2].innerHTML = `${dashboard.metrics.completion_rate}<span class="metric-unit">%</span>`
    document.querySelectorAll('.metric-value')[3].textContent = dashboard.metrics.waiting_approval
    const approvalCount = document.querySelector('.approval-summary strong'); if (approvalCount) approvalCount.textContent = String((dashboard.approvals || []).filter(item => item.status === 'pending').length)
  } catch (error) {
    if (error.status === 401) requestAuth()
    else { apiOnline = false; renderRuntime({ mode: 'unavailable' }); console.info('API unavailable; using local fixture', error) }
  }
}
let refreshTimer
function startLiveRefresh() {
  window.clearInterval(refreshTimer)
  refreshTimer = window.setInterval(() => { if (apiOnline && !document.hidden) bootstrapFromApi() }, 5000)
}

function openNewTask(prefill = '') { const input = taskModal.querySelector('#new-task-input'); input.value = prefill; taskModal.querySelector('#new-task-name').focus(); taskModal.showModal() }
document.querySelectorAll('[data-new-task]').forEach(item => item.addEventListener('click', () => openNewTask()))
document.querySelector('#new-task-pack')?.addEventListener('change', event => { const select = document.querySelector('#new-task-skill'); select.replaceChildren(...skillOptions[event.target.value].map(name => new Option(name, name))) })
document.querySelector('#new-task-form')?.addEventListener('submit', async event => {
  event.preventDefault()
  const name = document.querySelector('#new-task-name').value.trim() || '未命名任务'
  const input = document.querySelector('#new-task-input').value.trim()
  const packName = document.querySelector('#new-task-pack').value; const skill = document.querySelector('#new-task-skill').value
  const packKey = Object.keys(packData).find(key => packData[key].name === packName) || 'after-sales'; const skillId = skillData[skill] || 'equipment-diagnosis'
  let task
  if (apiOnline) { try { task = normalizeTask(await apiRequest('/api/v1/tasks', { method: 'POST', body: JSON.stringify({ name, pack_id: packKey, skill_id: skillId, input }) })) } catch (error) { apiOnline = false; showToast('接口暂时不可用，已使用本地任务记录') } }
  if (!task) { const id = `TK-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${String(Object.keys(tasks).length + 1).padStart(4, '0')}`; task = { pack: packKey, id, title: name, skill, input_snapshot: input, state: '待运行', stateClass: 'state-review', status: 'queued', copy: '任务已创建，等待执行 Skill 和 Workflow。', updated: '刚刚' } }
  tasks[task.id] = task; insertTaskRows(task.id, task); taskModal.close(); setPage('tasks'); showToast(`任务已创建：${name}`)
})
function insertTaskRows(key, task) {
  const pack = packData[task.pack]
  const tableRow = document.createElement('button'); tableRow.className = 'table-row'; tableRow.type = 'button'; tableRow.dataset.task = key
  tableRow.innerHTML = `<span><strong>${task.title}</strong><small>${task.id}</small></span><span class="table-pack"><i class="pack-color ${pack.color}"></i>${pack.name}</span><span class="state-pill ${task.stateClass || 'state-review'}">${task.state}</span><span>刚刚</span><span>›</span>`
  document.querySelector('.table-panel').append(tableRow); bindTaskTrigger(tableRow)
  const inboxRow = document.createElement('button'); inboxRow.className = 'task-row'; inboxRow.type = 'button'; inboxRow.dataset.task = key
  inboxRow.innerHTML = `<span class="task-status status-review"></span><span class="task-main"><strong>${task.title}</strong><small>${pack.name} · ${task.skill}</small></span><span class="task-time">刚刚</span><span class="row-chevron">›</span>`
  document.querySelector('.task-list').prepend(inboxRow); bindTaskTrigger(inboxRow)
}

function openSkillRun(button) { const card = button.closest('.skill-card'); const skillName = card?.querySelector('h3')?.textContent || '设备故障诊断'; document.querySelector('#skill-run-title').textContent = skillName; document.querySelector('#skill-run-name').value = skillName; skillModal.showModal() }
document.querySelectorAll('[data-run-skill]').forEach(item => item.addEventListener('click', event => { event.stopPropagation(); openSkillRun(item) }))
document.querySelector('#skill-run-form')?.addEventListener('submit', async event => {
  event.preventDefault(); const name = document.querySelector('#skill-run-name').value; const input = document.querySelector('#skill-run-input').value
  let queued = !apiOnline
  if (apiOnline) { try { await apiRequest('/api/v1/skill-runs', { method: 'POST', body: JSON.stringify({ skill_id: skillData[name] || 'equipment-diagnosis', input }) }); queued = true } catch (error) { showToast('运行队列接口暂时不可用') } }
  skillModal.close(); if (queued) showToast(`${name} 已加入运行队列`)
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
  const pack = packData[packKey]; const activePack = document.querySelector('.active-pack'); activePack.querySelector('.pack-color').className = `pack-color ${pack.color}`; activePack.querySelector('strong').textContent = pack.name
  activePack.querySelector('small').textContent = pack.name === '售后诊断' ? '3 workflows · 8 skills' : pack.name === '研发助手' ? '4 workflows · 6 skills' : '2 workflows · 5 skills'
  localStorage.setItem('dsh-active-pack', packKey)
}
document.querySelectorAll('[data-select-pack]').forEach(item => item.addEventListener('click', () => { setActivePack(item.dataset.selectPack); showToast(`已切换场景包：${packData[item.dataset.selectPack].name}`) }))
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
    if (apiOnline && approvalTaskId) { try { await apiRequest(`/api/v1/approvals/${encodeURIComponent(approvalTaskId)}/approve`, { method: 'POST', body: '{}' }); await bootstrapFromApi(); showToast('审批已通过，任务进入运行队列。') } catch (error) { showToast('审批接口暂时不可用') } } else showToast('审批已记录，任务进入运行队列。')
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
          try { const detail = await apiRequest(`/api/v1/tasks/${encodeURIComponent(activeTaskId)}`); const task = normalizeTask(detail.task); tasks[activeTaskId] = task; document.querySelector('#drawer-state').textContent = task.state; document.querySelector('#drawer-state').className = `state-pill ${task.stateClass}`; document.querySelector('#drawer-copy').textContent = task.copy; const inputPreview = document.querySelector('#drawer-input'); if (inputPreview) { inputPreview.replaceChildren(); const value = document.createElement('p'); value.textContent = taskInput(task); inputPreview.append(value) }; renderDrawerDetail(detail); await bootstrapFromApi() } catch (error) { console.info('Could not refresh task detail', error) }
        }, 1000)
      } catch (error) { showToast('Task 运行接口暂时不可用') }
    } else showToast('Task 已加入本地运行队列')
  }
  if (action === 'open-knowledge') { setPage('knowledge'); showToast('已打开证据源目录') }
  if (action === 'new-knowledge') showToast('资料上传已准备，下一步接入解析和索引任务。')
  if (action === 'new-workflow') showToast('工作流编辑器已准备，下一步接入节点编排。')
  if (action === 'run-workflow') {
    if (apiOnline) { try { await apiRequest('/api/v1/workflows/diagnose-equipment-v2/runs', { method: 'POST', body: '{}' }); showToast('工作流运行已加入队列：售后诊断 v2') } catch (error) { showToast('Workflow 接口暂时不可用') } }
    else showToast('工作流运行已加入本地队列：售后诊断 v2')
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
  let reply = '我已经收到这个问题。可以继续检索证据，或将当前会话转为 Task。'
  const packId = document.querySelector('#chat-pack').value
  if (apiOnline) { try {
    const result = await apiRequest('/api/v1/chat/messages', { method: 'POST', body: JSON.stringify({ message, pack_id: packId }) })
    updateEvidence(result.matches)
    reply = result.reply
  } catch (error) { reply = error.status === 503 ? '当前没有可用的 Harness runtime，请先配置运行时。' : '消息已记录，但当前运行服务暂时不可用。' } }
  messages.insertAdjacentHTML('beforeend', `<div class="chat-message message-assistant"><div class="chat-avatar">D</div><div><p>${reply.replace(/[<>]/g, '')}</p><small>已记录上下文 · 已检索证据 · 可转为 Task</small></div></div>`)
  messages.scrollTop = messages.scrollHeight
})

const savedPack = localStorage.getItem('dsh-active-pack'); if (savedPack && packData[savedPack]) setActivePack(savedPack)
const initialPage = window.location.hash.slice(1); if (pageLabels[initialPage]) setPage(initialPage)
bootstrapFromApi().then(startLiveRefresh)
