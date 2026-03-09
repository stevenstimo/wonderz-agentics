import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Briefcase, BrainCircuit, ShieldCheck, Info, UserPlus, GraduationCap } from 'lucide-react';
import PageLayout from './PageLayout';
import AuthorizeRecruitButton from './components/AuthorizeRecruitButton';
import { useHiringHall } from './hooks/useHiringHall';
import { apiUrl } from './apiClient';

const VALID_TOOLS = [
  { id: 'read_product', label: 'Read Product' },
  { id: 'write_copy', label: 'Write Copy' },
  { id: 'read_analytics', label: 'Read Analytics' },
  { id: 'write_social', label: 'Write Social' },
  { id: 'read_tickets', label: 'Read Tickets' },
  { id: 'write_tickets', label: 'Write Tickets' },
  { id: 'read_jobs', label: 'Read Jobs' },
  { id: 'send_report', label: 'Send Report' },
  { id: 'web_search', label: 'Web Search' },
  { id: 'read_lessons', label: 'Read Lessons' },
];

const CATEGORIES = [
  'Management',
  'Content',
  'Marketing',
  'Operations',
  'Technical',
  'Support',
  'Analytics',
  'Custom',
];

const INITIAL_FORM_DATA = {
  agent_name: '',
  role: '',
  goal: '',
  category: 'Custom',
  system_prompt: '',
  knowledge_sources: [],
  tool_whitelist: [],
};

const TAB_RECRUIT = 'recruit';
const TAB_PROMOTE = 'promote';

