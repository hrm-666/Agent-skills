# Mini Agent WebUI 重新设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 根据设计规范重新实现 Mini Agent 的 WebUI，采用极简专业风格（类似 Linear、Vercel），右侧边栏布局，暖灰配色系统，响应式可折叠抽屉。

**Architecture:** 单文件 HTML 架构，使用 Tailwind CDN + 原生 JavaScript。保持现有 API 接口不变（/api/chat, /api/upload, /api/providers）。桌面端左右分栏（60:40），移动端底部抽屉。所有样式和脚本内联在 HTML 中。

**Tech Stack:** HTML5, Tailwind CSS (CDN), Vanilla JavaScript, Material Symbols Icons

---

## 文件结构

**修改文件：**
- `webui/index.html` - 完全重写，应用新设计系统

**参考文件：**
- `docs/superpowers/specs/2026-04-22-webui-redesign-design.md` - 设计规范
- 现有 `webui/index.html` - 保留 JavaScript 逻辑和 API 调用

**保持不变：**
- 后端 API 接口
- 请求流程（先上传附件，再发送消息）
- Provider 管理逻辑

---

## Task 1: 设置 Tailwind 配置和基础样式

**Files:**
- Modify: `webui/index.html:1-100`

- [ ] **Step 1: 创建 HTML 头部和 Tailwind 配置**

创建新的 index.html，设置暖灰配色系统：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Mini Agent</title>
  <script src="https://cdn.tailwindcss.com?plugins=forms"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined&display=swap" rel="stylesheet" />
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            'warm-bg': '#fafaf9',
            'warm-surface': '#f5f5f4',
            'warm-border': '#e7e5e4',
            'text-primary': '#0f172a',
            'text-secondary': '#78716c',
            'success': '#059669',
            'error': '#dc2626',
          },
          fontFamily: {
            sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
          },
        },
      },
    };
  </script>
  <style>
    body { font-family: 'Inter', sans-serif; }
    .material-symbols-outlined { font-size: 20px; }
    .conversation-scroll::-webkit-scrollbar,
    .tool-scroll::-webkit-scrollbar { width: 8px; }
    .conversation-scroll::-webkit-scrollbar-thumb,
    .tool-scroll::-webkit-scrollbar-thumb {
      background: #e7e5e4;
      border-radius: 9999px;
    }
  </style>
</head>
```

- [ ] **Step 3: 测试移动端响应式**

在浏览器中调整窗口大小到 <768px，检查：
- 工具面板在桌面端显示，移动端隐藏
- 浮动按钮在移动端显示
- 点击浮动按钮打开抽屉
- 抽屉从底部滑出，带背景遮罩
- 点击遮罩关闭抽屉
- 工具步骤在抽屉中正确显示

Expected: 移动端响应式布局正常工作

- [ ] **Step 4: 提交移动端响应式**

```bash
git add webui/index.html
git commit -m "feat: implement mobile responsive layout

- Add bottom drawer for tool panel on mobile
- Add floating action button to toggle drawer
- Add backdrop overlay with click-to-close
- Sync tool steps between desktop and mobile views
- Hide/show elements based on screen size

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: 优化样式细节和微交互

**Files:**
- Modify: `webui/index.html` (refine styles and add transitions)

- [ ] **Step 1: 添加微交互样式**

在 `<style>` 标签中添加：

```css
/* 按钮微交互 */
button:not(:disabled):hover {
  transform: scale(0.98);
}

button:not(:disabled):active {
  transform: scale(0.95);
}

button {
  transition: transform 150ms ease-out, background-color 150ms ease-out;
}

/* 输入框焦点效果 */
textarea:focus,
select:focus {
  outline: none;
  ring: 2px;
  ring-color: #0f172a;
}

/* 消息气泡动画 */
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-bubble {
  animation: slideIn 200ms ease-out;
}

/* 加载动画 */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.loading-dots span {
  animation: pulse 1.5s ease-in-out infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}
```

- [ ] **Step 2: 应用动画类到消息气泡**

修改 `appendMessage` 函数中的 wrapper 类名：

```javascript
wrapper.className = (role === 'user' ? 'flex justify-end' : 'flex justify-start') + ' message-bubble';
```

- [ ] **Step 3: 测试微交互**

