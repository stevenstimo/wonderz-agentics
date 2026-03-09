import React, { useState } from 'react';
import PageLayout from './PageLayout';

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '') || 'http://localhost:8090';

function ChatBubble({ message, isUser, embedded }) {
	if (embedded) {
		return (
			<div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
				<div className={`max-w-md rounded-lg p-4 text-sm whitespace-pre-wrap ${isUser ? 'bg-indigo-700 text-white' : 'bg-gray-800 text-gray-100'}`}>
					{message}
				</div>
			</div>
		);
	}
	return (
		<div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-2`}>
			<div
				className={`max-w-[70%] px-5 py-4 rounded-card shadow-sleak border text-base whitespace-pre-line font-sans ${isUser ? 'bg-white border-sleak-border text-sleak-text' : 'bg-brand-500 border-brand-500 text-white'}`}
				style={{ borderRadius: '32px' }}
			>
				{message}
			</div>
		</div>
	);
}

async function apiFetch(path, options) {
	const first = await fetch(path, options);
	if (first.ok) return first;
	if (API_URL) {
		const direct = await fetch(`${API_URL}${path}`, options);
		return direct.ok ? direct : first;
	}
	return first;
}

function DeveloperBot({ embedded = false }) {
	const [prompt, setPrompt] = useState("");
	const [chat, setChat] = useState([
		{ sender: "bot", text: embedded
			? "Hallo! Ik ben de Developer Bot. Vraag naar job #137, health, recent_errors, agents of db_stats. Ik haal de data op en geef je een analyse."
			: "Hallo! Waarmee kan ik je als developer helpen? Vraag naar jobs, errors of systeemstatus." },
	]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");

	async function sendPrompt(e) {
		e.preventDefault();
		if (!prompt.trim()) return;
		setError("");
		setLoading(true);
		setChat((prev) => [...prev, { sender: "user", text: prompt }]);
		try {
			const res = await apiFetch('/api/devbot/ask', {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ prompt }),
			});
			const data = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(data.detail || data.error || "Serverfout");
			setChat((prev) => [...prev, { sender: "bot", text: data.answer || "(Geen antwoord ontvangen)" }]);
		} catch (err) {
			setChat((prev) => [...prev, { sender: "bot", text: `Sorry: ${err.message || "Kon geen antwoord ophalen."}` }]);
			setError(err.message || "Kon geen antwoord ophalen van de backend.");
		} finally {
			setLoading(false);
			setPrompt("");
		}
	}

	const messagesArea = (
		<div className={embedded ? 'space-y-4' : ''} style={embedded ? {} : { minHeight: 320 }}>
			{chat.map((msg, i) => (
				<ChatBubble key={i} message={msg.text} isUser={msg.sender === "user"} embedded={embedded} />
			))}
			{loading && <ChatBubble message="...Antwoord wordt opgehaald..." isUser={false} embedded={embedded} />}
		</div>
	);

	const formArea = (
		<form onSubmit={sendPrompt} className="flex gap-2 mt-4">
			<input
				type="text"
				className={`flex-1 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 ${embedded ? 'bg-gray-700 text-white focus:ring-indigo-600' : 'px-4 py-4 rounded-card border border-sleak-border focus:ring-brand-500/10 bg-white text-sleak-text'}`}
				style={embedded ? {} : { borderRadius: '32px' }}
				placeholder={embedded ? "Job #137, health, recent_errors, agents..." : "Typ je vraag..."}
				value={prompt}
				onChange={e => setPrompt(e.target.value)}
				disabled={loading}
			/>
			<button
				type="submit"
				className={`rounded-lg px-4 py-2 transition font-semibold ${embedded ? 'bg-indigo-600 hover:bg-indigo-700 text-white' : 'px-8 py-4 rounded-card font-black text-white shadow-sleak bg-brand-600 hover:bg-brand-500'}`}
				style={embedded ? {} : { borderRadius: '32px' }}
				disabled={loading || !prompt.trim()}
			>
				Verstuur
			</button>
		</form>
	);

	if (embedded) {
		return (
			<div className="flex flex-col h-full bg-gray-900 text-gray-100 rounded-lg overflow-hidden">
				<div className="flex-1 overflow-y-auto p-4 space-y-4">
					{messagesArea}
				</div>
				<div className="bg-gray-800 border-t border-gray-700 p-4">
					{formArea}
					{error && <div className="mt-2 text-red-500 text-sm">{error}</div>}
				</div>
			</div>
		);
	}

	return (
		<PageLayout size="wide" padded>
			<div className="max-w-2xl mx-auto py-10 px-4 wonderz-card" style={{ background: "#F9FAFB", minHeight: 600, borderRadius: '32px' }}>
				<h1 className="text-3xl font-black mb-4 text-black font-sans">Developer Bot</h1>
				<div className="mb-6 text-black font-sans">Vraag naar jobs, errors, agents of systeemstatus. De bot haalt de data op en geeft je een analyse.</div>
				<div className="mb-6">{messagesArea}</div>
				{formArea}
				{error && <div className="mt-2 text-red-500 text-sm font-sans">{error}</div>}
			</div>
		</PageLayout>
	);
}

export default DeveloperBot;
