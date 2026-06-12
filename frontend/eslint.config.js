import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // Standard fetch-on-mount effects call an async loader that setStates
      // after awaiting; this newer rule is overly strict for that pattern.
      'react-hooks/set-state-in-effect': 'warn',
      // Context provider + its useX() hook live in one file by design; this is
      // a dev-only Fast Refresh concern, not a correctness/build issue.
      'react-refresh/only-export-components': 'warn',
    },
  },
])
