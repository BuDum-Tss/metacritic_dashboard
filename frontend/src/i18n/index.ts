import { useSyncExternalStore } from 'react'

import { en } from './en'
import { ru, type Key } from './ru'

export type Lang = 'ru' | 'en'
export type { Key }

const STORAGE_KEY = 'language'
const dictionaries: Record<Lang, Record<Key, string>> = { ru, en }

function initial(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'ru' || saved === 'en') return saved
  } catch {
    // storage may be blocked: the browser language decides
  }
  return navigator.language.toLowerCase().startsWith('ru') ? 'ru' : 'en'
}

let current: Lang = initial()
const listeners = new Set<() => void>()

export function getLang(): Lang {
  return current
}

export function setLang(lang: Lang) {
  if (lang === current) return
  current = lang
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // the choice then lasts until the page is closed
  }
  document.documentElement.lang = lang
  listeners.forEach((listener) => listener())
}

// re-renders a component when the language changes
export function useLang(): Lang {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    getLang,
  )
}

// the locale of dates and numbers
export function locale(): string {
  return current === 'ru' ? 'ru-RU' : 'en-US'
}

type Params = Record<string, string | number>

function fill(text: string, params?: Params): string {
  return params ? text.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match)) : text
}

// true when the dictionary has the key: for the labels whose key is made of a value from the server
export function hasKey(key: string): key is Key {
  return key in ru
}

export function t(key: Key, params?: Params): string {
  return fill(dictionaries[current][key], params)
}

// A word that depends on the number: the forms are separated by "|" (one | few | many in Russian,
// one | other in English) and {n} is the number.
export function tn(key: Key, n: number, params?: Params): string {
  const forms = dictionaries[current][key].split('|').map((form) => form.trim())
  const rule = new Intl.PluralRules(locale()).select(n)
  const index = forms.length >= 3 ? (rule === 'one' ? 0 : rule === 'few' ? 1 : 2) : rule === 'one' ? 0 : 1
  return fill(forms[Math.min(index, forms.length - 1)], { n, ...params })
}

document.documentElement.lang = current
