import React, { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8090";

function ChatBubble({ message, isUser }) {
	return (
		<div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-2`}>
			<div
				className={`max-w-[70%] px-5 py-4 rounded-card shadow-sleak border text-base whitespace-pre-line font-sans '
					${isUser
						? 'bg-white border-sleak-border text-sleak-text'
						: 'bg-brand-500 border-brand-500 text-white'}
				`}
				style={{ borderRadius: '32px' }}
			>
				{message}
			</div>
		</div>
	);
}

function DeveloperBot() {
	const [prompt, setPrompt] = useState("");
	const [chat, setChat] = useState([
		{ sender: "bot", text: "Hallo! Waarmee kan ik je als developer helpen?" },
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
				const res = await fetch(`${API_URL}/api/devbot/ask`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ prompt }),
				});
				if (!res.ok) throw new Error("Serverfout");
				const data = await res.json();
				setChat((prev) => [
					...prev,
					{ sender: "bot", text: data.answer || "(Geen antwoord ontvangen)" },
				]);
			} catch (err) {
				setChat((prev) => [
					...prev,
					{ sender: "bot", text: "Sorry, er ging iets mis met het ophalen van het antwoord." },
				]);
				setError("Kon geen antwoord ophalen van de backend.");
			} finally {
				setLoading(false);
				setPrompt("");
			}
		}

		return (
			<div className="max-w-2xl mx-auto py-10 px-4 wonderz-card" style={{ background: "#F9FAFB", minHeight: 600, borderRadius: '32px' }}>
				<h1 className="text-3xl font-black mb-4 text-brand-600 font-sans">Developer Bot</h1>
				<div className="mb-6 text-sleak-secondary font-sans">Stel je development-vraag aan de AI. Je krijgt direct antwoord in de Wonderz-stijl.</div>

				<div className="flex flex-col gap-2 mb-6" style={{ minHeight: 320 }}>
					{chat.map((msg, i) => (
						<ChatBubble key={i} message={msg.text} isUser={msg.sender === "user"} />
					))}
					{loading && <ChatBubble message="...Antwoord wordt opgehaald..." isUser={false} />}
				</div>

				<form onSubmit={sendPrompt} className="flex gap-2 mt-4">
					<input
						type="text"
						className="flex-1 px-4 py-4 rounded-card border border-sleak-border focus:ring-4 focus:ring-brand-500/10 focus:outline-none bg-white text-sleak-text shadow-sleak font-sans"
						style={{ borderRadius: '32px' }}
						placeholder="Typ je vraag..."
						value={prompt}
						onChange={e => setPrompt(e.target.value)}
						disabled={loading}
					/>
					<button
						type="submit"
						className="px-8 py-4 rounded-card font-black text-white shadow-sleak bg-brand-600 hover:bg-brand-500 transition-all font-sans"
						style={{ borderRadius: '32px' }}
						disabled={loading || !prompt.trim()}
					>
						Verstuur
					</button>
				</form>
				{error && <div className="mt-2 text-red-500 text-sm font-sans">{error}</div>}
			</div>
		);
	}

export default DeveloperBot;
