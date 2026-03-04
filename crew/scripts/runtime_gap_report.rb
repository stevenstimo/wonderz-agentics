#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'time'

ROOT = File.expand_path('..', __dir__)
RUNS_DIR = File.join(ROOT, 'reports', 'runs')

options = {}
parser = OptionParser.new do |opts|
  opts.banner = 'Usage: ruby crew/scripts/runtime_gap_report.rb [--since-hours N]'
  opts.on('--since-hours N', Integer) { |v| options[:since_hours] = v }
end
parser.parse!(ARGV)

unless Dir.exist?(RUNS_DIR)
  puts JSON.pretty_generate({ status: 'ok', gaps: [], message: 'no runtime logs found' })
  exit 0
end

cutoff = options[:since_hours] ? (Time.now.utc - options[:since_hours] * 3600) : nil
by_intent = Hash.new { |h, k| h[k] = Hash.new(0) }
by_intent_unique = Hash.new { |h, k| h[k] = Hash.new(0) }

Dir.glob(File.join(RUNS_DIR, '*.jsonl')).sort.each do |path|
  current_intent = nil
  File.readlines(path, chomp: true).each do |line|
    next if line.strip.empty?
    row = JSON.parse(line) rescue nil
    next unless row.is_a?(Hash)

    row_ts = Time.iso8601(row['ts']) rescue nil
    next if cutoff && row_ts && row_ts < cutoff

    if row['type'] == 'run_started'
      current_intent = row['intent'].to_s
    elsif row['type'] == 'run_completed'
      summary = row['summary'] || {}
      current_intent = summary['intent'].to_s unless summary['intent'].to_s.empty?
      seen_types = {}
      Array(summary['failures']).each do |f|
        next unless f.is_a?(Hash)
        ftype = f['type'].to_s
        by_intent[current_intent][ftype] += 1
        seen_types[ftype] = true
      end
      seen_types.each_key { |ft| by_intent_unique[current_intent][ft] += 1 }
    end
  end
end

recommendation = {
  'missing_workspace_path' => 'Check and align project_structure_map and playbook path assumptions for this intent.',
  'tool_execution_failed' => 'Harden command templates and add conditional guards before execution.',
  'retry_exhausted' => 'Lower ambiguity and improve evaluator acceptance criteria or fallback strategy.',
  'intent_ambiguous' => 'Expand intent triggers and refine overlap phrases for clearer routing.',
  'governance_blocked' => 'Adjust governance allow/propose policy for expected runtime commands.',
  'contract_failed' => 'Tighten response builder and contract validator alignment.'
}

gaps = by_intent.map do |intent, counts|
  top_type, top_count = counts.max_by { |_k, v| v }
  {
    intent: intent,
    failure_counts: counts.sort.to_h,
    failure_counts_unique_runs: by_intent_unique[intent].sort.to_h,
    top_gap: top_type,
    top_gap_count: top_count,
    recommendation: recommendation[top_type] || 'Investigate recent failures and add targeted tests.'
  }
end.sort_by { |row| -(row[:top_gap_count] || 0) }

puts JSON.pretty_generate({ status: 'ok', since_hours: options[:since_hours], gaps: gaps })
