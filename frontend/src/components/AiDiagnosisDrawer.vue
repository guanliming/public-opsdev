<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    size="600px"
    :close-on-click-modal="false"
    class="ai-drawer"
    :with-header="false"
  >
    <div class="drawer-close-btn" @click="visible = false">
      <el-icon><Close /></el-icon>
    </div>
    <el-tabs v-model="activeTab" class="ai-tabs">
      <el-tab-pane label="智能诊断" name="diagnosis">
        <div class="diagnosis-content">
          <!-- Input Section -->
          <div class="input-section">
            <div class="section-label">选择项目</div>
            <el-select v-model="form.projectId" placeholder="选择项目（可选）" style="width: 100%; margin-bottom: 12px;" clearable>
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>

            <div class="section-label">错误日志</div>
            <el-input
              v-model="form.errorLog"
              type="textarea"
              :rows="6"
              placeholder="粘贴错误日志或通过日志页面选中文本自动填入..."
              resize="vertical"
            />

            <div class="section-label" style="margin-top: 12px;">补充说明（可选）</div>
            <el-input
              v-model="form.extraContext"
              type="textarea"
              :rows="2"
              placeholder="描述触发条件、复现步骤等..."
              resize="vertical"
            />

            <el-button
              type="primary"
              style="width: 100%; margin-top: 16px;"
              :loading="analyzing"
              :disabled="!form.errorLog.trim()"
              @click="startAnalysis"
            >
              <el-icon v-if="!analyzing" style="margin-right: 6px;"><MagicStick /></el-icon>
              {{ analyzing ? '诊断中...' : '开始诊断' }}
            </el-button>
          </div>

          <!-- Loading -->
          <div v-if="analyzing" class="analyzing-section">
            <div class="analyzing-animation">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>
            <p class="analyzing-text">AI 正在分析错误日志，请稍候...</p>
            <p class="analyzing-hint">分析过程可能需要 10~60 秒</p>
          </div>

          <!-- Result -->
          <div v-if="result" class="result-section">
            <!-- Summary Card -->
            <div class="summary-card" :class="'severity-' + result.severity">
              <div class="summary-left">
                <div class="severity-badge">
                  <span class="severity-icon">{{ severityIcon(result.severity) }}</span>
                  <span class="severity-text">{{ severityLabel(result.severity) }}</span>
                </div>
                <div v-if="result.error_type" class="error-type">{{ result.error_type }}</div>
              </div>
              <div class="summary-right">
                <div v-if="result.confidence" class="confidence-bar">
                  <span class="confidence-label">置信度</span>
                  <div class="confidence-dots">
                    <span class="conf-dot" :class="{ active: confidenceLevel(result.confidence) >= 1 }"></span>
                    <span class="conf-dot" :class="{ active: confidenceLevel(result.confidence) >= 2 }"></span>
                    <span class="conf-dot" :class="{ active: confidenceLevel(result.confidence) >= 3 }"></span>
                  </div>
                  <span class="confidence-value">{{ confidenceLabel(result.confidence) }}</span>
                </div>
                <div v-if="result.analysis_id" class="analysis-id">{{ result.analysis_id }}</div>
              </div>
            </div>

            <!-- Root Cause -->
            <div class="result-block">
              <div class="block-title">
                <span class="block-icon">&#x1f50d;</span> 根因分析
              </div>
              <div class="block-content root-cause">{{ result.root_cause }}</div>
            </div>

            <!-- Fix Suggestions -->
            <div v-if="result.fix_suggestions && result.fix_suggestions.length" class="result-block">
              <div class="block-title">
                <span class="block-icon">&#x1f6e0;</span> 修复建议
              </div>
              <div v-for="(s, idx) in result.fix_suggestions" :key="idx" class="suggestion-item">
                <div class="suggestion-header">
                  <span class="suggestion-index">{{ idx + 1 }}</span>
                  <span class="suggestion-file">{{ s.file }}<span v-if="s.line" class="suggestion-line">:{{ s.line }}</span></span>
                </div>
                <div class="suggestion-desc">{{ s.description }}</div>
                <div v-if="s.code_snippet" class="code-block">
                  <div class="code-toolbar">
                    <span class="code-lang">suggested fix</span>
                  </div>
                  <pre><code>{{ s.code_snippet }}</code></pre>
                </div>
              </div>
            </div>

            <!-- Related Files -->
            <div v-if="result.related_files && result.related_files.length" class="result-block">
              <div class="block-title">
                <span class="block-icon">&#x1f4c1;</span> 关联文件
              </div>
              <div class="related-files-grid">
                <div v-for="(f, idx) in result.related_files" :key="idx" class="related-file-item">
                  <div class="file-icon">&#x1f4c4;</div>
                  <div class="file-info">
                    <span class="file-path">{{ f.path }}</span>
                    <span class="file-reason">{{ f.reason }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Token Usage -->
            <div v-if="result.token_usage" class="token-footer">
              <span class="token-label">Token 消耗</span>
              <span class="token-value">{{ result.token_usage.total_tokens?.toLocaleString() }}</span>
            </div>
          </div>

          <!-- Error -->
          <div v-if="error" class="error-section">
            <el-alert :title="error" type="error" show-icon :closable="false" />
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="智能问答" name="chat">
        <div class="chat-content">
          <div class="section-label">选择项目（可选，AI 可读取代码上下文）</div>
          <el-select v-model="chatForm.projectId" placeholder="选择项目" style="width: 100%; margin-bottom: 16px;" clearable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>

          <div class="chat-messages" ref="chatMessagesRef">
            <div v-if="chatMessages.length === 0" class="chat-empty">
              <div class="chat-empty-icon">&#x1f4ac;</div>
              <p>向 AI 提问关于项目、代码、运维等方面的问题</p>
            </div>
            <div v-for="(msg, idx) in chatMessages" :key="idx" class="chat-msg" :class="msg.role">
              <div class="msg-avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
              <div class="msg-bubble">
                <div class="msg-text" v-if="msg.role === 'user'">{{ msg.content }}</div>
                <div class="msg-text formatted" v-else v-html="renderContent(msg.content)"></div>
                <div v-if="msg.duration" class="msg-duration">{{ msg.duration }}s</div>
              </div>
            </div>
            <div v-if="chatLoading" class="chat-msg assistant">
              <div class="msg-avatar">AI</div>
              <div class="msg-bubble">
                <div class="chat-typing">
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                </div>
              </div>
            </div>
          </div>

          <div class="chat-input-bar">
            <el-input
              v-model="chatForm.question"
              type="textarea"
              :rows="4"
              placeholder="输入你的问题，按 Enter 发送，Shift+Enter 换行..."
              resize="none"
              @keydown.enter.exact.prevent="sendChat"
            />
            <el-button
              type="primary"
              :loading="chatLoading"
              :disabled="!chatForm.question.trim()"
              @click="sendChat"
              class="chat-send-btn"
            >
              <el-icon v-if="!chatLoading"><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-drawer>
</template>

<script setup>
import { ref, reactive, watch, nextTick } from 'vue'
import { MagicStick, Promotion, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import request from '../utils/request'

const props = defineProps({
  modelValue: Boolean,
  projects: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const activeTab = ref('diagnosis')
const analyzing = ref(false)
const result = ref(null)
const error = ref('')
const chatLoading = ref(false)
const chatMessages = ref([])
const chatMessagesRef = ref(null)
const diagnosisSessionId = ref('')
const chatSessionId = ref('')

function generateSessionId(prefix = 'sess') {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

const form = reactive({
  projectId: null,
  errorLog: '',
  extraContext: '',
})

const chatForm = reactive({
  projectId: null,
  question: '',
})

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
  if (!val) {
    activeTab.value = 'diagnosis'
  }
})

function open(projectId, errorLog, extraContext) {
  activeTab.value = 'diagnosis'
  if (projectId) form.projectId = projectId
  if (errorLog) form.errorLog = errorLog
  if (extraContext) form.extraContext = extraContext
  diagnosisSessionId.value = generateSessionId('diag')
  visible.value = true
}

function openChat(projectId) {
  activeTab.value = 'chat'
  if (projectId) chatForm.projectId = projectId
  chatSessionId.value = generateSessionId('chat')
  chatMessages.value = []
  visible.value = true
  nextTick(scrollToBottom)
}

async function startAnalysis() {
  if (!form.errorLog.trim()) return
  analyzing.value = true
  result.value = null
  error.value = ''

  try {
    const payload = { error_log: form.errorLog }
    if (form.projectId) payload.project_id = form.projectId
    if (form.extraContext) payload.extra_context = form.extraContext
    payload.session_id = diagnosisSessionId.value

    const { data } = await request.post('/agent/analyze', payload, { timeout: 300000 })
    if (data.session_id) diagnosisSessionId.value = data.session_id
    result.value = data
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '诊断失败'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    analyzing.value = false
  }
}

async function sendChat() {
  const question = chatForm.question.trim()
  if (!question || chatLoading.value) return

  chatMessages.value.push({ role: 'user', content: question })
  chatForm.question = ''
  chatLoading.value = true
  const startTime = Date.now()
  nextTick(scrollToBottom)

  try {
    const payload = { question }
    if (chatForm.projectId) payload.project_id = chatForm.projectId
    payload.session_id = chatSessionId.value

    const { data } = await request.post('/agent/chat', payload, { timeout: 300000 })
    if (data.session_id) chatSessionId.value = data.session_id
    const elapsed = Math.round((Date.now() - startTime) / 1000)
    chatMessages.value.push({ role: 'assistant', content: data.answer || '未获取到回答', duration: elapsed })
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '问答请求失败'
    chatMessages.value.push({ role: 'assistant', content: '请求失败：' + msg })
    ElMessage.error(msg)
  } finally {
    chatLoading.value = false
    nextTick(scrollToBottom)
  }
}

function scrollToBottom() {
  const el = chatMessagesRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function renderContent(text) {
  if (!text) return ''
  return marked.parse(text, { breaks: true })
}

function severityIcon(severity) {
  const map = { critical: '⛔', high: '⚠️', medium: 'ℹ️', low: '✅' }
  return map[severity] || '❓'
}

function severityLabel(severity) {
  const map = { critical: '严重', high: '高危', medium: '中等', low: '低风险', unknown: '未知' }
  return map[severity] || severity
}

function confidenceLevel(confidence) {
  const map = { high: 3, medium: 2, low: 1 }
  return map[confidence] || 0
}

function confidenceLabel(confidence) {
  const map = { high: '高', medium: '中', low: '低' }
  return map[confidence] || confidence
}

defineExpose({ open, openChat, analyzing })
</script>

<style scoped>
.ai-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.ai-drawer :deep(.el-drawer__body) {
  padding: 0 16px;
  position: relative;
}
.drawer-close-btn {
  position: absolute;
  top: 8px;
  right: 16px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #909399;
  font-size: 18px;
  z-index: 10;
  border-radius: 50%;
  transition: all 0.2s;
}
.drawer-close-btn:hover {
  background: #f5f7fa;
  color: #606266;
}
.ai-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0;
}
.ai-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0;
}
.ai-tabs :deep(.el-tabs__nav) {
  margin: 0;
}
.ai-tabs :deep(.el-tabs__content) {
  padding: 8px 0 0;
  overflow: auto;
  flex: 1;
}
.ai-tabs :deep(.el-tab-pane) {
  height: 100%;
  padding: 0;
}

/* ─── Diagnosis Tab ─── */
.diagnosis-content {
  padding-bottom: 20px;
}

.input-section {
  margin-bottom: 20px;
}

.section-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  font-weight: 500;
}

/* Analyzing */
.analyzing-section {
  text-align: center;
  padding: 40px 0;
}

.analyzing-animation {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 16px;
}

.analyzing-animation .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  animation: bounce 1.4s ease-in-out infinite;
}