在浏览器中测试：
- 按钮 hover 时轻微缩小
- 按钮 active 时更明显缩小
- 输入框 focus 时显示边框
- 新消息出现时有滑入动画

Expected: 所有微交互流畅自然

- [ ] **Step 4: 提交样式优化**

```bash
git add webui/index.html
git commit -m "feat: add micro-interactions and animations

- Add button hover and active scale effects
- Add input focus ring styles
- Add message slide-in animation
- Add loading pulse animation
- Smooth transitions for all interactive elements

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: 添加键盘快捷键支持

**Files:**
- Modify: `webui/index.html` (add keyboard shortcuts)

- [ ] **Step 1: 添加键盘事件处理**

```javascript
// 键盘快捷键
refs.messageInput.addEventListener('keydown', (event) => {
  // Enter 发送，Shift+Enter 换行
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    refs.chatForm.requestSubmit();
  }
});

// Escape 关闭抽屉
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && mobileDrawer.isOpen) {
    mobileDrawer.close();
  }
});
```

- [ ] **Step 2: 测试键盘快捷键**

在浏览器中测试：
- 在输入框中按 Enter 发送消息
- 按 Shift+Enter 换行
- 打开移动端抽屉后按 Escape 关闭

Expected: 键盘快捷键正常工作

- [ ] **Step 3: 提交键盘支持**

```bash
git add webui/index.html
git commit -m "feat: add keyboard shortcuts

- Enter to send message
- Shift+Enter for new line
- Escape to close mobile drawer
- Improve keyboard navigation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 12: 最终测试和验收

**Files:**
- Test: `webui/index.html`

- [ ] **Step 1: 功能测试**

测试所有核心功能：
- [ ] 消息发送和接收
- [ ] 附件上传
- [ ] Provider 切换
- [ ] 工具步骤展示
- [ ] 移动端抽屉

- [ ] **Step 2: 响应式测试**

测试不同屏幕尺寸：
- [ ] 桌面端 (>1024px): 左右分栏正常
- [ ] 平板端 (768-1024px): 布局适配
- [ ] 移动端 (<768px): 抽屉正常工作

- [ ] **Step 3: 浏览器兼容性测试**

测试不同浏览器：
- [ ] Chrome/Edge 最新版
- [ ] Firefox 最新版
- [ ] Safari 最新版
- [ ] 移动端浏览器

- [ ] **Step 4: 视觉还原检查**

对照设计规范检查：
- [ ] 配色系统正确（暖灰色系）
- [ ] 字体大小和字重正确
- [ ] 间距系统一致
- [ ] 圆角大小正确
- [ ] 阴影效果轻微

- [ ] **Step 5: 性能检查**

- [ ] 页面加载快速 (<1s)
- [ ] 交互响应及时 (<100ms)
- [ ] 动画流畅 (60fps)
- [ ] 无明显卡顿

- [ ] **Step 6: 最终提交**

```bash
git add webui/index.html
git commit -m "feat: complete WebUI redesign

完成 Mini Agent WebUI 重新设计，主要改进：

视觉风格：
- 采用极简专业风格（类似 Linear、Vercel）
- 暖灰配色系统（#fafaf9, #f5f5f4, #e7e5e4）
- 统一的间距和圆角系统
- 轻微的阴影效果

布局结构：
- 桌面端左右分栏（60:40）
- 对话区域和工具面板分离
- 输入框固定在底部
- 清晰的信息层级

响应式设计：
- 桌面端固定分栏
- 移动端底部抽屉
- 浮动按钮触发
- 平滑的过渡动画

交互优化：
- 按钮微交互动画
- 消息滑入效果
- 键盘快捷键支持
- 流畅的滚动体验

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## 自审清单

**规范覆盖：**
- [x] 极简专业风格 - 已实现
- [x] 右侧边栏布局 - 已实现
- [x] 暖灰配色系统 - 已实现
- [x] 宽松信息密度 - 已实现
- [x] 可折叠抽屉响应式 - 已实现
- [x] 顶部导航栏 - 已实现
- [x] 对话气泡样式 - 已实现
- [x] 输入框区域 - 已实现
- [x] 工具面板 - 已实现
- [x] 移动端抽屉 - 已实现

**占位符检查：**
- 无 TBD 或 TODO
- 所有代码块完整
- 所有步骤有明确指令

**类型一致性：**
- DOM 引用命名一致
- 函数签名一致
- CSS 类名一致

---

## 执行选项

计划已完成并保存到 `docs/superpowers/plans/2026-04-22-webui-redesign.md`。

**两种执行方式：**

**1. Subagent-Driven (推荐)** - 每个任务派发新的子 agent，任务间审查，快速迭代

**2. Inline Execution** - 在当前会话中执行，批量执行带检查点

**选择哪种方式？**

发送一个会触发工具调用的消息（如"查询薪资最高的3个员工"），检查：
- 工具步骤卡片正确显示
- 可以展开/收起查看详情
- 参数和结果以代码块形式显示
- 样式符合设计规范

Expected: 工具步骤正确展示

- [ ] **Step 3: 提交工具步骤功能**

```bash
git add webui/index.html
git commit -m "feat: implement tool steps display

