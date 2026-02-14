import React, { useEffect, useState } from 'react';
import { ChevronUp } from 'lucide-react';
import PageLayout from './PageLayout';

export default function TalentOverview() {
  const [talents, setTalents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTalent, setSelectedTalent] = useState(null);
  const [promoting, setPromoting] = useState(false);
  const [promoteForm, setPromoteForm] = useState({
    role: 'Developer',
    system_instructions: '',
    hiring_logic: '',
    specialization: ''
  });
  
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchTalents();
  }, [apiBase]);

  const fetchTalents = () => {
    fetch(`${apiBase}/api/talents`)
      .then(res => res.json())
      .then(data => {
        setTalents(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  const handlePromote = async (talent) => {
    setSelectedTalent(talent);
    setPromoteForm({
      role: 'Developer',
      system_instructions: talent.quality || '',
      hiring_logic: talent.growth || '',
      specialization: talent.persona || ''
    });
  };

  const submitPromotion = async () => {
    if (!selectedTalent) return;
    if (!promoteForm.system_instructions.trim() || !promoteForm.hiring_logic.trim()) {
      alert('Please fill in system instructions and hiring logic');
      return;
    }

    setPromoting(true);
    try {
      const res = await fetch(`${apiBase}/api/talents/${selectedTalent.id}/promote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(promoteForm)
      });

      if (res.ok) {
        setSelectedTalent(null);
        fetchTalents();
        alert(`${selectedTalent.name} promoted to ${promoteForm.role}!`);
      } else {
        alert('Promotion failed');
      }
    } catch (err) {
      alert('Error promoting talent');
    } finally {
      setPromoting(false);
    }
  };

  if (loading) return <div className="p-8">Loading talents...</div>;

  return (
    <PageLayout size="wide" padded>
      <h1 className="text-2xl font-bold mb-6">Talents</h1>
      {talents.length === 0 ? (
        <div className="text-center text-gray-500 py-12">No talents yet. Create one via the API!</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {talents.map(talent => (
            <div key={talent.id} className="bg-white rounded-lg shadow p-4 flex flex-col">
              <img
                src={talent.avatar_url || 'https://api.dicebear.com/7.x/personas/svg?seed=' + encodeURIComponent(talent.name)}
                alt={talent.name}
                className="w-20 h-20 rounded-full mb-3 mx-auto object-cover border"
              />
              <div className="flex-1">
                <div className="font-semibold text-lg text-center">{talent.name}</div>
                <div className="text-gray-600 text-xs text-center mb-2">{talent.persona}</div>
                <div className="text-gray-700 text-xs mb-3">
                  <div className="font-semibold mb-1">Quality:</div>
                  <div className="line-clamp-2">{talent.quality}</div>
                </div>
                {talent.skills && talent.skills.length > 0 && (
                  <div className="flex flex-wrap gap-1 justify-center mb-3">
                    {talent.skills.map((skill, i) => (
                      <span key={i} className="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded text-xs">
                        {skill.name} ({skill.level || '?'})
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={() => handlePromote(talent)}
                className="btn-manage w-full gap-2 mt-auto"
              >
                <ChevronUp className="w-4 h-4" />
                Promote to Crew
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Promotion Modal */}
      {selectedTalent && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Promote {selectedTalent.name}</h2>
              <button
                onClick={() => setSelectedTalent(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-1">Role</label>
                <select
                  value={promoteForm.role}
                  onChange={(e) => setPromoteForm({ ...promoteForm, role: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option>Developer</option>
                  <option>Product Owner</option>
                  <option>Reviewer</option>
                  <option>DevOps</option>
                  <option>AI</option>
                  <option>HR</option>
                  <option>Training</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold mb-1">Specialization</label>
                <input
                  type="text"
                  value={promoteForm.specialization}
                  onChange={(e) => setPromoteForm({ ...promoteForm, specialization: e.target.value })}
                  placeholder={selectedTalent.persona}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold mb-1">System Instructions</label>
                <textarea
                  value={promoteForm.system_instructions}
                  onChange={(e) => setPromoteForm({ ...promoteForm, system_instructions: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg h-24"
                  placeholder="How should this crew member behave and operate?"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold mb-1">Hiring Logic</label>
                <textarea
                  value={promoteForm.hiring_logic}
                  onChange={(e) => setPromoteForm({ ...promoteForm, hiring_logic: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg h-24"
                  placeholder="When and how should this crew member be assigned to tasks?"
                />
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setSelectedTalent(null)}
                  className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
                  disabled={promoting}
                >
                  Cancel
                </button>
                <button
                  onClick={submitPromotion}
                  disabled={promoting}
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  {promoting ? 'Promoting...' : 'Promote Now'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </PageLayout>
  );
}
