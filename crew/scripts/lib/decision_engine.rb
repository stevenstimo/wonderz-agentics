# frozen_string_literal: true

require_relative 'runtime_types'

class DecisionEngine
  INTENT_HINTS = {
    'layout_inconsistency' => /layout|smaller|breder|smaller|className|max-w|grid|pagina/i,
    'api_or_data_issue' => /api|endpoint|data|db|query|error|backend|status/i,
    'architecture_or_explanation' => /architectuur|explain|uitleg|design|flow/i
  }.freeze

  def initialize(profile:, playbooks:)
    @profile = profile
    @playbooks = playbooks
  end

  def classify_intent(requested_intent:, query:)
    unless requested_intent.to_s.strip.empty?
      return {
        intent: requested_intent,
        confidence: 0.99,
        reason: 'intent explicitly provided',
        margin: 1.0,
        ambiguous: false,
        candidates: [{ intent: requested_intent, score: 0.99, detail: 'explicit' }]
      }
    end

    text = query.to_s
    routing = @profile.fetch('intent_routing', {})
    if text.strip.empty?
      fallback = routing.keys.first
      return {
        intent: fallback,
        confidence: 0.4,
        reason: 'fallback to first routed intent',
        margin: 0.0,
        ambiguous: true,
        candidates: [{ intent: fallback, score: 0.4, detail: 'empty query fallback' }]
      }
    end

    best_intent = nil
    best_score = -1.0
    best_detail = nil
    second_best = -1.0
    candidates = []

    routing.each do |intent, intent_cfg|
      playbook_id = intent_cfg['playbook']
      playbook = @playbooks[playbook_id] || {}
      trigger_phrases = Array(playbook.dig('triggers', 'any_of'))
      trigger_score, trigger_detail = score_by_triggers(text, trigger_phrases)
      hint_score = score_by_hints(intent, text)
      final_score = [[trigger_score, hint_score].max, 0.99].min
      candidates << { intent: intent, score: final_score.round(3), detail: trigger_detail }

      if final_score > best_score
        second_best = best_score
        best_score = final_score
        best_intent = intent
        best_detail = "playbook=#{playbook_id}; #{trigger_detail}; hint_score=#{format('%.3f', hint_score)}"
      elsif final_score > second_best
        second_best = final_score
      end
    end

    # Confidence softening when top-2 intents are close.
    margin = best_score - [second_best, 0.0].max
    calibrated = [best_score - (margin < 0.08 ? 0.08 : 0.0), 0.35].max
    ambiguous = calibrated < 0.5 || margin < 0.06

    {
      intent: best_intent,
      confidence: calibrated.round(3),
      reason: "classified via trigger matching; #{best_detail}; margin=#{format('%.3f', margin)}",
      margin: margin.round(3),
      ambiguous: ambiguous,
      candidates: candidates.sort_by { |c| -c[:score] }
    }
  end

  def route(intent, confidence: 0.9, reason: nil)
    intent_cfg = @profile.fetch('intent_routing', {})[intent]
    raise "Unknown intent '#{intent}' for #{@profile['agent_id']}" unless intent_cfg

    playbook_id = intent_cfg['playbook']
    raise "Playbook '#{playbook_id}' not loaded" unless @playbooks.key?(playbook_id)

    RuntimeTypes.decision_record(
      intent: intent,
      confidence: confidence,
      playbook_id: playbook_id,
      reason: reason || "intent_routing.#{intent}.playbook"
    )
  end

  def decide_next(evaluation:, retry_count:, max_retries:)
    return 'accept' if evaluation[:verdict] == 'accept'
    return 'retry' if retry_count < max_retries

    'escalate'
  end

  private

  def score_by_hints(intent, text)
    regex = INTENT_HINTS[intent]
    return 0.3 unless regex

    text.match?(regex) ? 0.78 : 0.25
  end

  def score_by_triggers(query, phrases)
    return [0.2, 'no triggers configured'] if phrases.empty?

    qn = normalize(query)
    q_tokens = tokenize(qn)
    best = 0.0
    best_phrase = nil

    phrases.each do |phrase|
      pn = normalize(phrase)
      score = if qn.include?(pn)
                0.95
              else
                token_overlap_score(q_tokens, tokenize(pn))
              end
      if score > best
        best = score
        best_phrase = phrase
      end
    end

    [best, "best_trigger='#{best_phrase}' score=#{format('%.3f', best)}"]
  end

  def normalize(text)
    text.to_s.downcase.gsub(/[^a-z0-9\s]/i, ' ').gsub(/\s+/, ' ').strip
  end

  def tokenize(text)
    text.split(' ').reject { |t| t.length < 2 }
  end

  def token_overlap_score(a_tokens, b_tokens)
    return 0.0 if a_tokens.empty? || b_tokens.empty?

    a = a_tokens.uniq
    b = b_tokens.uniq
    common = (a & b).length.to_f
    union = (a | b).length.to_f
    jaccard = common / union
    [0.2, 0.2 + (0.75 * jaccard)].max
  end
end