- Render tool steps as collapsible cards
- Display tool name, arguments, and results
- Style code blocks with dark background
- Add expand/collapse functionality

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: 实现移动端响应式布局

**Files:**
- Modify: `webui/index.html` (add mobile drawer and responsive styles)

- [ ] **Step 1: 添加移动端抽屉 HTML**

在 `</main>` 前添加：

```html
<!-- 移动端工具抽屉 -->
<div id="mobileDrawer" class="lg:hidden fixed inset-0 z-40 pointer-events-none">
  <!-- 背景遮罩 -->
  <div id="drawerOverlay" class="absolute inset-0 bg-black/30 opacity-0 transition-opacity duration-200 pointer-events-none"></div>
  
  <!-- 抽屉内容 -->
  <div id="drawerContent" class="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl max-h-[70vh] overflow-y-auto transform translate-y-full transition-transform duration-300 pointer-events-auto">
    <!-- 拖动手柄 -->
    <div class="flex justify-center pt-3 pb-2">
      <div class="w-10 h-1 bg-warm-border rounded-full"></div>
    </div>
    
    <!-- 工具面板内容 -->
    <div class="p-6">
      <h2 class="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-4">Tool Event Stream</h2>
      
      <div id="mobileToolEmptyState" class="bg-warm-surface rounded-xl p-8 text-center">
        <span class="material-symbols-outlined text-4xl text-text-secondary mb-3 block">handyman</span>
        <p class="text-sm text-text-secondary">暂无工具调用</p>
      </div>
      
      <div id="mobileToolSteps" class="space-y-3"></div>
    </div>
  </div>
</div>

<!-- 移动端浮动按钮 -->
<button id="mobileToolBtn" class="lg:hidden fixed bottom-6 right-6 w-14 h-14 bg-text-primary text-white rounded-full shadow-lg flex items-center justify-center z-30">
  <span class="material-symbols-outlined">handyman</span>
</button>
```

- [ ] **Step 2: 添加抽屉控制 JavaScript**

```javascript
// 移动端抽屉控制
const mobileDrawer = {
  drawer: document.getElementById('mobileDrawer'),
  overlay: document.getElementById('drawerOverlay'),
  content: document.getElementById('drawerContent'),
  btn: document.getElementById('mobileToolBtn'),
  isOpen: false,
  
  open() {
    this.isOpen = true;
    this.drawer.classList.remove('pointer-events-none');
    this.overlay.classList.remove('pointer-events-none', 'opacity-0');
    this.content.classList.remove('translate-y-full');
  },
  
  close() {
    this.isOpen = false;
    this.overlay.classList.add('opacity-0');
    this.content.classList.add('translate-y-full');
    setTimeout(() => {
      this.drawer.classList.add('pointer-events-none');
      this.overlay.classList.add('pointer-events-none');
    }, 300);
  },
  
  toggle() {
    this.isOpen ? this.close() : this.open();
  },
};

// 事件绑定
mobileDrawer.btn.addEventListener('click', () => mobileDrawer.toggle());
mobileDrawer.overlay.addEventListener('click', () => mobileDrawer.close());

// 同步工具步骤到移动端
function syncToolStepsToMobile() {
  const mobileSteps = document.getElementById('mobileToolSteps');
  const mobileEmpty = document.getElementById('mobileToolEmptyState');
  
  if (refs.toolSteps.children.length > 0) {
    mobileEmpty.classList.add('hidden');
    mobileSteps.innerHTML = refs.toolSteps.innerHTML;
  }
}

// 修改 renderToolSteps 函数，添加同步调用
// 在 renderToolSteps 函数末尾添加：
// syncToolStepsToMobile();
```

