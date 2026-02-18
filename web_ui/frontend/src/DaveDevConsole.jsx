import React, { useState, useEffect, useRef } from 'react';
import { Send, Code, Copy, CheckCircle } from 'lucide-react';

export default function DaveDevConsole() {
  const [dave, setDave] = useState(null);
  const [messages, setMessages] = useState([
    {
      type: 'assistant',
      text: "Hey! I'm Dave Dev, your Technical Consultant. Ask me about architecture, frontend, database, or talent management. I'll give you answers + VS Code prompts!"
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');



  async function parseJsonSafe(res) {
    const raw = await res.text();
    try {
      return raw ? JSON.parse(raw) : {};
    } catch {
      return { error: raw || 'Invalid JSON response from backend' };
    }
  }

  async function apiFetch(path, options = undefined) {
    // First try local proxy (/api -> backend in Vite dev).
    const first = await fetch(path, options);
    if (first.ok) return first;

    // Fallback for environments where proxy is unavailable.
    if (!apiBase) return first;
    const direct = await fetch(`${apiBase}${path}`, options);
    return direct.ok ? direct : first;
  }

  useEffect(() => {
    // Load Dave Dev profile
    apiFetch('/api/dave-dev/info')
      .then(parseJsonSafe)
      .then(data => setDave(data))
      .catch(err => console.error('Failed to load Dave Dev:', err));
  }, [apiBase]);

  useEffect(() => {
    // Auto-scroll to bottom
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = '0px';
    inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 180)}px`;
  }, [input]);

  const buildRequestContext = (questionText) => {
    const recentUserMessages = messages
      .filter((m) => m.type === 'user')
      .slice(-5)
      .map((m) => m.text);

    return {
      question: questionText,
      context: `Active panel: Dave Dev Console\nPage title: ${document.title}`,
      page: window.location.pathname,
      selected_tool: 'Dave Dev Console',
      recent_messages: recentUserMessages,
    };
  };

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    // Add user message
    setMessages(prev => [...prev, { type: 'user', text: input }]);
    setInput('');
    setLoading(true);

    try {
      const payload = buildRequestContext(input);
      const res = await apiFetch('/api/dave-dev/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await parseJsonSafe(res);
      if (!res.ok) {
        throw new Error(data.detail || data.error || 'Dave Dev request failed');
      }

      // Add assistant response
      setMessages(prev => [...prev, {
        type: 'assistant',
        text: data.answer || 'Ik heb nu geen antwoord kunnen vormen.',
        vscode_prompt: data.vscode_prompt,
        code_references: data.code_references,
        confidence: data.confidence
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        type: 'assistant',
        text: `Error getting response: ${err.message || 'Please try again.'}`
      }]);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-900 to-purple-900 p-4 border-b border-purple-800">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center font-bold">
            DD
          </div>
          <div>
            <h1 className="font-bold text-lg">Dave Dev</h1>
            <p className="text-xs text-gray-300">{dave?.specialization || 'Loading...'}</p>
          </div>
          <div className="ml-auto">
            <span className="inline-block px-3 py-1 bg-green-900 text-green-200 rounded-full text-xs font-semibold">
              {dave?.status || 'offline'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-md ${msg.type === 'user' ? 'bg-indigo-700 text-white' : 'bg-gray-800 text-gray-100'} rounded-lg p-4`}>
              <div className="text-sm whitespace-pre-wrap leading-relaxed">{msg.text}</div>

              {msg.vscode_prompt && (
                <div className="mt-3 bg-gray-900 rounded p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Code className="w-4 h-4 text-green-400" />
                      <span className="text-xs font-semibold text-green-400">VS CODE PROMPT</span>
                    </div>
                    <button
                      onClick={() => copyToClipboard(msg.vscode_prompt, i)}
                      className="text-gray-400 hover:text-gray-200 transition"
                    >
                      {copiedIndex === i ? (
                        <CheckCircle className="w-4 h-4 text-green-400" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                  <p className="text-xs text-gray-300 font-mono bg-black p-2 rounded mt-2 max-h-24 overflow-y-auto">
                    {msg.vscode_prompt}
                  </p>
                </div>
              )}

              {msg.code_references && msg.code_references.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-xs font-semibold text-yellow-400 mb-1">Code References:</p>
                  <div className="flex flex-wrap gap-1">
                    {msg.code_references.map((ref, j) => (
                      <span key={j} className="text-xs bg-yellow-900 text-yellow-200 px-2 py-1 rounded font-mono">
                        {ref}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {msg.confidence !== undefined && (
                <div className="mt-2 text-xs text-gray-400">
                  Confidence: {Math.round(msg.confidence * 100)}%
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex gap-2">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-100"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-200"></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-gray-800 border-t border-gray-700 p-4">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder="Ask about architecture, frontend, database..."
            rows={1}
            className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600 resize-none overflow-y-auto"
            disabled={loading}
          />
          <button
            onClick={handleSendMessage}
            disabled={loading || !input.trim()}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 transition flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
