#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'securerandom'
require 'time'
require 'yaml'
require_relative 'lib/lesson_contract'

EXIT_PASS = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2

ROOT = File.expand_path('..', __dir__)
DEFAULT_SCHEMA_PATH = File.join(ROOT, 'schemas', 'lesson.schema.json')
LESSONS_DIR = File.join(ROOT, 'lessons')
AGENTS_DIR = File.join(ROOT, 'agents')

options = {
  what_worked: [],
  where_paths: [],
  where_files: [],
  evidence: [],
  confidence: nil,
  source: nil,
  context_type: nil,
  agent_id: nil,
  schema: DEFAULT_SCHEMA_PATH,
  limit_mode: 'append',
  dry_run: false
}

parser = OptionParser.new do |opts|
  opts.banner = 'Usage: ruby crew/scripts/append_lesson.rb --agent-id ID --context-type TYPE --what-worked TEXT [--what-worked TEXT] --where-path PATH [--evidence file:line:snippet] --source SOURCE --confidence 0.9 [--json]'
  opts.on('--agent-id ID') { |v| options[:agent_id] = v }
  opts.on('--context-type TYPE') { |v| options[:context_type] = v }
  opts.on('--what-worked TEXT') { |v| options[:what_worked] << v }
  opts.on('--where-path PATH') { |v| options[:where_paths] << v }
  opts.on('--where-file FILE') { |v| options[:where_files] << v }
  opts.on('--evidence ITEM', 'format: file:line:matched_text') { |v| options[:evidence] << v }
  opts.on('--source SOURCE') { |v| options[:source] = v }
  opts.on('--confidence FLOAT') { |v| options[:confidence] = v.to_f }
  opts.on('--task-signature TEXT') { |v| options[:task_signature] = v }
  opts.on('--supersedes ID') { |v| options[:supersedes] = v }
  opts.on('--ttl-days INT') { |v| options[:ttl_days] = v.to_i }
  opts.on('--update-id ID', 'Replace existing lesson with this id instead of append') do |v|
    options[:update_id] = v
    options[:limit_mode] = 'update'
  end
  opts.on('--schema PATH') { |v| options[:schema] = v }
  opts.on('--dry-run', 'Validate and build payload without writing to lessons file') { options[:dry_run] = true }
  opts.on('--json') { options[:json] = true }
end

begin
  parser.parse!(ARGV)
rescue OptionParser::ParseError => e
  warn e.message
  warn parser.banner
  exit EXIT_USAGE
end

required = %i[agent_id context_type source confidence]
missing = required.select { |k| options[k].nil? || options[k].to_s.strip.empty? }
missing << :what_worked if options[:what_worked].empty?
missing << :where_paths if options[:where_paths].empty?
if missing.any?
  warn "Missing required options: #{missing.join(', ')}"
  exit EXIT_USAGE
end

unless File.exist?(options[:schema])
  warn "Schema not found: #{options[:schema]}"
  exit EXIT_USAGE
end

profile_path = File.join(AGENTS_DIR, "#{options[:agent_id]}.profile.yml")
default_decay = 30
if File.exist?(profile_path)
  profile = YAML.load_file(profile_path)
  default_decay = profile.dig('learning', 'decay_days') || default_decay
end

ttl_days = options[:ttl_days] || default_decay

evidence = options[:evidence].map do |row|
  file, line, matched_text = row.split(':', 3)
  { 'file' => file.to_s, 'line' => line.to_i, 'matched_text' => matched_text.to_s }
end

lesson = {
  'id' => options[:update_id] || "lesson-#{SecureRandom.uuid}",
  'agent_id' => options[:agent_id],
  'created_at' => Time.now.utc.iso8601,
  'context_type' => options[:context_type],
  'what_worked' => options[:what_worked],
  'where_found' => {
    'paths' => options[:where_paths],
    'files' => options[:where_files]
  },
  'evidence' => evidence,
  'confidence' => options[:confidence],
  'source' => options[:source],
  'ttl_days' => ttl_days
}

lesson['task_signature'] = options[:task_signature] if options[:task_signature]
lesson['supersedes'] = options[:supersedes] if options[:supersedes]

errors = LessonContract.validate_record(options[:schema], lesson)
if errors.any?
  payload = { status: 'validation_failed', errors: errors }
  if options[:json]
    puts JSON.pretty_generate(payload)
  else
    puts 'FAIL: lesson validation failed'
    errors.each { |e| puts "- #{e}" }
  end
  exit EXIT_VALIDATION
end

lesson_file = File.join(LESSONS_DIR, "#{options[:agent_id]}.jsonl")

unless options[:dry_run]
  Dir.mkdir(LESSONS_DIR) unless Dir.exist?(LESSONS_DIR)

  if options[:limit_mode] == 'update'
    lines = File.exist?(lesson_file) ? File.readlines(lesson_file, chomp: true) : []
    replaced = false
    updated_lines = lines.map do |line|
      rec = JSON.parse(line)
      if rec['id'] == options[:update_id]
        replaced = true
        lesson.to_json
      else
        line
      end
    end
    updated_lines << lesson.to_json unless replaced
    File.write(lesson_file, updated_lines.join("\n") + "\n")
  else
    File.open(lesson_file, 'a') { |f| f.puts(lesson.to_json) }
  end
end

payload = {
  status: options[:dry_run] ? 'ok_dry_run' : 'ok',
  mode: options[:limit_mode],
  dry_run: options[:dry_run],
  lesson_file: lesson_file,
  lesson_id: lesson['id']
}

if options[:json]
  puts JSON.pretty_generate(payload)
else
  puts "PASS: lesson #{options[:limit_mode]} succeeded"
  puts "- lesson_file: #{lesson_file}"
  puts "- lesson_id: #{lesson['id']}"
end

exit EXIT_PASS