启动后端，在浏览器中测试：
- 输入消息并发送
- 用户消息立即显示
- 发送按钮变为"处理中..."
- Agent 回复正确显示
- 带附件的消息正常发送

Expected: 完整的消息发送流程正常工作

- [ ] **Step 3: 提交消息发送功能**

```bash
git add webui/index.html
git commit -m "feat: implement message sending and API integration

- Add form submission handler
- Upload files before sending message
- Call /api/chat with text and file paths
- Display agent response
- Handle loading states and errors

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: 实现工具步骤展示

**Files:**
- Modify: `webui/index.html` (add tool steps rendering)

- [ ] **Step 1: 添加工具步骤渲染函数**

```javascript
// 工具步骤展示
function renderToolSteps(steps) {
  refs.toolEmptyState.classList.add('hidden');
  
  steps.forEach((step, index) => {
    const card = document.createElement('details');
    card.className = 'bg-warm-surface rounded-xl p-4 border border-warm-border';
    
    const summary = document.createElement('summary');
    summary.className = 'cursor-pointer list-none';
    
    const summaryContent = document.createElement('div');
    summaryContent.className = 'flex items-start justify-between gap-3';
    
    const left = document.createElement('div');
    left.className = 'flex-1 min-w-0';
    
    const title = document.createElement('div');
    title.className = 'text-sm font-semibold text-text-primary truncate';
    title.textContent = `${index + 1}. ${step.name || 'tool_call'}`;
    left.appendChild(title);
    
    const meta = document.createElement('div');
    meta.className = 'text-xs text-text-secondary mt-1';
    meta.textContent = `${Object.keys(step.args || {}).length} 个参数`;
    left.appendChild(meta);
    
    summaryContent.appendChild(left);
    
    const toggle = document.createElement('span');
    toggle.className = 'text-xs text-text-secondary';
    toggle.textContent = '展开';
    summaryContent.appendChild(toggle);
    
    summary.appendChild(summaryContent);
    card.appendChild(summary);
    
    // 详情内容
    const details = document.createElement('div');
    details.className = 'mt-3 pt-3 border-t border-warm-border space-y-3';
    
    // 参数
    const argsBlock = document.createElement('div');
    const argsLabel = document.createElement('div');
    argsLabel.className = 'text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2';
    argsLabel.textContent = '参数';
    argsBlock.appendChild(argsLabel);
    
    const argsCode = document.createElement('pre');
    argsCode.className = 'bg-text-primary text-gray-200 rounded-lg p-3 text-xs overflow-x-auto';
    argsCode.textContent = JSON.stringify(step.args || {}, null, 2);
    argsBlock.appendChild(argsCode);
    details.appendChild(argsBlock);
    
    // 结果
    const resultBlock = document.createElement('div');
    const resultLabel = document.createElement('div');
    resultLabel.className = 'text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2';
    resultLabel.textContent = '结果';
    resultBlock.appendChild(resultLabel);
    
    const resultCode = document.createElement('pre');
    resultCode.className = 'bg-text-primary text-gray-200 rounded-lg p-3 text-xs overflow-x-auto';
    resultCode.textContent = typeof step.result === 'string' ? step.result : JSON.stringify(step.result, null, 2);
    resultBlock.appendChild(resultCode);
    details.appendChild(resultBlock);
    
    card.appendChild(details);
    
    // 切换事件
    card.addEventListener('toggle', () => {
      toggle.textContent = card.open ? '收起' : '展开';
    });
    
    refs.toolSteps.appendChild(card);
  });
}
```

启动后端服务器，在浏览器中测试：
- Provider 列表正确加载
- 下拉菜单显示所有 providers
- 切换 provider 后保存到 localStorage
- 刷新页面后保持选择

Expected: Provider 管理功能正常

- [ ] **Step 3: 提交 Provider 功能**

```bash
git add webui/index.html
git commit -m "feat: implement provider loading and switching

- Load providers from /api/providers
- Render provider dropdown with vision support indicator
- Save selected provider to localStorage
- Auto-select based on active/configured status

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: 实现消息发送和 API 调用

**Files:**
- Modify: `webui/index.html` (add chat submission logic)

