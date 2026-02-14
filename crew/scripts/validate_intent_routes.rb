#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'yaml'

ROOT = File.expand_path('..', __dir__)
AGENTS_DIR = File.join(ROOT, 'agents')
PLAYBOOKS_DIR = File.join(ROOT, 'playbooks')

playbooks = {}
Dir.glob(File.join(PLAYBOOKS_DIR, '*.yml')).sort.each do |path|
  data = YAML.load_file(path)
  playbooks[data['id']] = {
    file: path,
    contract: data['response_contract'] || {}
  }
end

errors = []
checked = 0

Dir.glob(File.join(AGENTS_DIR, '*.profile.yml')).sort.each do |profile_path|
  profile = YAML.load_file(profile_path)
  profile_id = profile['agent_id']
  profile_contract = profile['response_contract'] || {}
  routing = profile['intent_routing'] || {}

  if routing.empty?
    errors << "#{profile_id}: intent_routing is empty"
    next
  end

  routing.each do |intent_key, intent_cfg|
    checked += 1
    playbook_id = intent_cfg['playbook']
    if playbook_id.to_s.strip.empty?
      errors << "#{profile_id}.intent_routing.#{intent_key}: missing playbook id"
      next
    end

    unless playbooks.key?(playbook_id)
      errors << "#{profile_id}.intent_routing.#{intent_key}: unknown playbook '#{playbook_id}'"
      next
    end

    pb_contract = playbooks[playbook_id][:contract]
    required_sections_profile = Array(profile_contract['required_sections'])
    required_sections_playbook = Array(pb_contract['required_sections'])

    missing_in_playbook = required_sections_profile - required_sections_playbook
    unless missing_in_playbook.empty?
      errors << "#{profile_id}.intent_routing.#{intent_key}: playbook '#{playbook_id}' missing sections #{missing_in_playbook.join(', ')}"
    end
  end
end

if errors.empty?
  puts JSON.generate({ status: 'PASS', checked_routes: checked, playbooks: playbooks.keys.sort })
  exit 0
end

puts JSON.pretty_generate({
  status: 'FAIL',
  checked_routes: checked,
  error_count: errors.length,
  errors: errors
})
exit 1
