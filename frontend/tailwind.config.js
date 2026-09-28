/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18252c",
        moss: "#176b5b",
        lime: "#ffd166",
        paper: "#f8f4eb",
        coral: "#e76f51",
      },
      fontFamily: {
        display: ["Georgia", "serif"],
        sans: ["Trebuchet MS", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