- [ ] **Step 1: 添加消息发送函数**

```javascript
// 消息发送
async function handleSubmit(event) {
  event.preventDefault();
  
  if (state.sending) return;
  
  const text = refs.messageInput.value.trim();
  if (!text) {
    alert('请输入消息');
    return;
  }
  
  const provider = state.providers.find(p => p.name === state.selectedProvider);
  if (!provider || !provider.configured) {
    alert('当前 provider 未配置');
    return;
  }
  
  const filesSnapshot = [...state.pendingFiles];
  
  // 显示用户消息
  appendMessage({
    role: 'user',
    text,
    files: filesSnapshot.map(f => f.name),
  });
  
  // 清空输入
  refs.messageInput.value = '';
  state.pendingFiles = [];
  renderFilePreview();
  
  // 设置发送状态
  setSending(true);
  
  try {
    // 上传附件
    let uploadedPaths = [];
    if (filesSnapshot.length > 0) {
      uploadedPaths = await uploadFiles(filesSnapshot);
    }
    
    // 发送消息
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        image_paths: uploadedPaths,
        provider: provider.name,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`);
    }
    
    const result = await response.json();
    
    // 显示 Agent 回复
    appendMessage({
      role: 'assistant',
      text: result.reply || '无回复',
    });
    
    // 显示工具步骤
    if (result.steps && result.steps.length > 0) {
      renderToolSteps(result.steps);
    }
    
  } catch (error) {
    console.error('发送失败:', error);
    appendMessage({
      role: 'assistant',
      text: `错误: ${error.message}`,
    });
  } finally {
    setSending(false);
  }
}

async function uploadFiles(files) {
  const paths = [];
  
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`上传失败: ${file.name}`);
    }
    
    const result = await response.json();
    paths.push(result.path);
  }
  
  return paths;
}

function setSending(sending) {
  state.sending = sending;
  refs.sendBtn.disabled = sending;
  refs.sendBtn.textContent = sending ? '处理中...' : '发送';
  refs.messageInput.disabled = sending;
  refs.attachBtn.disabled = sending;
  refs.providerSelect.disabled = sending;
}

// 事件绑定
refs.chatForm.addEventListener('submit', handleSubmit);
```

在浏览器中测试：
- 点击附件按钮，选择文件
- 文件预览区域显示
- 文件标签正确显示文件名
- 点击 × 可以移除单个文件
- 点击"清除"可以移除所有文件

Expected: 附件选择和预览功能正常工作

- [ ] **Step 3: 提交附件功能**

```bash
git add webui/index.html
git commit -m "feat: implement file attachment handling

- Add file selection and preview
- Display selected files with remove buttons
- Add clear all files functionality
- Style file tags with warm gray theme

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: 实现 Provider 加载和切换

**Files:**
- Modify: `webui/index.html` (add provider management)

- [ ] **Step 1: 添加 Provider 管理函数**

```javascript
// Provider 管理
const PROVIDER_STORAGE_KEY = 'mini-agent-provider';

async function loadProviders() {
  try {
    const response = await fetch('/api/providers');
    const data = await response.json();
    state.providers = Array.isArray(data) ? data : [];
    
    if (state.providers.length === 0) {
      throw new Error('没有可用的 provider');
    }
    
    // 选择初始 provider
    const stored = localStorage.getItem(PROVIDER_STORAGE_KEY);
    const active = state.providers.find(p => p.is_active);
    const configured = state.providers.find(p => p.configured);
    
    state.selectedProvider = 
      state.providers.find(p => p.name === stored)?.name ||
      active?.name ||
      configured?.name ||
      state.providers[0].name;
    
    renderProviderOptions();
  } catch (error) {
    console.error('加载 providers 失败:', error);
    alert('加载 providers 失败: ' + error.message);
  }
}

function renderProviderOptions() {
  refs.providerSelect.innerHTML = '';
  
  state.providers.forEach(provider => {
    const option = document.createElement('option');
    option.value = provider.name;
    option.textContent = `${provider.name} ${provider.supports_vision ? '(支持图片)' : '(仅文本)'}`;
    option.selected = provider.name === state.selectedProvider;
    refs.providerSelect.appendChild(option);
  });
}

function handleProviderChange(event) {
  state.selectedProvider = event.target.value;
  localStorage.setItem(PROVIDER_STORAGE_KEY, state.selectedProvider);
}

// 事件绑定
refs.providerSelect.addEventListener('change', handleProviderChange);

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
  loadProviders();
});
```

