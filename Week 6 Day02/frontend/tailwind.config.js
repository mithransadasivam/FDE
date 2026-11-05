/** @type {import('tailwindcss').Config} */
// The console's colours match the course decks: navy, teal, ember and amber.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "Segoe UI", "sans-serif"] },
      colors: {
        navy: { DEFAULT: "#1B1F3B", 600: "#30365E" },
        teal: { DEFAULT: "#0E8F7E", 50: "#EEF7F5", 100: "#D6EEE9" },
        ember: { DEFAULT: "#E8552F", 50: "#FDEEE9" },
        amber: { DEFAULT: "#D98E04", 50: "#FDF5E3" },
        ink: { DEFAULT: "#1B1F3B", 2: "#5E6378", 3: "#9A9EB3" },
        mist: "#F4F5FA",
      },
    },
  },
  plugins: [],
};
