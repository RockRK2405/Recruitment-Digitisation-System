/**
 * LLM provider abstraction for the gateway.
 * Priority: OpenAI-compatible (FreeLLMAPI/OpenRouter/Groq) → Ollama → Gemini
 * Configured via env vars; first reachable provider wins.
 */
import axios from 'axios'

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

const env = process.env

async function callOpenAiCompatible(messages: ChatMessage[]): Promise<string | null> {
  const baseUrl = (env.OPENAI_COMPATIBLE_BASE_URL || '').replace(/\/+$/, '')
  const apiKey = env.OPENAI_COMPATIBLE_API_KEY || ''
  const model = env.OPENAI_COMPATIBLE_MODEL || 'auto'
  if (!baseUrl || !apiKey) return null
  try {
    const res = await axios.post(
      `${baseUrl}/chat/completions`,
      { model, messages, temperature: 0.3 },
      { headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' }, timeout: 120000 },
    )
    return res.data?.choices?.[0]?.message?.content?.trim() || null
  } catch (err) {
    console.warn('OpenAI-compatible LLM call failed:', err instanceof Error ? err.message : err)
    return null
  }
}

async function callOllamaChat(messages: ChatMessage[]): Promise<string | null> {
  const url = (env.OLLAMA_URL || 'http://localhost:11434/api/generate').replace('/api/generate', '/api/chat')
  const model = env.OLLAMA_MODEL || 'llama3'
  try {
    const res = await axios.post(url, { model, messages, stream: false }, { timeout: 120000 })
    return res.data?.message?.content?.trim() || null
  } catch (err) {
    console.warn('Ollama chat failed:', err instanceof Error ? err.message : err)
    return null
  }
}

async function callGeminiChat(messages: ChatMessage[]): Promise<string | null> {
  const apiKey = env.GEMINI_API_KEY || ''
  const model = env.GEMINI_MODEL || 'gemini-2.5-flash'
  if (!apiKey) return null
  try {
    const flat = messages.map((m) => {
      if (m.role === 'system') return `System: ${m.content}\n\n`
      if (m.role === 'user') return `User: ${m.content}\n`
      return `Assistant: ${m.content}\n`
    }).join('') + 'Assistant:'
    const res = await axios.post(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
      { contents: [{ parts: [{ text: flat }] }], generationConfig: { temperature: 0.3 } },
      { timeout: 120000 },
    )
    return res.data?.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || null
  } catch (err) {
    console.warn('Gemini chat failed:', err instanceof Error ? err.message : err)
    return null
  }
}

export async function chatLLM(messages: ChatMessage[]): Promise<{ text: string; provider: string }> {
  const preferred = (env.LLM_PROVIDER || 'openai_compatible').toLowerCase()

  const tryOrder: Array<{ name: string; fn: () => Promise<string | null> }> = []
  if (preferred === 'openai_compatible') {
    tryOrder.push({ name: 'openai_compatible', fn: () => callOpenAiCompatible(messages) })
    tryOrder.push({ name: 'ollama', fn: () => callOllamaChat(messages) })
    tryOrder.push({ name: 'gemini', fn: () => callGeminiChat(messages) })
  } else if (preferred === 'ollama') {
    tryOrder.push({ name: 'ollama', fn: () => callOllamaChat(messages) })
    tryOrder.push({ name: 'openai_compatible', fn: () => callOpenAiCompatible(messages) })
    tryOrder.push({ name: 'gemini', fn: () => callGeminiChat(messages) })
  } else {
    tryOrder.push({ name: 'gemini', fn: () => callGeminiChat(messages) })
    tryOrder.push({ name: 'openai_compatible', fn: () => callOpenAiCompatible(messages) })
    tryOrder.push({ name: 'ollama', fn: () => callOllamaChat(messages) })
  }

  for (const provider of tryOrder) {
    const result = await provider.fn()
    if (result) return { text: result, provider: provider.name }
  }
  return {
    text: "I'm unable to reach any LLM right now. Check that your LLM provider is configured in .env (LLM_PROVIDER + corresponding API key or URL).",
    provider: 'none',
  }
}

export async function completeLLM(prompt: string): Promise<string> {
  const { text } = await chatLLM([{ role: 'user', content: prompt }])
  return text
}