在浏览器控制台测试：

```javascript
// 测试用户消息
appendMessage({ role: 'user', text: '你好，这是测试消息', files: ['test.png'] });

// 测试 Agent 消息
appendMessage({ role: 'assistant', text: '你好！我是 Mini Agent。' });
```

Expected: 
- 用户消息：深蓝灰背景，白色文字，右对齐，右下角尖角
- Agent 消息：白色背景，黑色文字，左对齐，左下角尖角
- 附件标签正确显示
- 消息自动滚动到底部

- [ ] **Step 3: 提交消息渲染功能**

```bash
git add webui/index.html
git commit -m "feat: implement message bubble rendering

- Add appendMessage function for user and agent messages
- Style user messages with dark background and white text
- Style agent messages with white background and border
- Add attachment tags display
- Implement auto-scroll to bottom

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: 实现附件上传功能

**Files:**
- Modify: `webui/index.html` (add file handling JavaScript)

- [ ] **Step 1: 添加附件处理函数**

在 JavaScript 部分添加：

```javascript
// 附件处理
function handleFileSelect(event) {
  const files = Array.from(event.target.files || []);
  if (files.length === 0) return;
  
  state.pendingFiles = [...state.pendingFiles, ...files];
  renderFilePreview();
  refs.fileInput.value = '';
}

function renderFilePreview() {
  if (state.pendingFiles.length === 0) {
    refs.attachmentPreview.classList.add('hidden');
    return;
  }
  
  refs.attachmentPreview.classList.remove('hidden');
  refs.fileCount.textContent = state.pendingFiles.length;
  refs.fileList.innerHTML = '';
  
  state.pendingFiles.forEach((file, index) => {
    const tag = document.createElement('div');
    tag.className = 'flex items-center gap-2 px-3 py-1.5 bg-white border border-warm-border rounded-full text-xs';
    
    const icon = document.createElement('span');
    icon.className = 'material-symbols-outlined text-sm';
    icon.textContent = 'draft';
    tag.appendChild(icon);
    
    const name = document.createElement('span');
    name.textContent = file.name;
    tag.appendChild(name);
    
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'text-text-secondary hover:text-text-primary';
    removeBtn.textContent = '×';
    removeBtn.onclick = () => removeFile(index);
    tag.appendChild(removeBtn);
    
    refs.fileList.appendChild(tag);
  });
}

function removeFile(index) {
  state.pendingFiles.splice(index, 1);
  renderFilePreview();
}

function clearAllFiles() {
  state.pendingFiles = [];
  renderFilePreview();
}

// 事件绑定
refs.attachBtn.addEventListener('click', () => refs.fileInput.click());
refs.fileInput.addEventListener('change', handleFileSelect);
refs.clearFiles.addEventListener('click', clearAllFiles);
```

在浏览器中打开，检查：
- 左右分栏在桌面端（>1024px）正确显示
- 左侧占 60%，右侧占 40%
- 对话区域和工具面板都可滚动
- 输入框固定在左侧底部
- 空状态正确显示

Expected: 布局正确，左右分栏比例合适

- [ ] **Step 3: 提交布局结构**

```bash
git add webui/index.html
git commit -m "feat: implement desktop split layout

- Add 60/40 split layout for desktop
- Add conversation area with empty state
- Add input area with textarea and buttons
- Add tool panel with empty state
- Implement scrollable containers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: 实现对话气泡样式

**Files:**
- Modify: `webui/index.html` (add JavaScript for message rendering)

- [ ] **Step 1: 添加消息渲染函数**

在 `</body>` 前添加 JavaScript：

