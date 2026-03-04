// Returns a mapping from stageId to array of agent names, based on progress messages
export function getAgentsPerStage(progress) {
  // progress: array of { stage, agents: [names], ... }
  const agentsPerStage = {};
  for (const msg of progress) {
    if (msg.stage && Array.isArray(msg.agents)) {
      agentsPerStage[msg.stage] = msg.agents;
    }
  }
  return agentsPerStage;
}
