/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0a0a0f",
        panel:   "#111118",
        border:  "#1e1e2e",
        muted:   "#4a4a6a",
        primary: "#3a7bfd",
        accent:  "#00d4aa",
      },
    },
  },
  plugins: [],
};
