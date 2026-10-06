<script setup lang="ts">
import { watch } from 'vue'
import AppShell from './layouts/AppShell.vue'
import ConfirmHost from './components/ConfirmHost.vue'
import ToastHost from './components/ToastHost.vue'
import LoginView from './views/LoginView.vue'
import { auth } from './lib/auth'
import { refresh, resetStore, startPolling, stopPolling } from './lib/store'

// Load data and keep it fresh while signed in; drop it all on sign-out.
watch(
  () => auth.token,
  (token) => {
    if (token) {
      void refresh()
      startPolling()
    } else {
      stopPolling()
      resetStore()
    }
  },
  { immediate: true },
)
</script>

<template>
  <AppShell v-if="auth.token" />
  <LoginView v-else />
  <ConfirmHost />
  <ToastHost />
</template>
