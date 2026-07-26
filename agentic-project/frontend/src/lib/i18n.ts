import { useUiStore } from "../stores/uiStore";
import { translations, type Language } from "./translations";

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, key) => (key in vars ? String(vars[key]) : match));
}

function translate(language: Language, key: string, vars?: Record<string, string | number>): string {
  const template = translations[language][key] ?? translations.en[key] ?? key;
  return interpolate(template, vars);
}

/** Translate a key using the current UI language, read outside of render (event handlers,
 * store actions). Does not subscribe to language changes — use useT() inside components. */
export function t(key: string, vars?: Record<string, string | number>): string {
  return translate(useUiStore.getState().language, key, vars);
}

/** Hook form of t() — subscribes to the language store so the component re-renders when
 * the Navbar toggle flips languages. Use this inside component render bodies. */
export function useT() {
  const language = useUiStore((s) => s.language);
  return (key: string, vars?: Record<string, string | number>) => translate(language, key, vars);
}

/** Pick the singular/plural key variant based on count, then translate it. Works with both
 * t() and useT()'s returned function — pass whichever translator you have. */
export function tCount(
  translator: (key: string, vars?: Record<string, string | number>) => string,
  baseKey: string,
  count: number,
  vars?: Record<string, string | number>
): string {
  const key = count === 1 ? `${baseKey}Singular` : `${baseKey}Plural`;
  return translator(key, { count, ...vars });
}
