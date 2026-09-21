import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  resolve: {
    tsconfigPaths: true,
  },
  plugins: [
    tanstackStart({
      spa: { enabled: true },
      prerender: { enabled: true },
      server: { entry: "server" },
    }),
    react(),
    tailwindcss(),
  ],
});


