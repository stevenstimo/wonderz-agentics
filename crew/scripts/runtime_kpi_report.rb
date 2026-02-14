#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'time'

ROOT = File.expand_path('..', __dir__)
RUNS_DIR = File.join(ROOT, 'reports', 'runs')

options = {}
parser = OptionParser.new do |opts|
  opts.banner = 'Usage: ruby crew/scripts/runtime_kpi_report.rb [--since-hours N]'
  opts.on('--since-hours N', Integer) { |v| options[:since_hours] = v }
end
parser.parse!(ARGV)

unless Dir.exist?(RUNS_DIR)
  puts JSON.pretty_generate({ status: 'ok', runs: 0, message: 'no runtime logs found' })
  exit 0
end

cutoff = options[:since_hours] ? (Time.now.utc - options[:since_hours] * 3600) : nil
run_summaries = []
failure_counts = Hash.new(0)
failure_counts_unique_runs = Hash.new(0)
Dir.glob(File.join(RUNS_DIR, '*.jsonl')).sort.each do |path|
  summary = nil
  run_failure_types = {}
  File.readlines(path, chomp: true).each do |line|
    next if line.strip.empty?
    row = JSON.parse(line) rescue nil
    next unless row.is_a?(Hash)
    row_ts = Time.iso8601(row['ts']) rescue nil
    next if cutoff && row_ts && row_ts < cutoff
    summary = row['summary'] if row['type'] == 'run_completed'
    if row['type'] == 'failure' && row['failure'].is_a?(Hash)
      ftype = row['failure']['type'].to_s
      failure_counts[ftype] += 1
      run_failure_types[ftype] = true
    end
  end
  run_summaries << summary if summary
  run_failure_types.each_key { |ft| failure_counts_unique_runs[ft] += 1 }
end

if run_summaries.empty?
  puts JSON.pretty_generate({ status: 'ok', runs: 0, message: 'no completed runs found' })
  exit 0
end

success_count = run_summaries.count { |r| r['status'] == 'success' }
retry_total = run_summaries.sum { |r| r['retry_count'].to_i }
latency_total = run_summaries.sum { |r| r.dig('metrics', 'total_step_latency_ms').to_i }
tokens_total = run_summaries.sum { |r| r.dig('metrics', 'llm_usage', 'total_tokens').to_i }

payload = {
  status: 'ok',
  since_hours: options[:since_hours],
  runs: run_summaries.length,
  success_rate: (success_count.to_f / run_summaries.length).round(4),
  avg_retries: (retry_total.to_f / run_summaries.length).round(4),
  avg_step_latency_ms: (latency_total.to_f / run_summaries.length).round(2),
  total_llm_tokens: tokens_total,
  failure_counts: failure_counts.sort.to_h,
  failure_counts_unique_runs: failure_counts_unique_runs.sort.to_h
}

puts JSON.pretty_generate(payload)
