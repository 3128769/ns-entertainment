import { createApp } from 'vue'
import App from './App.vue'
import { startTheme } from './lib/theme'
import { router } from './router'
import './styles/tokens.css'
import './styles/base.css'
import './styles/ui.css'

startTheme()
createApp(App).use(router).mount('#app')