```html
<script>
// 状态管理
const state = {
  providers: [],
  selectedProvider: '',
  pendingFiles: [],
  sending: false,
};

// DOM 引用
const refs = {
  conversation: document.getElementById('conversation'),
  emptyState: document.getElementById('emptyState'),
  messageInput: document.getElementById('messageInput'),
  sendBtn: document.getElementById('sendBtn'),
  attachBtn: document.getElementById('attachBtn'),
  fileInput: document.getElementById('fileInput'),
  attachmentPreview: document.getElementById('attachmentPreview'),
  fileList: document.getElementById('fileList'),
  fileCount: document.getElementById('fileCount'),
  clearFiles: document.getElementById('clearFiles'),
  chatForm: document.getElementById('chatForm'),
  providerSelect: document.getElementById('providerSelect'),
  toolSteps: document.getElementById('toolSteps'),
  toolEmptyState: document.getElementById('toolEmptyState'),
};

// 渲染消息气泡
function appendMessage({ role, text, files = [] }) {
  refs.emptyState.classList.add('hidden');
  
  const wrapper = document.createElement('div');
  wrapper.className = role === 'user' ? 'flex justify-end' : 'flex justify-start';
  
  const bubble = document.createElement('div');
  bubble.className = role === 'user'
    ? 'max-w-[85%] bg-text-primary text-white rounded-2xl rounded-br-md px-5 py-4'
    : 'max-w-[85%] bg-white border border-warm-border text-text-primary rounded-2xl rounded-bl-md px-5 py-4';
  
  // 消息头部
  const header = document.createElement('div');
  header.className = role === 'user'
    ? 'text-xs font-semibold uppercase tracking-wider text-white/70 mb-2'
    : 'text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2';
  header.textContent = role === 'user' ? '你' : 'Agent';
  bubble.appendChild(header);
  
  // 消息内容
  const content = document.createElement('div');
  content.className = 'text-base leading-relaxed whitespace-pre-wrap break-words';
  content.textContent = text;
  bubble.appendChild(content);
  
  // 附件标签
  if (files.length > 0) {
    const fileContainer = document.createElement('div');
    fileContainer.className = 'flex flex-wrap gap-2 mt-3';
    files.forEach(fileName => {
      const fileTag = document.createElement('span');
      fileTag.className = role === 'user'
        ? 'px-3 py-1.5 bg-white/15 text-white/85 text-xs rounded-full'
        : 'px-3 py-1.5 bg-warm-surface text-text-secondary text-xs rounded-full';
      fileTag.textContent = fileName;
      fileContainer.appendChild(fileTag);
    });
    bubble.appendChild(fileContainer);
  }
  
  wrapper.appendChild(bubble);
  refs.conversation.appendChild(wrapper);
  refs.conversation.scrollTop = refs.conversation.scrollHeight;
}
</script>
```

在浏览器中打开，检查：
- 导航栏固定在顶部
- Logo 显示正确
- Provider 选择器显示
- 状态指示器在桌面端显示
- 移动端菜单按钮在小屏幕显示

Expected: 导航栏正确显示，响应式行为正常

- [ ] **Step 3: 提交导航栏**

