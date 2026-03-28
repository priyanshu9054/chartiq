import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const getStocks = () => api.get('/api/stocks');

export const getSymbolDetail = (symbol) => api.get(`/api/stocks/${symbol}`);

export const getLeaderboard = () => api.get('/api/leaderboard');

export const sendChatMessage = (message, session_id, symbol_context) => 
  api.post('/api/chat', { message, session_id, symbol_context });

export default api;
