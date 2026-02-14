#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'yaml'

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

ROOT = File.expand_path('..', __dir__)
AGENTS_DIR = File.join(ROOT, 'agents')
PLAYBOOKS_DIR = File.join(ROOT, 'playbooks')

REQUIRED_AGENT_KEYS = %w[
  version
  agent_id
  display_name
  role
  behavior
  intent_routing
  response_contract
  learning
  llm
  runtime
  governance
].freeze

REQUIRED_BEHAVIOR_KEYS = %w[
  tool_first
  no_manual_mode_if_scan_possible
  require_evidence
  minimum_evidence_items
  ask_before_apply_fix
].freeze

REQUIRED_RESPONSE_KEYS = %w[
  required_sections
  required_fields_per_evidence
  banned_patterns
  closing_question
].freeze

REQUIRED_LEARNING_KEYS = %w[
  enable_lessons_log
  lessons_file
  write_on
  decay_days
].freeze

REQUIRED_RUNTIME_KEYS = %w[
  max_retries
  max_depth
  max_runtime_seconds
  min_accept_score
  max_lesson_influence
].freeze

REQUIRED_LLM_KEYS = %w[
  enabled
  provider
  model
  endpoint
  api_key_env
  timeout_seconds
].freeze

REQUIRED_GOVERNANCE_KEYS = %w[
  allowed_prefixes
  propose_only_prefixes
].freeze

REQUIRED_PLAYBOOK_KEYS = %w[
  version
  id
  summary
  behavior
  intent_routing
  response_contract
  learning
].freeze

def gather_files(dir, glob)
  Dir.glob(File.join(dir, glob)).sort
end

def check_required(hash, required, label, errors)
  required.each do |key|
    errors << "#{label}: missing key '#{key}'" unless hash.key?(key)
  end
end

def validate_agent(file, errors)
  data = YAML.load_file(file)
  label = "agent #{File.basename(file)}"
  check_required(data, REQUIRED_AGENT_KEYS, label, errors)
  check_required(data.fetch('behavior', {}), REQUIRED_BEHAVIOR_KEYS, "#{label}.behavior", errors)
  check_required(data.fetch('response_contract', {}), REQUIRED_RESPONSE_KEYS, "#{label}.response_contract", errors)
  check_required(data.fetch('learning', {}), REQUIRED_LEARNING_KEYS, "#{label}.learning", errors)
  check_required(data.fetch('llm', {}), REQUIRED_LLM_KEYS, "#{label}.llm", errors)
  check_required(data.fetch('runtime', {}), REQUIRED_RUNTIME_KEYS, "#{label}.runtime", errors)
  check_required(data.fetch('governance', {}), REQUIRED_GOVERNANCE_KEYS, "#{label}.governance", errors)
end

def validate_playbook(file, errors)
  data = YAML.load_file(file)
  label = "playbook #{File.basename(file)}"
  check_required(data, REQUIRED_PLAYBOOK_KEYS, label, errors)
end

errors = []

agent_files = gather_files(AGENTS_DIR, '*.profile.yml')
if agent_files.empty?
  warn 'No agent profile files found'
  exit EXIT_USAGE
end

playbook_files = gather_files(PLAYBOOKS_DIR, '*.yml')
if playbook_files.empty?
  warn 'No playbook files found'
  exit EXIT_USAGE
end

agent_files.each { |f| validate_agent(f, errors) }
playbook_files.each { |f| validate_playbook(f, errors) }

if errors.empty?
  puts JSON.generate({ status: 'PASS', checked_agents: agent_files.length, checked_playbooks: playbook_files.length })
  exit EXIT_PASS
end

puts JSON.pretty_generate({
  status: 'FAIL',
  error_count: errors.length,
  errors: errors
})
exit EXIT_FAIL