```bash
git add webui/index.html
git commit -m "feat: implement top navigation bar

- Add fixed navigation with backdrop blur
- Add logo, provider selector, and status indicator
- Add mobile menu button for responsive design
- Use warm gray color system

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: 实现桌面端左右分栏布局

**Files:**
- Modify: `webui/index.html` (main section)

- [ ] **Step 1: 创建左右分栏结构**

替换 main 标签内容：

```html
<main class="pt-16 h-screen">
  <div class="max-w-[1280px] mx-auto h-[calc(100vh-64px)] flex">
    <!-- 左侧：对话区域 (60%) -->
    <div class="flex-1 lg:w-[60%] flex flex-col border-r border-warm-border bg-white">
      <!-- 对话列表 -->
      <div id="conversation" class="flex-1 overflow-y-auto conversation-scroll p-6 space-y-6">
        <!-- 空状态 -->
        <div id="emptyState" class="flex flex-col items-center justify-center h-full text-center">
          <div class="w-16 h-16 rounded-full bg-warm-surface flex items-center justify-center mb-4">
            <span class="material-symbols-outlined text-3xl text-text-secondary">forum</span>
          </div>
          <h3 class="text-lg font-semibold text-text-primary mb-2">开始新对话</h3>
          <p class="text-sm text-text-secondary max-w-md">
            输入消息或上传附件开始与 Agent 对话
          </p>
        </div>
      </div>
      
      <!-- 输入框区域 -->
      <div class="border-t border-warm-border bg-white p-6">
        <form id="chatForm" class="space-y-4">
          <!-- 附件预览区 -->
          <div id="attachmentPreview" class="hidden bg-warm-surface rounded-xl p-3 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-sm text-text-secondary">已选择 <span id="fileCount">0</span> 个文件</span>
              <button type="button" id="clearFiles" class="text-xs text-text-secondary hover:text-text-primary">清除</button>
            </div>
            <div id="fileList" class="flex flex-wrap gap-2"></div>
          </div>
          
          <!-- 输入框 -->
          <textarea id="messageInput" 
                    rows="4"
                    placeholder="输入消息..."
                    class="w-full px-4 py-3 bg-warm-surface border border-warm-border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-text-primary transition-all"></textarea>
          
          <!-- 按钮组 -->
          <div class="flex items-center justify-between">
            <button type="button" id="attachBtn" class="w-10 h-10 flex items-center justify-center rounded-full border border-warm-border hover:bg-warm-surface transition-colors">
              <span class="material-symbols-outlined">attach_file</span>
            </button>
            <button type="submit" id="sendBtn" class="px-6 py-2.5 bg-text-primary text-white rounded-lg font-semibold hover:bg-opacity-90 transition-all active:scale-95">
              发送
            </button>
          </div>
        </form>
        <input type="file" id="fileInput" multiple class="hidden" />
      </div>
    </div>
    
    <!-- 右侧：工具面板 (40%) -->
    <div id="toolPanel" class="hidden lg:block lg:w-[40%] bg-white overflow-y-auto tool-scroll">
      <div class="p-6">
        <h2 class="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-4">Tool Event Stream</h2>
        
        <!-- 空状态 -->
        <div id="toolEmptyState" class="bg-warm-surface rounded-xl p-8 text-center">
          <span class="material-symbols-outlined text-4xl text-text-secondary mb-3 block">handyman</span>
          <p class="text-sm text-text-secondary">暂无工具调用</p>
        </div>
        
        <!-- 工具步骤容器 -->
        <div id="toolSteps" class="space-y-3"></div>
      </div>
    </div>
  </div>
</main>
```

在浏览器中打开 HTML，检查：
- Tailwind CSS 加载成功
- Inter 字体加载成功
- Material Symbols 图标加载成功
- 自定义颜色可用

Expected: 页面空白但无控制台错误

- [ ] **Step 3: 提交基础配置**

```bash
git add webui/index.html
git commit -m "feat: setup Tailwind config with warm gray color system

- Add Inter font and Material Symbols icons
- Configure warm gray color palette (#fafaf9, #f5f5f4, #e7e5e4)
- Add custom scrollbar styles
- Set up base typography

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: 实现顶部导航栏

**Files:**
- Modify: `webui/index.html` (body section)

- [ ] **Step 1: 创建导航栏 HTML 结构**

```html
<body class="bg-warm-bg text-text-primary antialiased">
  <!-- 顶部导航栏 -->
  <nav class="fixed top-0 left-0 right-0 z-50 h-16 bg-white/90 backdrop-blur-xl border-b border-warm-border">
    <div class="max-w-[1280px] mx-auto h-full px-6 flex items-center justify-between">
      <!-- Logo -->
      <div class="flex items-center">
        <span class="text-lg font-bold tracking-tight text-text-primary">MINI AGENT</span>
      </div>
      
      <!-- 右侧控制区 -->
      <div class="flex items-center gap-3">
        <!-- Provider 选择器 -->
        <select id="providerSelect" 
                class="px-3 py-2 text-sm border border-warm-border rounded-lg bg-white hover:bg-warm-surface transition-colors focus:outline-none focus:ring-2 focus:ring-text-primary">
          <option>加载中...</option>
        </select>
        
        <!-- 状态指示器 -->
        <div class="hidden md:flex items-center gap-2 px-3 py-1.5 bg-warm-surface rounded-full">
          <span class="w-2 h-2 rounded-full bg-success"></span>
          <span class="text-xs font-semibold uppercase tracking-wider text-text-secondary">Live</span>
        </div>
        
        <!-- 移动端菜单按钮 -->
        <button id="mobileMenuBtn" class="md:hidden w-10 h-10 flex items-center justify-center rounded-full border border-warm-border hover:bg-warm-surface">
          <span class="material-symbols-outlined">menu</span>
        </button>
      </div>
    </div>
  </nav>
  
  <!-- 主内容区占位 -->
  <main class="pt-16">
    <!-- 待实现 -->
  </main>
</body>
```
