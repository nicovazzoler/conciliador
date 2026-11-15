import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // En desarrollo, lo que empieza con /api va a FastAPI: misma dirección, sin CORS.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
