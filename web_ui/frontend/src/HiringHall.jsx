import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Briefcase, BrainCircuit, ShieldCheck, Info, UserPlus, GraduationCap } from 'lucide-react';
import PageLayout from './PageLayout';
import AuthorizeRecruitButton from './components/AuthorizeRecruitButton';
import { useHiringHall } from './hooks/useHiringHall';
import { apiUrl, apiFetch } from './apiClient';

const VALID_TOOLS = [
  { id: 'read_product', label: 'Read Product' },
  { id: 'write_copy', label: 'Write Copy' },
  { id: 'read_brief', label: 'Read Brief' },
  { id: 'knowledge_retrieval', label: 'Knowledge Retrieval' },
  { id: 'submit_artifact', label: 'Submit Artifact' },
  { id: 'read_analytics', label: 'Read Analytics' },
  { id: 'write_social', label: 'Write Social' },
  { id: 'read_tickets', label: 'Read Tickets' },
  { id: 'write_tickets', label: 'Write Tickets' },
  { id: 'read_jobs', label: 'Read Jobs' },
  { id: 'send_report', label: 'Send Report' },
  { id: 'web_search', label: 'Web Search' },
  { id: 'read_url', label: 'Read URL' },
  { id: 'read_lessons', label: 'Read Lessons' },
  { id: 'review_content', label: 'Review Content' },
  { id: 'optimize_seo', label: 'Optimize SEO' },
  { id: 'keyword_research', label: 'Keyword Research' },
  { id: 'provide_feedback', label: 'Provide Feedback' },
  { id: 'validate_output', label: 'Validate Output' },
  { id: 'check_evidence', label: 'Check Evidence' },
  { id: 'score_confidence', label: 'Score Confidence' },
  { id: 'approve_artifact', label: 'Approve Artifact' },
  { id: 'write_feedback', label: 'Write Feedback' },
  { id: 'create_development_point', label: 'Create Development Point' },
  { id: 'flag_escalation', label: 'Flag Escalation' },
  { id: 'read_logs', label: 'Read Logs' },
  { id: 'read_metrics', label: 'Read Metrics' },
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

const FRAMEWORK_ROLES = [
  { id: 'copywriter', label: 'Copywriter (Worker)' },
  { id: 'seo-specialist', label: 'SEO Specialist (Worker)' },
  { id: 'support-specialist', label: 'Support Specialist (Worker)' },
  { id: 'incident-response', label: 'Incident Response (Worker)' },
  { id: 'senior-engineer', label: 'Senior Engineer (Worker)' },
  { id: 'qa-reviewer', label: 'QA Reviewer (Talent)' },
  { id: 'logic-validator', label: 'Logic Validator (Talent)' },
  { id: 'orchestrator', label: 'Orchestrator (CEO)' },
];

const INITIAL_FORM_DATA = {
  agent_name: '',
  role: '',
  type: 'worker',
  goal: '',
  category: 'Custom',
  system_prompt: '',
  knowledge_sources: [],
  tool_whitelist: [],
  output_format: { type: 'markdown', schema: 'freeform' },
  guardrails: { scope_limitation: '', quality_thresholds: [], escalation_rule: '' },
  model_config: { model: 'claude-sonnet', temperature: 0.7, top_p: 0.9 },
};

const TAB_RECRUIT = 'recruit';
const TAB_PROMOTE = 'promote';

const HiringHall = ({ onHire }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const promoteId = searchParams.get('promote');
  const [activeTab, setActiveTab] = useState(promoteId ? TAB_PROMOTE : TAB_RECRUIT);
  const [formData, setFormData] = useState({ ...INITIAL_FORM_DATA });
  const { recruit, isLoading, error, success } = useHiringHall();
  const [roleTemplates, setRoleTemplates] = useState([]);

  const [readyNewbies, setReadyNewbies] = useState([]);
  const [loadingNewbies, setLoadingNewbies] = useState(false);
  const [hiringNewbieId, setHiringNewbieId] = useState(null);
  const [hireError, setHireError] = useState(null);

  useEffect(() => {
    apiFetch('/api/agents/role-templates')
      .then((r) => (r.ok ? r.json() : {}))
      .then((data) => setRoleTemplates(Array.isArray(data?.role_templates) ? data.role_templates : []))
      .catch(() => setRoleTemplates([]));
  }, []);

  const applyRoleTemplate = (roleKey) => {
    const template = roleTemplates.find((t) => t.role === roleKey);
    if (!template) return;
    setFormData((prev) => ({
      ...prev,
      role: template.role,
      type: template.type || 'worker',
      tool_whitelist: Array.isArray(template.tool_whitelist) ? [...template.tool_whitelist] : prev.tool_whitelist,
      output_format: template.output_format && typeof template.output_format === 'object' ? { ...template.output_format } : prev.output_format,
      guardrails: template.guardrails && typeof template.guardrails === 'object'
        ? {
            scope_limitation: template.guardrails.scope_limitation || '',
            quality_thresholds: Array.isArray(template.guardrails.quality_thresholds) ? [...template.guardrails.quality_thresholds] : [],
            escalation_rule: template.guardrails.escalation_rule || '',
          }
        : prev.guardrails,
      model_config: template.model_config && typeof template.model_config === 'object'
        ? { ...template.model_config }
        : prev.model_config,
    }));
  };

  useEffect(() => {
    if (promoteId) setActiveTab(TAB_PROMOTE);
  }, [promoteId]);

  useEffect(() => {
    if (activeTab === TAB_PROMOTE) {
      setLoadingNewbies(true);
      apiFetch('/api/newbies/ready')
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
      const res = await apiFetch(`/api/newbies/${newbie.newbie_id}/hire`, {
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
      setFormData({ ...INITIAL_FORM_DATA });
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
    name: formData.agent_name,
    agent_name: formData.agent_name,
    role: formData.role,
    type: formData.type,
    category: formData.category,
    goal: formData.goal,
    system_prompt: formData.system_prompt,
    tool_whitelist: formData.tool_whitelist,
    knowledge_sources: formData.knowledge_sources,
    output_format: formData.output_format,
    guardrails: formData.guardrails,
    model_config: formData.model_config,
  };

  return (
    <PageLayout variant="inner" size="medium" className="space-y-12 animate-in zoom-in-95 duration-500 pb-24">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-black text-[var(--color-text-primary)] tracking-tight">Recruit New Crew Member</h1>
        <p className="text-[var(--color-text-muted)] text-lg max-w-2xl mx-auto">
          Configureer het &quot;Brein&quot; van je agent. Definieer hun persona, kennisbasis en operationele tools.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[var(--color-border)]">
        <button
          type="button"
          onClick={() => setActiveTab(TAB_RECRUIT)}
          className={`px-6 py-3 font-semibold rounded-t-xl transition-colors ${
            activeTab === TAB_RECRUIT ? 'bg-white border border-[var(--color-border)] border-b-0 text-[#1d62e3]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
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
            activeTab === TAB_PROMOTE ? 'bg-white border border-[var(--color-border)] border-b-0 text-[#1d62e3]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          <span className="flex items-center gap-2">
            <GraduationCap size={18} />
            Promote Newbie
            {readyNewbies.length > 0 && (
              <span className="wz-badge-success ml-1">
                {readyNewbies.length}
              </span>
            )}
          </span>
        </button>
      </div>

      {activeTab === TAB_PROMOTE && (
        <div className="wz-card rounded-[32px] p-10">
          <h2 className="text-xl font-bold text-[var(--color-text-primary)] mb-4">Ready Newbies</h2>
          <p className="text-[var(--color-text-muted)] text-sm mb-6">
            Newbies met readiness ≥ 70. Klik op Hire om ze direct naar de crew te promoveren.
          </p>
          {hireError && (
            <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{hireError}</div>
          )}
          {loadingNewbies ? (
            <p className="text-[var(--color-text-muted)] text-sm">Laden...</p>
          ) : readyNewbies.length === 0 ? (
            <p className="text-[var(--color-text-muted)] text-sm">Geen ready newbies. Train newbies op de Newbies-pagina tot readiness ≥ 70.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {readyNewbies.map((n) => (
                <div
                  key={n.newbie_id}
                  className={`rounded-xl border p-5 transition ${
                    promoteId === n.newbie_id ? 'border-[#1d62e3] bg-[#f0f6ff]' : 'border-[var(--color-border)] bg-[var(--color-bg-subtle)] hover:border-[#1d62e3]/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-[var(--color-text-primary)]">{n.newbie_name || '—'}</h3>
                      {n.suggested_role && <span className="text-sm text-[var(--color-text-muted)]">{n.suggested_role}</span>}
                      <p className="text-xs text-[var(--color-text-muted)] mt-1 line-clamp-2">{n.persona || ''}</p>
                      <span className="text-xs font-medium text-green-600 mt-2 block">Readiness: {n.readiness_score ?? 0}%</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleHireNewbie(n)}
                      disabled={hiringNewbieId === n.newbie_id}
                      className="wz-btn-primary flex items-center gap-2 disabled:opacity-50"
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
        <div className="wz-card rounded-[32px] p-10 space-y-8">
          <div className="flex items-center gap-3 border-b border-[var(--color-bg-subtle)] pb-6">
            <div className="w-10 h-10 bg-[var(--color-brand-primary-light)] text-[var(--color-brand-primary)] rounded-xl flex items-center justify-center">
              <Briefcase size={20} />
            </div>
            <h2 className="text-xl font-bold text-[var(--color-text-primary)]">Core Identity</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Name</label>
              <input
                required
                placeholder="e.g. Donna Paulsen"
                className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[var(--color-brand-primary)]/10 focus:bg-white outline-none transition-all font-bold"
                value={formData.agent_name}
                onChange={(e) => setFormData({ ...formData, agent_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Role (framework)</label>
              <select
                required
                className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[var(--color-brand-primary)]/10 focus:bg-white outline-none transition-all font-bold"
                value={formData.role}
                onChange={(e) => {
                  const roleKey = e.target.value;
                  setFormData((prev) => ({ ...prev, role: roleKey }));
                  applyRoleTemplate(roleKey);
                }}
              >
                <option value="">Select a role</option>
                {FRAMEWORK_ROLES.map((r) => (
                  <option key={r.id} value={r.id}>{r.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Type</label>
              <div className="flex gap-4 pt-2">
                {['worker', 'talent', 'orchestrator'].map((t) => (
                  <label key={t} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="agentType"
                      checked={formData.type === t}
                      onChange={() => setFormData((prev) => ({ ...prev, type: t }))}
                      className="rounded-full"
                    />
                    <span className="font-medium capitalize">{t}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Goal</label>
              <input
                required
                placeholder="e.g. Elke dag proactief rapporteren over afgesloten jobs..."
                className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[var(--color-brand-primary)]/10 focus:bg-white outline-none transition-all font-bold"
                value={formData.goal}
                onChange={(e) => setFormData({ ...formData, goal: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Category</label>
              <select
                className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[var(--color-brand-primary)]/10 focus:bg-white outline-none transition-all font-bold"
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
        <div className="wz-card rounded-[32px] p-10 space-y-8">
          <div className="flex items-center gap-3 border-b border-[var(--color-bg-subtle)] pb-6">
            <div className="w-10 h-10 bg-[var(--color-bg-subtle)] text-[var(--color-technical)] rounded-xl flex items-center justify-center">
              <BrainCircuit size={20} />
            </div>
            <h2 className="text-xl font-bold text-[var(--color-text-primary)]">Agent Persona & Brain</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">
                System Instructions
              </label>
              <div className="flex items-center gap-1.5 text-[var(--color-text-muted)]">
                <Info size={12} />
                <span className="text-[10px] font-bold">Dit definieert het gedrag en de toon van de agent.</span>
              </div>
            </div>
            <textarea
              required
              placeholder="Je bent een empathische support agent..."
              className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-6 py-6 rounded-[24px] focus:ring-4 focus:ring-[var(--color-brand-primary)]/10 focus:bg-white outline-none transition-all min-h-[160px] font-medium text-[var(--color-text-primary)] leading-relaxed"
              value={formData.system_prompt}
              onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
            />
          </div>

          <div className="space-y-4">
            <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">
              Knowledge Sources (URLs, één per regel)
            </label>
            <textarea
              placeholder="https://docs.example.com/..."
              className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-6 py-4 rounded-xl focus:ring-4 focus:ring-[var(--color-brand-primary)]/10 focus:bg-white outline-none transition-all min-h-[80px] font-medium"
              value={knowledgeText}
              onChange={handleKnowledgeChange}
            />
          </div>

          <div className="space-y-4">
            <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Tool Access (min. 1)</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {VALID_TOOLS.map((tool) => (
                <label
                  key={tool.id}
                  className="flex items-center gap-2 rounded-xl border border-[var(--color-border)] px-4 py-3 bg-[var(--color-bg-subtle)] hover:bg-[var(--color-brand-primary-light)] cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={formData.tool_whitelist.includes(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                  />
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">{tool.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Output format</label>
            <select
              className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl font-bold"
              value={formData.output_format?.type || 'markdown'}
              onChange={(e) => setFormData((prev) => ({
                ...prev,
                output_format: { ...prev.output_format, type: e.target.value, schema: prev.output_format?.schema || 'freeform' },
              }))}
            >
              <option value="markdown">markdown</option>
              <option value="json">json</option>
              <option value="code">code</option>
            </select>
          </div>

          <div className="space-y-4">
            <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Guardrails — scope_limitation</label>
            <textarea
              required
              placeholder="Wat mag deze agent absoluut niet?"
              className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl min-h-[80px] font-medium"
              value={formData.guardrails?.scope_limitation || ''}
              onChange={(e) => setFormData((prev) => ({
                ...prev,
                guardrails: { ...prev.guardrails, scope_limitation: e.target.value },
              }))}
            />
            <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Guardrails — escalation_rule</label>
            <textarea
              required
              placeholder="Wanneer escaleer naar CEO?"
              className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl min-h-[80px] font-medium"
              value={formData.guardrails?.escalation_rule || ''}
              onChange={(e) => setFormData((prev) => ({
                ...prev,
                guardrails: { ...prev.guardrails, escalation_rule: e.target.value },
              }))}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Model</label>
              <select
                className="w-full bg-[var(--color-bg-subtle)] border border-[var(--color-border)] px-5 py-4 rounded-xl font-bold"
                value={formData.model_config?.model || 'claude-sonnet'}
                onChange={(e) => setFormData((prev) => ({
                  ...prev,
                  model_config: { ...prev.model_config, model: e.target.value },
                }))}
              >
                <option value="claude-sonnet">claude-sonnet</option>
                <option value="claude-haiku">claude-haiku</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-[var(--color-text-muted)] uppercase tracking-widest px-1">Temperature (0.1 – 0.9)</label>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.1"
                className="w-full"
                value={formData.model_config?.temperature ?? 0.7}
                onChange={(e) => setFormData((prev) => ({
                  ...prev,
                  model_config: { ...prev.model_config, temperature: parseFloat(e.target.value) },
                }))}
              />
              <span className="text-sm font-medium">{formData.model_config?.temperature ?? 0.7}</span>
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
      <div className="bg-[var(--color-text-primary)] rounded-[32px] p-8 text-white flex items-center gap-8 shadow-2xl relative overflow-hidden">
        <div className="w-16 h-16 bg-[var(--color-brand-primary)] rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg">
          <ShieldCheck size={32} />
        </div>
        <div>
          <h4 className="text-lg font-bold mb-1">Safety Gate Integration Active</h4>
          <p className="text-[var(--color-text-muted)] text-sm font-medium leading-relaxed max-w-xl">
            Nieuwe agents worden direct onderworpen aan de globale Compliance Officer (**Aegis**). Acties worden
            gemonitord volgens de Wonderz-veiligheidsprotocollen.
          </p>
        </div>
      </div>
    </PageLayout>
  );
};

export default HiringHall;