const HiringHall = ({ onHire }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const promoteId = searchParams.get('promote');
  const [activeTab, setActiveTab] = useState(promoteId ? TAB_PROMOTE : TAB_RECRUIT);
  const [formData, setFormData] = useState({ ...INITIAL_FORM_DATA });
  const { recruit, isLoading, error, success } = useHiringHall();

  const [readyNewbies, setReadyNewbies] = useState([]);
  const [loadingNewbies, setLoadingNewbies] = useState(false);
  const [hiringNewbieId, setHiringNewbieId] = useState(null);
  const [hireError, setHireError] = useState(null);

  useEffect(() => {
    if (promoteId) setActiveTab(TAB_PROMOTE);
  }, [promoteId]);

  useEffect(() => {
    if (activeTab === TAB_PROMOTE) {
      setLoadingNewbies(true);
      fetch(apiUrl('/api/newbies/ready'))
        .then((r) => r.ok ? r.json() : [])
        .then((data) => setReadyNewbies(Array.isArray(data) ? data : []))
        .catch(() => setReadyNewbies([]))
        .finally(() => setLoadingNewbies(false));
    }
  }, [activeTab]);

  const handleHireNewbie = async (newbie) => {
    setHiringNewbieId(newbie.newbie_id);
    setHireError(null);
    try {
      const res = await fetch(apiUrl(`/api/newbies/${newbie.newbie_id}/hire`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setSearchParams((prev) => { const next = new URLSearchParams(prev); next.delete('promote'); return next; });
        setReadyNewbies((prev) => prev.filter((n) => n.newbie_id !== newbie.newbie_id));
        onHire?.(data);
      } else {
        setHireError(data.detail || `Hire mislukt (${res.status})`);
      }
    } catch (err) {
      setHireError(err.message || 'Hire mislukt');
    } finally {
      setHiringNewbieId(null);
    }
  };

  // Bij success: volledig form reset — inclusief system_prompt textarea (expliciet clearen)
  // reset() niet aanroepen: success banner blijft zichtbaar; recruit() cleart bij volgende submit
  useEffect(() => {
    if (success) {
      setFormData({
        agent_name: '',
        role: '',
        goal: '',
        category: 'Custom',
        system_prompt: '',
        knowledge_sources: [],
        tool_whitelist: [],
      });
      onHire?.(success);
    }
  }, [success, onHire]);

  const toggleTool = (id) => {
    setFormData((prev) => ({
      ...prev,
      tool_whitelist: prev.tool_whitelist.includes(id)
        ? prev.tool_whitelist.filter((t) => t !== id)
        : [...prev.tool_whitelist, id],
    }));
  };

  const handleKnowledgeChange = (e) => {
    const text = e.target.value || '';
    const urls = text
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((url) => ({ url, status: 'pending' }));
    setFormData((prev) => ({ ...prev, knowledge_sources: urls }));
  };

  const knowledgeText = formData.knowledge_sources
    .map((s) => (typeof s === 'string' ? s : s?.url)).filter(Boolean).join('\n');

  const agentFormData = {
    agent_name: formData.agent_name,
    role: formData.role,
    category: formData.category,
    goal: formData.goal,
    system_prompt: formData.system_prompt,
    tool_whitelist: formData.tool_whitelist,
    knowledge_sources: formData.knowledge_sources,
  };

  return (
    <PageLayout variant="inner" size="medium" className="space-y-12 animate-in zoom-in-95 duration-500 pb-24">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-black text-[#111827] tracking-tight">Recruit New Crew Member</h1>
        <p className="text-[#6B7280] text-lg max-w-2xl mx-auto">
          Configureer het &quot;Brein&quot; van je agent. Definieer hun persona, kennisbasis en operationele tools.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[#E5E7EB]">
        <button
          type="button"
          onClick={() => setActiveTab(TAB_RECRUIT)}
          className={`px-6 py-3 font-semibold rounded-t-xl transition-colors ${
            activeTab === TAB_RECRUIT ? 'bg-white border border-[#E5E7EB] border-b-0 text-[#1d62e3]' : 'text-[#6B7280] hover:text-[#111827]'
          }`}
        >
          <span className="flex items-center gap-2">
            <Briefcase size={18} />
            Recruit from scratch
          </span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab(TAB_PROMOTE)}
          className={`px-6 py-3 font-semibold rounded-t-xl transition-colors ${
            activeTab === TAB_PROMOTE ? 'bg-white border border-[#E5E7EB] border-b-0 text-[#1d62e3]' : 'text-[#6B7280] hover:text-[#111827]'
          }`}
        >
          <span className="flex items-center gap-2">
            <GraduationCap size={18} />
            Promote Newbie
            {readyNewbies.length > 0 && (
              <span className="ml-1 px-2 py-0.5 rounded-full bg-green-100 text-green-800 text-xs font-bold">
                {readyNewbies.length}
              </span>
            )}
          </span>
        </button>
      </div>

      {activeTab === TAB_PROMOTE && (
        <div className="bg-white rounded-[32px] border border-[#E5E7EB] p-10 shadow-sleak">
          <h2 className="text-xl font-bold text-[#111827] mb-4">Ready Newbies</h2>
          <p className="text-[#6B7280] text-sm mb-6">
            Newbies met readiness ≥ 70. Klik op Hire om ze direct naar de crew te promoveren.
          </p>
          {hireError && (
            <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{hireError}</div>
          )}
          {loadingNewbies ? (
            <p className="text-[#6B7280] text-sm">Laden...</p>
          ) : readyNewbies.length === 0 ? (
            <p className="text-[#6B7280] text-sm">Geen ready newbies. Train newbies op de Newbies-pagina tot readiness ≥ 70.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {readyNewbies.map((n) => (
                <div
                  key={n.newbie_id}
                  className={`rounded-xl border p-5 transition ${
                    promoteId === n.newbie_id ? 'border-[#1d62e3] bg-[#f0f6ff]' : 'border-[#E5E7EB] bg-[#F9FAFB] hover:border-[#1d62e3]/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-[#111827]">{n.newbie_name || '—'}</h3>
                      {n.suggested_role && <span className="text-sm text-[#6B7280]">{n.suggested_role}</span>}
                      <p className="text-xs text-[#6B7280] mt-1 line-clamp-2">{n.persona || ''}</p>
                      <span className="text-xs font-medium text-green-600 mt-2 block">Readiness: {n.readiness_score ?? 0}%</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleHireNewbie(n)}
                      disabled={hiringNewbieId === n.newbie_id}
                      className="flex items-center gap-2 px-4 py-2 bg-[#1d62e3] text-white rounded-xl font-medium hover:bg-[#1557c7] disabled:opacity-50"
                    >
                      <UserPlus size={18} />
                      {hiringNewbieId === n.newbie_id ? 'Bezig...' : 'Hire'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === TAB_RECRUIT && (
      <form onSubmit={(e) => e.preventDefault()} className="space-y-10">
        {/* Section 1: Core Identity */}
        <div className="bg-white rounded-[32px] border border-[#E5E7EB] p-10 shadow-sleak space-y-8">
          <div className="flex items-center gap-3 border-b border-[#F9FAFB] pb-6">
            <div className="w-10 h-10 bg-[#f0f6ff] text-[#1d62e3] rounded-xl flex items-center justify-center">
              <Briefcase size={20} />
            </div>
            <h2 className="text-xl font-bold text-[#111827]">Core Identity</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Name</label>
              <input
                required
                placeholder="e.g. Donna Paulsen"
                className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all font-bold"
                value={formData.agent_name}
                onChange={(e) => setFormData({ ...formData, agent_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Role</label>
              <input
                required
                placeholder="e.g. personal-assistant"
                className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all font-bold"
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Goal</label>
              <input
                required
                placeholder="e.g. Elke dag proactief rapporteren over afgesloten jobs..."
                className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all font-bold"
                value={formData.goal}
                onChange={(e) => setFormData({ ...formData, goal: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Category</label>
              <select
                className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all font-bold"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Section 2: The Brain (System Instruction) */}
        <div className="bg-white rounded-[32px] border border-[#E5E7EB] p-10 shadow-sleak space-y-8">
          <div className="flex items-center gap-3 border-b border-[#F9FAFB] pb-6">
            <div className="w-10 h-10 bg-[#f5f3ff] text-[#8B5CF6] rounded-xl flex items-center justify-center">
              <BrainCircuit size={20} />
            </div>
            <h2 className="text-xl font-bold text-[#111827]">Agent Persona & Brain</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">
                System Instructions
              </label>
              <div className="flex items-center gap-1.5 text-[#6B7280]">
                <Info size={12} />
                <span className="text-[10px] font-bold">Dit definieert het gedrag en de toon van de agent.</span>
              </div>
            </div>
            <textarea
              required
              placeholder="Je bent een empathische support agent..."
              className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-6 py-6 rounded-[24px] focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all min-h-[160px] font-medium text-[#111827] leading-relaxed"
              value={formData.system_prompt}
              onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
            />
          </div>

          <div className="space-y-4">
            <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">
              Knowledge Sources (URLs, één per regel)
            </label>
            <textarea
              placeholder="https://docs.example.com/..."
              className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-6 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all min-h-[80px] font-medium"
              value={knowledgeText}
              onChange={handleKnowledgeChange}
            />
          </div>

          <div className="space-y-4">
            <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Tool Access</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {VALID_TOOLS.map((tool) => (
                <label
                  key={tool.id}
                  className="flex items-center gap-2 rounded-xl border border-[#E5E7EB] px-4 py-3 bg-[#F9FAFB] hover:bg-[#f0f6ff] cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={formData.tool_whitelist.includes(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                  />
                  <span className="text-sm font-medium text-[#111827]">{tool.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <AuthorizeRecruitButton
          formData={agentFormData}
          onRecruit={recruit}
          isLoading={isLoading}
          error={error}
          success={success}
        />
      </form>
      )}

      {/* Footer Security Badge */}
      <div className="bg-[#111827] rounded-[32px] p-8 text-white flex items-center gap-8 shadow-2xl relative overflow-hidden">
        <div className="w-16 h-16 bg-[#1d62e3] rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg">
          <ShieldCheck size={32} />
        </div>
        <div>
          <h4 className="text-lg font-bold mb-1">Safety Gate Integration Active</h4>
          <p className="text-[#6B7280] text-sm font-medium leading-relaxed max-w-xl">
            Nieuwe agents worden direct onderworpen aan de globale Compliance Officer (**Aegis**). Acties worden
            gemonitord volgens de Wonderz-veiligheidsprotocollen.
          </p>
        </div>
      </div>
    </PageLayout>
  );
};

export default HiringHall;
