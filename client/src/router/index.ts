import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'lobby',
      component: () => import('../views/LobbyView.vue'),
    },
    {
      path: '/game',
      name: 'game',
      component: () => import('../views/GameView.vue'),
    },
    {
      path: '/gameover',
      name: 'gameover',
      component: () => import('../views/GameOverView.vue'),
    },
  ],
})

export default router
