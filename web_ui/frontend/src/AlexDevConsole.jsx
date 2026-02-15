import React, { useState, useEffect, useRef } from 'react';
import { Send } from 'lucide-react';

export default function AlexDevConsole() {
  const [alex, setAlex] = useState(null);
  const [messages, setMessages] = useState([
    {
      type: 'assistant',
      text: "Hey! I'm Alex Dev, frontend engineer. Ask me about UI, layout stability, and component quality."
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
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
    const first = await fetch(path, options);
    if (first.ok) return first;
    if (!apiBase) return first;
    const direct = await fetch(`${apiBase}${path}`, options);
    return direct.ok ? direct : first;
  }

  useEffect(() => {
    apiFetch('/api/alex-dev/info')
      .then(parseJsonSafe)
      .then(data => setAlex(data))
      .catch(() => setAlex(null));
  }, [apiBase]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;
    const question = input;
    setMessages(prev => [...prev, { type: 'user', text: question }]);
    setInput('');
    setLoading(true);

    try {
      const attempts = [
        {
          path: '/api/alex-dev/ask',
          body: { question },
        },
        {
          path: '/api/devbot/ask',
          body: {
            prompt: question,
            question,
            agent_id: 'alex-dev',
            selected_tool: 'Alex Dev Console',
          },
        },
        {
          path: '/api/dave-dev/ask',
          body: {
            question: `Beantwoord als Alex Dev (frontend engineer). Vraag: ${question}`,
          },
        },
      ];

      let data = null;
      let lastError = 'Alex Dev endpoint unavailable';
      for (const attempt of attempts) {
        const res = await apiFetch(attempt.path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(attempt.body),
        });
        const parsed = await parseJsonSafe(res);
        if (res.ok) {
          data = parsed;
          break;
        }
        lastError = parsed?.detail || parsed?.error || `${res.status} ${res.statusText}` || lastError;
      }

      if (!data) {
        throw new Error(lastError);
      }

      setMessages(prev => [...prev, {
        type: 'assistant',
        text: data.answer || data.response || 'Alex kon nu geen antwoord formuleren.'
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        type: 'assistant',
        text: `Alex Dev is niet bereikbaar: ${err.message || 'probeer opnieuw.'}`
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100 rounded-lg overflow-hidden">
      <div className="bg-gradient-to-r from-cyan-900 to-blue-900 p-4 border-b border-cyan-800">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-cyan-600 flex items-center justify-center font-bold">
            AD
          </div>
          <div>
            <h1 className="font-bold text-lg">Alex Dev</h1>
            <p className="text-xs text-gray-300">{alex?.specialization || 'Frontend engineer'}</p>
          </div>
          <div className="ml-auto">
            <span className="inline-block px-3 py-1 bg-green-900 text-green-200 rounded-full text-xs font-semibold">
              {alex?.status || 'active'}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-md ${msg.type === 'user' ? 'bg-cyan-700 text-white' : 'bg-gray-800 text-gray-100'} rounded-lg p-4`}>
              <p className="text-sm">{msg.text}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 rounded-lg p-4 text-xs text-gray-300">Alex denkt na...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="bg-gray-800 border-t border-gray-700 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Vraag iets aan Alex Dev..."
            className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-600"
            disabled={loading}
          />
          <button
            onClick={handleSendMessage}
            disabled={loading || !input.trim()}
            className="bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 transition flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