.analyzing-animation .dot:nth-child(2) { animation-delay: 0.2s; }
.analyzing-animation .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.analyzing-text {
  color: #606266;
  font-size: 14px;
  margin: 0;
}

.analyzing-hint {
  color: #c0c4cc;
  font-size: 12px;
  margin-top: 8px;
}

/* Result */
.result-section {
  margin-top: 24px;
}

/* Summary Card */
.summary-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  border-radius: 10px;
  margin-bottom: 24px;
  border: 1px solid;
}

.summary-card.severity-critical {
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border-color: #f89898;
}

.summary-card.severity-high {
  background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
  border-color: #f3d19e;
}

.summary-card.severity-medium {
  background: linear-gradient(135deg, #f0f9ff 0%, #e1f3ff 100%);
  border-color: #a0cfff;
}

.summary-card.severity-low {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
  border-color: #a4da89;
}

.summary-card.severity-unknown {
  background: linear-gradient(135deg, #f4f4f5 0%, #e9e9eb 100%);
  border-color: #c8c9cc;
}

.summary-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.severity-badge {
  display: flex;
  align-items: center;
  gap: 8px;
}

.severity-icon {
  font-size: 20px;
}

.severity-text {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.error-type {
  font-size: 13px;
  color: #606266;
  padding: 2px 8px;
  background: rgba(255,255,255,0.7);
  border-radius: 4px;
  display: inline-block;
}

.summary-right {
  text-align: right;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.confidence-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.confidence-label {
  font-size: 12px;
  color: #909399;
}

.confidence-dots {
  display: flex;
  gap: 3px;
}

.conf-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dcdfe6;
  transition: background 0.3s;
}

.conf-dot.active {
  background: #667eea;
}

.confidence-value {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.analysis-id {
  font-size: 11px;
  color: #c0c4cc;
  font-family: 'Consolas', monospace;
}

/* Result Blocks */
.result-block {
  margin-bottom: 24px;
}

.block-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.block-icon {
  font-size: 16px;
}

.block-content {
  font-size: 14px;
  line-height: 1.8;
  color: #4a4a4a;
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Suggestions */
.suggestion-item {
  margin-bottom: 16px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  transition: box-shadow 0.2s;
}

.suggestion-item:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.suggestion-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.suggestion-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.suggestion-file {
  font-family: 'Consolas', 'SF Mono', monospace;
  font-size: 13px;
  color: #667eea;
  font-weight: 600;
}

.suggestion-line {
  color: #909399;
}

.suggestion-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #4a4a4a;
  margin-bottom: 12px;
  padding-left: 32px;
}

.code-block {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #2d2d2d;
}

.code-toolbar {
  background: #2d2d2d;
  padding: 6px 12px;
  display: flex;
  align-items: center;
}

.code-lang {
  font-size: 11px;
  color: #858585;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.code-block pre {
  margin: 0;
  padding: 14px 16px;
  background: #1e1e1e;
}

.code-block code {
  font-family: 'Consolas', 'SF Mono', 'Courier New', monospace;
  font-size: 12px;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

/* Related Files */
.related-files-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.related-file-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  transition: background 0.2s;
}

.related-file-item:hover {
  background: #f8f9fa;
}

.file-icon {
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

.file-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-path {
  font-family: 'Consolas', 'SF Mono', monospace;
  font-size: 13px;
  color: #667eea;
  font-weight: 500;
}

.file-reason {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

/* Token Footer */
.token-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  margin-top: 8px;
}

.token-label {
  font-size: 12px;
  color: #c0c4cc;
}

.token-value {
  font-size: 12px;
  color: #909399;
  font-family: 'Consolas', monospace;
  font-weight: 500;
}

/* Error */
.error-section {
  margin-top: 16px;
}

/* ─── Chat Tab ─── */
.chat-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-empty {
  text-align: center;
  color: #c0c4cc;
  padding: 60px 20px;
}

.chat-empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.chat-empty p {
  font-size: 14px;
  margin: 0;
  line-height: 1.6;
}

.chat-msg {
  display: flex;
  gap: 10px;
  max-width: 85%;
}

.chat-msg.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.chat-msg.assistant {
  align-self: flex-start;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.chat-msg.user .msg-avatar {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
}

.chat-msg.assistant .msg-avatar {
  background: #e8e8e8;
  color: #606266;
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  overflow: hidden;
}

.chat-msg.user .msg-bubble {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-msg.assistant .msg-bubble {
  background: #f0f2f5;
  color: #303133;
  border-bottom-left-radius: 4px;
}

.msg-text {
  white-space: pre-wrap;
}

.msg-text.formatted {
  white-space: normal;
}

.msg-text.formatted p {
  margin: 0 0 8px;
}

.msg-text.formatted p:last-child {
  margin-bottom: 0;
}

.msg-text.formatted pre {
  margin: 8px 0;
  padding: 12px 14px;
  background: #1e1e1e;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}

.msg-text.formatted code {
  font-family: 'Consolas', 'SF Mono', 'Courier New', monospace;
  font-size: 12px;
}

.msg-text.formatted :not(pre) > code {
  background: #e8e8e8;
  padding: 1px 5px;
  border-radius: 3px;
  color: #d63384;
}

.msg-text.formatted ul,
.msg-text.formatted ol {
  margin: 4px 0;
  padding-left: 20px;
}

.msg-text.formatted li {
  margin-bottom: 2px;
}

.msg-text.formatted strong {
  font-weight: 600;
}

.msg-text.formatted blockquote {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid #667eea;
  color: #606266;
  background: rgba(102, 126, 234, 0.06);
  border-radius: 0 4px 4px 0;
}

.msg-text.formatted h1,
.msg-text.formatted h2,
.msg-text.formatted h3,
.msg-text.formatted h4 {
  margin: 10px 0 6px;
  font-weight: 600;
}

.msg-text.formatted h1 { font-size: 16px; }
.msg-text.formatted h2 { font-size: 15px; }
.msg-text.formatted h3 { font-size: 14px; }
.msg-text.formatted h4 { font-size: 14px; }

.msg-text.formatted table {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
  font-size: 13px;
}

.msg-text.formatted th,
.msg-text.formatted td {
  border: 1px solid #dcdfe6;
  padding: 6px 10px;
  text-align: left;
}

.msg-text.formatted th {
  background: #f5f7fa;
  font-weight: 600;
}

.msg-text.formatted a {
  color: #667eea;
  text-decoration: underline;
}

.msg-duration {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 6px;
  text-align: right;
}

.chat-typing {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #909399;
  animation: typingBounce 1.2s ease-in-out infinite;
}

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.chat-input-bar {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  flex-shrink: 0;
}

.chat-input-bar .el-textarea {
  flex: 1;
}

.chat-input-bar .el-textarea :deep(.el-textarea__inner) {
  min-height: 80px !important;
}

.chat-send-btn {
  height: 80px;
  width: 56px;
  flex-shrink: 0;
  font-size: 20px;
}
</style>
