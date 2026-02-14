#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'securerandom'
require_relative 'lib/orchestrator'

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

options = {
  json: false,
  max_retries: nil,
  max_depth: nil,
  max_runtime_seconds: nil,
  max_lesson_influence: nil,
  approval_mode: nil,
  min_accept_score: nil,
  run_id: "run-#{SecureRandom.hex(6)}"
}

parser = OptionParser.new do |opts|
  opts.banner = 'Usage: ruby crew/scripts/run_agent.rb --agent-id ID [--intent KEY] [--query TEXT] [--page-name NAME] [--keyword WORD] [--json]'
  opts.on('--agent-id ID') { |v| options[:agent_id] = v }
  opts.on('--intent KEY') { |v| options[:intent] = v }
  opts.on('--query TEXT') { |v| options[:query] = v }
  opts.on('--input TEXT') { |v| options[:input] = v }
  opts.on('--page-name NAME') { |v| options[:page_name] = v }
  opts.on('--baseline-file FILE') { |v| options[:baseline_file] = v }
  opts.on('--keyword WORD') { |v| options[:keyword] = v }
  opts.on('--service-hint HINT') { |v| options[:service_hint] = v }
  opts.on('--path-hint HINT') { |v| options[:path_hint] = v }
  opts.on('--max-retries N', Integer) { |v| options[:max_retries] = v }
  opts.on('--max-depth N', Integer) { |v| options[:max_depth] = v }
  opts.on('--max-runtime-seconds N', Integer) { |v| options[:max_runtime_seconds] = v }
  opts.on('--max-lesson-influence N', Integer) { |v| options[:max_lesson_influence] = v }
  opts.on('--approval-mode MODE', 'manual|auto') { |v| options[:approval_mode] = v }
  opts.on('--min-accept-score FLOAT', Float) { |v| options[:min_accept_score] = v }
  opts.on('--llm-enabled BOOL', 'true|false') { |v| options[:llm_enabled] = (v == 'true') }
  opts.on('--llm-model MODEL') { |v| options[:llm_model] = v }
  opts.on('--run-id ID') { |v| options[:run_id] = v }
  opts.on('--json') { options[:json] = true }
end

begin
  parser.parse!(ARGV)
rescue OptionParser::ParseError => e
  warn e.message
  warn parser.banner
  exit EXIT_USAGE
end

if options[:agent_id].to_s.strip.empty?
  warn 'Missing required option: --agent-id'
  warn parser.banner
  exit EXIT_USAGE
end

begin
  summary = Orchestrator.new(options).run
  if options[:json]
    puts JSON.pretty_generate(summary)
  else
    puts summary[:response]
  end
  exit(summary[:status] == 'success' ? EXIT_PASS : EXIT_FAIL)
rescue StandardError => e
  if options[:json]
    puts JSON.pretty_generate({ status: 'error', message: e.message })
  else
    warn "ERROR: #{e.message}"
  end
  exit EXIT_FAIL
end
