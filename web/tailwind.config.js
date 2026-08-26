export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primárias - Verde WR (#1B7A3A) conforme DESIGN_TOKENS.md do site institucional
        primary: {
          50: '#E8F5E9',
          100: '#C8E6C9',
          200: '#A5D6A7',
          300: '#81C784',
          400: '#66BB6A',
          500: '#047F37',
          600: '#047F37',
          700: '#0F4620',
          800: '#0D3A1A',
          900: '#0A2E14',
        },
        // Secundárias - Azul Escuro
        secondary: {
          50: '#F5F5F5',
          100: '#EEEEEE',
          200: '#E8E8E8',
          300: '#D0D0D0',
          400: '#B0B0B0',
          500: '#1E3A5F',
          600: '#1E3A5F',
          700: '#0F1E35',
          800: '#0F1E35',
          900: '#0F1E35',
        },
        // Acentos
        accent: {
          50: '#FFF3E0',
          100: '#FFE0B2',
          200: '#FFCC80',
          300: '#FFB74D',
          400: '#FFA726',
          500: '#FF6B35',
          600: '#FF6B35',
          700: '#E65100',
          800: '#BF360C',
          900: '#FF6B35',
        },
        // Neutras
        gray: {
          50: '#FAFAFA',
          100: '#F0F0F0',
          200: '#E8E8E8',
          300: '#D0D0D0',
          400: '#B0B0B0',
          500: '#999999',
          600: '#666666',
          700: '#333333',
          800: '#1A1A1A',
          900: '#000000',
        },
        // Status
        success: '#4CAF50',
        warning: '#FFC107',
        error: '#F44336',
        info: '#2196F3',
      },
      fontFamily: {
        sans: ['Poppins', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        primary: ['Poppins', 'sans-serif'],
        secondary: ['Poppins', 'sans-serif'],
      },
      boxShadow: {
        sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
        base: '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
        md: '0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06)',
        lg: '0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05)',
        xl: '0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04)',
        '2xl': '0 25px 50px rgba(0, 0, 0, 0.25)',
      },
      borderRadius: {
        sm: '4px',
        base: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
        '2xl': '20px',
      },
    },
  },
  plugins: [],
}
