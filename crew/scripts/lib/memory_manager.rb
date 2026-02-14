# frozen_string_literal: true

require 'json'
require 'time'

class MemoryManager
  def initialize(root:)
    @lessons_dir = File.join(root, 'lessons')
  end

  def select_lessons(agent_id:, context_type:, path_hint:, limit: 2)
    lesson_file = File.join(@lessons_dir, "#{agent_id}.jsonl")
    return [] unless File.exist?(lesson_file)

    now = Time.now.utc
    rows = []
    File.readlines(lesson_file, chomp: true).each do |line|
      next if line.strip.empty?
      rec = JSON.parse(line) rescue nil
      next unless rec.is_a?(Hash)
      next unless rec['context_type'] == context_type

      created_at = Time.iso8601(rec['created_at']) rescue nil
      next if created_at.nil?
      ttl_days = rec['ttl_days'] || 30
      next if now > (created_at + ttl_days * 86_400)

      score = rec['confidence'].to_f
      if !path_hint.to_s.empty?
        all_paths = Array(rec.dig('where_found', 'paths')) +
                    Array(rec.dig('where_found', 'files')) +
                    Array(rec['evidence']).map { |ev| ev['file'] }
        score += 0.2 if all_paths.any? { |p| p.to_s.include?(path_hint) }
      end
      rows << rec.merge('_score' => score)
    end

    rows.sort_by { |r| [-r['_score'], -Time.iso8601(r['created_at']).to_i] }
        .first(limit)
        .map { |r| r.reject { |k, _| k == '_score' } }
  end

  def apply_influence(lessons, max_lesson_influence)
    return [] if max_lesson_influence <= 0

    lessons.first(max_lesson_influence)
  end

  def append_lesson(agent_id:, context_type:, evidence:, what_worked:, source:, confidence:, ttl_days: 30)
    Dir.mkdir(@lessons_dir) unless Dir.exist?(@lessons_dir)
    lesson_file = File.join(@lessons_dir, "#{agent_id}.jsonl")
    lesson = {
      'id' => "lesson-runtime-#{Time.now.utc.to_i}",
      'agent_id' => agent_id,
      'created_at' => Time.now.utc.iso8601,
      'context_type' => context_type,
      'what_worked' => Array(what_worked),
      'where_found' => {
        'paths' => [],
        'files' => Array(evidence).map { |e| e['file'] }.uniq
      },
      'evidence' => Array(evidence),
      'confidence' => confidence,
      'source' => source,
      'ttl_days' => ttl_days
    }
    File.open(lesson_file, 'a') { |f| f.puts(lesson.to_json) }
    lesson
  end
end
