import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{proxy:{'/api/espn':{target:'http://localhost:10000'}}},preview:{host:'0.0.0.0',allowedHosts:['cams-stats.onrender.com']}});
