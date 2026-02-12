
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8090";

function ChatBubble({ message, isUser }) {
	return (
		<div
			className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-2`}
		>
			<div
				className={`max-w-[70%] px-5 py-3 rounded-2xl shadow-sm border text-base whitespace-pre-line '
					${isUser
						? 'bg-white border-gray-200 text-gray-900'
						: 'bg-[var(--purple-tech,#8B5CF6)] border-[var(--purple-tech,#8B5CF6)] text-white'}
				`}
				style={{ borderRadius: 24 }}
			>
				{message}
			</div>
		</div>
	);
}

export default function DeveloperBot() {
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
		<div className="max-w-2xl mx-auto py-10 px-4" style={{ background: "var(--bg-main,#F9FAFB)", minHeight: 600, borderRadius: 32 }}>
			<h1 className="text-3xl font-bold mb-4" style={{ color: "var(--purple-tech,#8B5CF6)" }}>Developer Bot</h1>
			<div className="mb-6 text-gray-700">Stel je development-vraag aan de AI. Je krijgt direct antwoord in de stijl van Wonderz/Sleak.</div>

			<div className="flex flex-col gap-2 mb-6" style={{ minHeight: 320 }}>
				{chat.map((msg, i) => (
					<ChatBubble key={i} message={msg.text} isUser={msg.sender === "user"} />
				))}
				{loading && <ChatBubble message="...Antwoord wordt opgehaald..." isUser={false} />}
			</div>

			<form onSubmit={sendPrompt} className="flex gap-2 mt-4">
				<input
					type="text"
					className="flex-1 px-4 py-3 rounded-2xl border border-gray-300 focus:ring-2 focus:ring-[var(--purple-tech,#8B5CF6)] focus:outline-none bg-white text-gray-900 shadow-sm"
					style={{ borderRadius: 24 }}
					placeholder="Typ je vraag..."
					value={prompt}
					onChange={e => setPrompt(e.target.value)}
					disabled={loading}
				/>
				<button
					type="submit"
					className="px-6 py-3 rounded-2xl font-semibold text-white shadow-sm"
					style={{ background: "var(--purple-tech,#8B5CF6)", borderRadius: 24 }}
					disabled={loading || !prompt.trim()}
				>
					Verstuur
				</button>
			</form>
			{error && <div className="mt-2 text-red-500 text-sm">{error}</div>}
		</div>
	);
}
