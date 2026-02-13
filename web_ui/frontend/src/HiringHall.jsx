import React, { useState } from 'react';
import { Briefcase, Sparkles, BrainCircuit, ShieldCheck, Info } from 'lucide-react';
import Sidebar from './Sidebar';
/**
 * @typedef {'Management' | 'Creative' | 'Technical'} AgentCategory
 * @typedef {{
 *   id: string,
 *   name: string,
 *   category: AgentCategory,
 *   description?: string,
 *   avatarUrl?: string,
 *   specialization: string,
 *   status: string,
 *   metrics: { performanceScore: number, tasksCompleted: number, tokensConsumed: number, successRate: number }
 * }} Agent
 */
const HiringHall = ({ onHire }) => {
  const [formData, setFormData] = useState({
    name: '',
    role: '',
    goal: '',
    category: 'Creative',
    category: 'Creative',
    systemInstruction: '',
    knowledgeSources: '',
    tools: []
  });

  const availableTools = [
    { id: 'shopify', label: 'Shopify Admin API', icon: '🛍️' },
    { id: 'search', label: 'Google Search Grounding', icon: '🔍' },
    { id: 'analytics', label: 'GA4 Realtime Data', icon: '📈' }
  ];

  const toggleTool = (id) => {
    setFormData(prev => ({
      ...prev,
      tools: prev.tools.includes(id)
        ? prev.tools.filter(t => t !== id)
        : [...prev.tools, id]
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onHire({
      id: Math.random().toString(36).substr(2, 9),
      name: formData.name,
      role: formData.role,
      goal: formData.goal,
      category: formData.category,
      specialization: formData.specialization,
      status: 'Idle',
      metrics: { performanceScore: 0, tasksCompleted: 0, tokensConsumed: 0, successRate: 0 }
    });
  };

  return (
    <div className="dashboard-container">
      <Sidebar />
      <main className="content-area">
        <div className="main-content">
          <div className="inner-container">
            <div className="max-w-5xl mx-auto space-y-12 animate-in zoom-in-95 duration-500 pb-24">
              <div className="text-center space-y-4">
                <h1 className="text-4xl font-black text-[#111827] tracking-tight">Recruit New Crew Member</h1>
                <p className="text-[#6B7280] text-lg max-w-2xl mx-auto">Configureer het "Brein" van je agent. Definieer hun persona, kennisbasis en operationele tools.</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-10">
                {/* Section 1: Core Identity - Blauw Accent */}
                <div className="bg-white rounded-[32px] border border-[#E5E7EB] p-10 shadow-sleak space-y-8">
                  <div className="flex items-center gap-3 border-b border-[#F9FAFB] pb-6">
                     <div className="w-10 h-10 bg-[#f0f6ff] text-[#1d62e3] rounded-xl flex items-center justify-center">
                        <Briefcase size={20} />
                     </div>
                     <h2 className="text-xl font-bold text-[#111827]">Core Identity</h2>
                  </div>
          
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Name</label>
                      <input required placeholder="e.g. Zoe" className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all font-bold" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Role</label>
                      <input required placeholder="e.g. Support Specialist" className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all font-bold" value={formData.role} onChange={e => setFormData({...formData, role: e.target.value})} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">Category</label>
                      <select className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-5 py-4 rounded-xl focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all font-bold" value={formData.category} onChange={e => setFormData({...formData, category: e.target.value})}>
                        <option value="Management">Management</option>
                        <option value="Creative">Creative</option>
                        <option value="Technical">Technical</option>
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
                       <label className="text-[10px] font-black text-[#6B7280] uppercase tracking-widest px-1">System Instructions</label>
                       <div className="flex items-center gap-1.5 text-[#6B7280]">
                          <Info size={12} />
                          <span className="text-[10px] font-bold">Dit definieert het gedrag en de toon van de agent.</span>
                       </div>
                    </div>
                    <textarea 
                      required
                      placeholder="Je bent een empathische support agent..."
                      className="w-full bg-[#F9FAFB] border border-[#E5E7EB] px-6 py-6 rounded-[24px] focus:ring-4 focus:ring-[#1d62e3]/10 focus:bg-white outline-none transition-all min-h-[160px] font-medium text-[#111827] leading-relaxed"
                      value={formData.systemInstruction}
                      onChange={e => setFormData({...formData, systemInstruction: e.target.value})}
                    />
                  </div>
                </div>

                {/* Submit Button - Wonderz Blue */}
                <div className="flex gap-4">
                  <button 
                    type="submit"
                    className="flex-1 bg-[#1d62e3] hover:bg-[#154dbb] text-white font-black py-6 rounded-[32px] shadow-2xl shadow-[#1d62e3]/20 transition-all flex items-center justify-center gap-4 text-xl active:scale-[0.98]"
                  >
                    Authorize & Recruit Crew Member
                    <Sparkles size={24} className="text-[#e0edff]" />
                  </button>
                </div>
              </form>

              {/* Footer Security Badge */}
              <div className="bg-[#111827] rounded-[32px] p-8 text-white flex items-center gap-8 shadow-2xl relative overflow-hidden">
                 <div className="w-16 h-16 bg-[#1d62e3] rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg">
                    <ShieldCheck size={32} />
                 </div>
                 <div>
                    <h4 className="text-lg font-bold mb-1">Safety Gate Integration Active</h4>
                    <p className="text-[#6B7280] text-sm font-medium leading-relaxed max-w-xl">
                      Nieuwe agents worden direct onderworpen aan de globale Compliance Officer (**Aegis**). Acties worden gemonitord volgens de Wonderz-veiligheidsprotocollen.
                    </p>
                 </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default HiringHall;
