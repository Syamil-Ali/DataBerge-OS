import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [tailwindcss(), react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3-')) return 'charts';
          if (id.includes('node_modules/react-markdown') || id.includes('node_modules/remark-') || id.includes('node_modules/rehype-')) return 'markdown';
          if (id.includes('node_modules/lucide-react')) return 'icons';
          if (id.includes('node_modules/react')) return 'react-vendor';
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
    },
  },
});
