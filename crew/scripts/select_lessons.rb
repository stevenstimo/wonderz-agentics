#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'time'
require_relative 'lib/lesson_contract'

EXIT_PASS = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2

ROOT = File.expand_path('..', __dir__)
DEFAULT_SCHEMA_PATH = File.join(ROOT, 'schemas', 'lesson.schema.json')
LESSONS_DIR = File.join(ROOT, 'lessons')

options = {
  limit: 2,
  schema: DEFAULT_SCHEMA_PATH
}

parser = OptionParser.new do |opts|
  opts.banner = 'Usage: ruby crew/scripts/select_lessons.rb --agent-id ID --context-type TYPE [--path-hint PATH] [--limit 2] [--json]'
  opts.on('--agent-id ID') { |v| options[:agent_id] = v }
  opts.on('--context-type TYPE') { |v| options[:context_type] = v }
  opts.on('--path-hint HINT') { |v| options[:path_hint] = v }
  opts.on('--limit N', Integer) { |v| options[:limit] = v }
  opts.on('--schema PATH') { |v| options[:schema] = v }
  opts.on('--json') { options[:json] = true }
end

begin
  parser.parse!(ARGV)
rescue OptionParser::ParseError => e
  warn e.message
  warn parser.banner
  exit EXIT_USAGE
end

if options[:agent_id].to_s.empty? || options[:context_type].to_s.empty?
  warn 'Missing required options: --agent-id and --context-type'
  exit EXIT_USAGE
end

unless File.exist?(options[:schema])
  warn "Schema not found: #{options[:schema]}"
  exit EXIT_USAGE
end

lesson_file = File.join(LESSONS_DIR, "#{options[:agent_id]}.jsonl")
unless File.exist?(lesson_file)
  payload = { status: 'ok', selected: [], reason: 'no_lesson_file' }
  puts(options[:json] ? JSON.pretty_generate(payload) : 'PASS: no lessons found')
  exit EXIT_PASS
end

now = Time.now.utc
path_hint = options[:path_hint].to_s

records = []
File.readlines(lesson_file, chomp: true).each do |line|
  next if line.strip.empty?
  begin
    record = JSON.parse(line)
  rescue JSON::ParserError
    next
  end
  errs = LessonContract.validate_record(options[:schema], record)
  next unless errs.empty?
  next unless record['context_type'] == options[:context_type]

  created_at = Time.iso8601(record['created_at']) rescue nil
  next if created_at.nil?
  ttl_days = record['ttl_days'] || 30
  expires_at = created_at + (ttl_days * 86_400)
  next if now > expires_at

  score = record['confidence'].to_f
  if !path_hint.empty?
    all_paths = Array(record.dig('where_found', 'paths')) +
                Array(record.dig('where_found', 'files')) +
                Array(record['evidence']).map { |ev| ev['file'] }
    score += 0.2 if all_paths.any? { |p| p.to_s.include?(path_hint) }
  end

  records << record.merge('_score' => score)
end

selected = records
           .sort_by { |r| [-r['_score'], -Time.iso8601(r['created_at']).to_i] }
           .first(options[:limit])
           .map { |r| r.reject { |k, _| k == '_score' } }

payload = { status: 'ok', selected: selected, count: selected.length }

if options[:json]
  puts JSON.pretty_generate(payload)
else
  puts "PASS: selected #{selected.length} lesson(s)"
  selected.each do |lesson|
    puts "- #{lesson['id']} (confidence=#{lesson['confidence']}, context=#{lesson['context_type']})"
  end
end

exit EXIT_PASS
