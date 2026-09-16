import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypeScript from 'eslint-config-next/typescript';

const configuredNext = nextVitals.map((config) => {
  if (!config.rules?.['react-hooks/set-state-in-effect']) return config;
  return {
    ...config,
    rules: {
      ...config.rules,
      // These React Compiler rules were not enforced by the former `next lint`
      // setup. Keep them visible without mixing component rewrites into cleanup.
      'react-hooks/immutability': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
    },
  };
});

const configuredTypeScript = nextTypeScript.map((config) => {
  if (!config.rules?.['@typescript-eslint/no-explicit-any']) return config;
  return {
    ...config,
    rules: {
      ...config.rules,
      // Preserve the existing loose typing baseline as warnings for later hardening.
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-empty-object-type': 'warn',
      '@typescript-eslint/no-require-imports': 'off',
    },
  };
});

export default defineConfig([
  ...configuredNext,
  ...configuredTypeScript,
  globalIgnores([
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
  ]),
]);
