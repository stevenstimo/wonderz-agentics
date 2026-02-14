# frozen_string_literal: true

require 'json'
require 'net/http'
require 'uri'

class LlmClient
  def initialize(config:)
    @config = config || {}
  end

  def enabled?
    @config.fetch('enabled', false) == true
  end

  def generate_diagnosis(intent:, query:, evidence_items:, lessons:, fallback_cause:, fallback_fix:)
    return disabled_result unless enabled?

    api_key = ENV[@config.fetch('api_key_env', 'OPENAI_API_KEY')]
    return disabled_result('missing_api_key') if api_key.to_s.strip.empty?

    endpoint = @config.fetch('endpoint', 'https://api.openai.com/v1/chat/completions')
    model = @config.fetch('model', 'gpt-4o-mini')
    timeout_seconds = (@config.fetch('timeout_seconds', 20) || 20).to_i

    prompt = build_prompt(
      intent: intent,
      query: query,
      evidence_items: evidence_items,
      lessons: lessons,
      fallback_cause: fallback_cause,
      fallback_fix: fallback_fix
    )

    started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    response = post_chat_completion(endpoint, api_key, model, prompt, timeout_seconds)
    latency_ms = ((Process.clock_gettime(Process::CLOCK_MONOTONIC) - started) * 1000).round

    content = dig_content(response)
    parsed = JSON.parse(content)
    cause = parsed['cause'].to_s.strip
    fix = parsed['fix'].to_s.strip

    return disabled_result('invalid_llm_payload') if cause.empty? || fix.empty?

    {
      used: true,
      provider: @config.fetch('provider', 'openai_compatible'),
      model: model,
      cause: cause,
      fix: fix,
      confidence: parsed['confidence'].to_f,
      usage: normalize_usage(response['usage'], prompt, content),
      latency_ms: latency_ms
    }
  rescue StandardError => e
    disabled_result("llm_error: #{e.message}")
  end

  private

  def disabled_result(reason = 'disabled')
    {
      used: false,
      reason: reason,
      cause: nil,
      fix: nil,
      confidence: 0.0,
      usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      latency_ms: 0
    }
  end

  def post_chat_completion(endpoint, api_key, model, prompt, timeout_seconds)
    uri = URI.parse(endpoint)
    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = (uri.scheme == 'https')
    http.open_timeout = timeout_seconds
    http.read_timeout = timeout_seconds

    req = Net::HTTP::Post.new(uri.request_uri)
    req['Authorization'] = "Bearer #{api_key}"
    req['Content-Type'] = 'application/json'
    req.body = JSON.generate(
      {
        model: model,
        temperature: 0.1,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: 'Return strict JSON with keys: cause, fix, confidence (0..1).' },
          { role: 'user', content: prompt }
        ]
      }
    )

    res = http.request(req)
    raise "llm_http_#{res.code}" unless res.code.to_i.between?(200, 299)

    JSON.parse(res.body)
  end

  def build_prompt(intent:, query:, evidence_items:, lessons:, fallback_cause:, fallback_fix:)
    evidence_lines = Array(evidence_items).first(3).map do |ev|
      "- #{ev['file']}:#{ev['line']} -> #{ev['matched_text']}"
    end
    lesson_lines = Array(lessons).first(2).flat_map { |l| Array(l['what_worked']) }.map { |x| "- #{x}" }

    <<~TXT
      Intent: #{intent}
      User query: #{query}
      Evidence:
      #{evidence_lines.join("\n")}

      Relevant lessons:
      #{lesson_lines.join("\n")}

      Fallback cause: #{fallback_cause}
      Fallback fix: #{fallback_fix}

      Return strict JSON:
      {"cause":"...","fix":"...","confidence":0.0}
    TXT
  end

  def dig_content(response)
    choices = Array(response['choices'])
    msg = choices.first && choices.first['message']
    content = msg && msg['content']
    raise 'llm_missing_content' if content.to_s.strip.empty?

    content
  end

  def normalize_usage(usage, prompt, completion_text)
    if usage.is_a?(Hash)
      prompt_tokens = usage['prompt_tokens'].to_i
      completion_tokens = usage['completion_tokens'].to_i
      total_tokens = usage['total_tokens'].to_i
      total_tokens = prompt_tokens + completion_tokens if total_tokens <= 0
      return {
        prompt_tokens: prompt_tokens,
        completion_tokens: completion_tokens,
        total_tokens: total_tokens
      }
    end

    prompt_tokens = (prompt.to_s.length / 4.0).ceil
    completion_tokens = (completion_text.to_s.length / 4.0).ceil
    {
      prompt_tokens: prompt_tokens,
      completion_tokens: completion_tokens,
      total_tokens: prompt_tokens + completion_tokens
    }
  end
end
