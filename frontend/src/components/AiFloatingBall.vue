<template>
  <div
    class="ai-floating-ball"
    :style="{ left: position.x + 'px', top: position.y + 'px' }"
    @mousedown="startDrag"
    @click.stop="handleClick"
  >
    <div class="ai-ball-inner" :class="{ analyzing: isAnalyzing }">
      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="url(#grad)" opacity="0.15"/>
        <circle cx="9" cy="10" r="1.5" fill="#fff"/>
        <circle cx="15" cy="10" r="1.5" fill="#fff"/>
        <path d="M8 14s1.5 2 4 2 4-2 4-2" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M12 2V1M4.93 4.93L4.22 4.22M2 12H1M4.93 19.07l-.71.71" stroke="#a78bfa" stroke-width="1.5" stroke-linecap="round"/>
        <rect x="6" y="6" width="12" height="12" rx="3" stroke="#fff" stroke-width="1.5"/>
        <path d="M9 6V4M15 6V4" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
        <defs>
          <linearGradient id="grad" x1="2" y1="2" x2="22" y2="22">
            <stop stop-color="#667eea"/>
            <stop offset="1" stop-color="#764ba2"/>
          </linearGradient>
        </defs>
      </svg>
    </div>
    <div class="ai-ball-pulse"></div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'

const emit = defineEmits(['open'])

const isAnalyzing = ref(false)
const isDragging = ref(false)
const hasMoved = ref(false)

const position = reactive({
  x: 0,
  y: 0,
})

let dragStart = { x: 0, y: 0 }
let posStart = { x: 0, y: 0 }

function setDefaultPosition() {
  position.x = window.innerWidth - 70
  position.y = window.innerHeight - 120
}

function startDrag(e) {
  isDragging.value = true
  hasMoved.value = false
  dragStart.x = e.clientX
  dragStart.y = e.clientY
  posStart.x = position.x
  posStart.y = position.y
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

function onDrag(e) {
  const dx = e.clientX - dragStart.x
  const dy = e.clientY - dragStart.y
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
    hasMoved.value = true
  }
  const newX = Math.max(0, Math.min(window.innerWidth - 56, posStart.x + dx))
  const newY = Math.max(0, Math.min(window.innerHeight - 56, posStart.y + dy))
  position.x = newX
  position.y = newY
}

function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  snapToEdge()
}

function snapToEdge() {
  const midX = window.innerWidth / 2
  if (position.x + 28 < midX) {
    position.x = 8
  } else {
    position.x = window.innerWidth - 64
  }
}

function handleClick() {
  if (!hasMoved.value) {
    emit('open')
  }
}

function handleResize() {
  if (position.x > window.innerWidth - 64) {
    position.x = window.innerWidth - 64
  }
  if (position.y > window.innerHeight - 64) {
    position.y = window.innerHeight - 64
  }
}

defineExpose({ isAnalyzing })

onMounted(() => {
  setDefaultPosition()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.ai-floating-ball {
  position: fixed;
  z-index: 9999;
  width: 56px;
  height: 56px;
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-ball-inner {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
  z-index: 2;
}

.ai-ball-inner:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

.ai-ball-inner.analyzing {
  animation: spin 2s linear infinite;
}

.ai-ball-pulse {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  animation: pulse 2s ease-in-out infinite;
  z-index: 1;
}

@keyframes pulse {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.6;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.4);
    opacity: 0;
  }
  100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.6;
  }
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
