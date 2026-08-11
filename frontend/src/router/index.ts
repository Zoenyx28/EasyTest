import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import TestOverviewView from '../components/TestOverviewView.vue'
import TestExecutionView from '../components/TestExecutionView.vue'
import TestReportsView from '../components/TestReportsView.vue'
import TestProjectsView from '../components/TestProjectsView.vue'
import LoginView from '../components/LoginView.vue'
import RegisterView from '../components/RegisterView.vue'
import DefectView from '../components/DefectView.vue'
import RequirementsView from '../components/RequirementsView.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/cases',
  },
  {
    path: '/cases',
    name: 'cases',
    component: TestOverviewView,
  },
  {
    path: '/execution',
    name: 'execution',
    component: TestExecutionView,
  },
  {
    path: '/reports',
    name: 'reports',
    component: TestReportsView,
  },
  {
    path: '/defects',
    name: 'defects',
    component: DefectView,
  },
  {
    path: '/project',
    redirect: '/projects',
  },
  {
    path: '/projects',
    name: 'projects',
    component: TestProjectsView,
  },
  {
    path: '/requirements',
    name: 'requirements',
    component: RequirementsView,
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const publicRoutes = ['login', 'register']
  if (publicRoutes.includes(to.name as string)) {
    next()
    return
  }
  const token = localStorage.getItem('token')
  if (!token) {
    next({ name: 'login' })
    return
  }
  next()
})

export default router