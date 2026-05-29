<template>
  <el-drawer
    v-model="visible"
    title="AI 智能诊断"
    direction="rtl"
    size="600px"
    :close-on-click-modal="false"
    class="ai-diagnosis-drawer"
  >
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
  </el-drawer>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const props = defineProps({
  modelValue: Boolean,
  projects: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const analyzing = ref(false)
const result = ref(null)
const error = ref('')

const form = reactive({
  projectId: null,
  errorLog: '',
  extraContext: '',
})

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function open(projectId, errorLog, extraContext) {
  if (projectId) form.projectId = projectId
  if (errorLog) form.errorLog = errorLog
  if (extraContext) form.extraContext = extraContext
  visible.value = true
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

    const { data } = await request.post('/agent/analyze', payload, { timeout: 130000 })
    result.value = data
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '诊断失败'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    analyzing.value = false
  }
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

defineExpose({ open, analyzing })
</script>

<style scoped>
.diagnosis-content {
  padding: 0 4px;
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
</style>
