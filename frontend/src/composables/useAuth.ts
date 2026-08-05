import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useApi } from './useApi';
import type { UserInfo, AuthResponse } from '../types';

const currentUser = ref<UserInfo | null>(null);
const token = ref<string | null>(localStorage.getItem('token'));

const isLoggedIn = computed(() => !!token.value && !!currentUser.value);

export function useAuth() {
  const router = useRouter();
  const api = useApi();

  async function login(username: string, password: string): Promise<void> {
    const res = await api.post<AuthResponse>('/auth/login', { username, password });
    token.value = res.token;
    currentUser.value = res.user;
    localStorage.setItem('token', res.token);
    localStorage.setItem('user', JSON.stringify(res.user));
  }

  async function register(username: string, nickname: string, password: string, avatar?: string): Promise<void> {
    const res = await api.post<AuthResponse>('/auth/register', {
      username,
      nickname,
      password,
      avatar_url: avatar,
    });
    token.value = res.token;
    currentUser.value = res.user;
    localStorage.setItem('token', res.token);
    localStorage.setItem('user', JSON.stringify(res.user));
  }

  function logout(): void {
    token.value = null;
    currentUser.value = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    router.push('/login');
  }

  async function fetchMe(): Promise<void> {
    try {
      const user = await api.get<UserInfo>('/auth/me');
      currentUser.value = user;
      localStorage.setItem('user', JSON.stringify(user));
    } catch {
      logout();
    }
  }

  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
  }

  async function uploadAvatar(file: File): Promise<string> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.postFormData<{ avatar_url: string }>('/auth/avatar', formData);
    if (currentUser.value) {
      currentUser.value.avatar_url = res.avatar_url;
      localStorage.setItem('user', JSON.stringify(currentUser.value));
    }
    return res.avatar_url;
  }

  async function updateProfile(data: { nickname?: string; avatar_url?: string }): Promise<UserInfo> {
    const user = await api.put<UserInfo>('/auth/profile', data);
    currentUser.value = user;
    localStorage.setItem('user', JSON.stringify(user));
    return user;
  }

  function init(): void {
    const savedToken = localStorage.getItem('token');
    if (savedToken) {
      token.value = savedToken;
      const savedUser = localStorage.getItem('user');
      if (savedUser) {
        try {
          currentUser.value = JSON.parse(savedUser);
        } catch {
          // ignore
        }
      }
      fetchMe();
    }
  }

  return {
    isLoggedIn,
    currentUser,
    token,
    login,
    register,
    logout,
    fetchMe,
    changePassword,
    uploadAvatar,
    updateProfile,
    init,
  };
}