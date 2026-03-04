# frozen_string_literal: true

module ResponseBuilder
  module_function

  def parse_evidence_lines(step_results)
    lines = []
    Array(step_results).each do |res|
      next unless res[:ok] || res['ok']
      stdout = res[:stdout] || res['stdout']
      stdout.to_s.lines.each do |line|
        value = line.strip
        lines << value if value.match?(/^[^:]+:\d+:/)
      end
    end
    lines.uniq
  end

  def to_evidence_items(raw_lines)
    raw_lines.map do |raw|
      file, line, matched = raw.split(':', 3)
      next if file.to_s.empty? || line.to_s.empty? || matched.to_s.empty?
      next unless line.match?(/^\d+$/)

      {
        'file' => file,
        'line' => line.to_i,
        'matched_text' => matched.strip
      }
    end.compact
  end

  def derive(intent:, evidence_items:, lessons:)
    joined = evidence_items.map { |e| e['matched_text'] }.join(' ')

    if intent == 'layout_inconsistency'
      return [
        'Containerbreedte wijkt af van baseline (`max-w-3xl` vs `max-w-5xl`).',
        'Pas wrapper aan naar baselinebreedte (`max-w-5xl`) in de doelpagina.'
      ] if joined.include?('max-w-3xl') && joined.include?('max-w-5xl')

      return [
        'Layoutverschil komt waarschijnlijk door grid-breakpoint (`md:grid-cols-2`).',
        'Zet grid naar `md:grid-cols-1 lg:grid-cols-2` om middenscherm-weergave gelijk te trekken.'
      ] if joined.include?('md:grid-cols-2')
    else
      return [
        'Foutpad gevonden in backend flow (exception/error handling).',
        'Voeg guard/validatie toe rond het failure-point en normaliseer error-response.'
      ] if joined.downcase.match?(/raise|except|error/)

      return [
        'API/data pad toont status/rollback probleem.',
        'Controleer transactielogica en retourneer consistente status + foutboodschap.'
      ] if joined.downcase.match?(/status_code|rollback/)
    end

    if lessons.any?
      lesson_hint = Array(lessons.first['what_worked']).first
      return [
        'Analyse gaf voldoende signalen maar geen harde single-root indicator.',
        "Gebruik de best-scorende lesson als fixrichting: #{lesson_hint}."
      ]
    end

    [
      'Eerste analyse geeft nog geen volledige root-cause zekerheid.',
      'Vergelijk doelcomponent met baseline op wrapper/container tokens en pas de eerste afwijking aan.'
    ]
  end

  def build_markdown(evidence_items:, cause:, fix:, closing_question:)
    evidence_lines = evidence_items.first(3).map do |ev|
      "- `#{ev['file']}:#{ev['line']}` -> `#{ev['matched_text']}`"
    end
    evidence_lines = ['- `unknown:1` -> `no evidence captured`'] if evidence_lines.empty?

    <<~MD
      Gevonden:
      #{evidence_lines.join("\n")}

      Oorzaak:
      - #{cause}

      Fix voorstel:
      - #{fix}

      Vraag:
      - #{closing_question}
    MD
  end
end
