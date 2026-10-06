<script setup lang="ts">
import { ref } from 'vue'
import { X } from '@lucide/vue'

const props = defineProps<{ modelValue: string[]; max?: number; placeholder?: string; id?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const draft = ref('')
const limit = props.max ?? 20
const fold = (value: string): string => value.normalize('NFKC').toLowerCase()

function commit(raw: string): void {
  const next = [...props.modelValue]
  for (const piece of raw.split(/[\n,，、;；]/)) {
    const word = piece.trim().replace(/\s+/g, ' ').slice(0, 64)
    if (word && next.length < limit && !next.some((existing) => fold(existing) === fold(word))) next.push(word)
  }
  if (next.length !== props.modelValue.length) emit('update:modelValue', next)
  draft.value = ''
}

const remove = (index: number): void => emit('update:modelValue', props.modelValue.filter((_, i) => i !== index))

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault()
    commit(draft.value)
  } else if (event.key === 'Backspace' && !draft.value && props.modelValue.length) {
    remove(props.modelValue.length - 1)
  }
}

function onPaste(event: ClipboardEvent): void {
  const text = event.clipboardData?.getData('text') ?? ''
  if (/[\n,，、;；]/.test(text)) {
    event.preventDefault()
    commit(draft.value + text)
  }
}
</script>

<template>
  <div>
    <div class="tags" @click="($refs.input as HTMLInputElement).focus()">
      <span v-for="(tag, index) in modelValue" :key="tag" class="chip violet">
        {{ tag }}
        <button type="button" class="x" :aria-label="`移除 ${tag}`" @click.stop="remove(index)"><X :size="12" /></button>
      </span>
      <input :id="id" ref="input" v-model="draft" class="entry" :placeholder="modelValue.length ? '' : placeholder" :disabled="modelValue.length >= limit" aria-label="添加关键词" @keydown="onKey" @paste="onPaste" @blur="commit(draft)" />
    </div>
    <small class="count num">{{ modelValue.length }} / {{ limit }}</small>
  </div>
</template>

<style scoped>
.tags { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-height: 38px; padding: 5px 8px; background: var(--panel); border: 1px solid var(--strong); border-radius: 8px; cursor: text; transition: border-color 0.12s, box-shadow 0.12s; }
.tags:focus-within { border-color: var(--black); box-shadow: 0 0 0 3px var(--ring); }
.tags .chip { padding-right: 3px; font-size: 12px; height: 24px; }
.x { display: grid; place-items: center; width: 16px; height: 16px; border: 0; border-radius: 50%; background: transparent; color: inherit; opacity: 0.7; }
.x:hover { opacity: 1; background: color-mix(in srgb, currentColor 14%, transparent); }
.entry { flex: 1; min-width: 120px; height: 24px; padding: 0 4px; border: 0; outline: none; background: transparent; font-size: 13px; }
.count { display: block; margin-top: 4px; text-align: right; color: var(--muted); font-size: 11px; }
</style>
