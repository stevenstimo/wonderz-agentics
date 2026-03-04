# frozen_string_literal: true

require 'time'

module RuntimeTypes
  module_function

  def run_context(options)
    {
      run_id: options[:run_id],
      agent_id: options[:agent_id],
      intent: options[:intent],
      input: options[:input],
      query: options[:query],
      page_name: options[:page_name],
      baseline_file: options[:baseline_file],
      keyword: options[:keyword],
      service_hint: options[:service_hint],
      path_hint: options[:path_hint],
      max_retries: options[:max_retries],
      max_depth: options[:max_depth],
      max_runtime_seconds: options[:max_runtime_seconds],
      max_lesson_influence: options[:max_lesson_influence],
      approval_mode: options[:approval_mode],
      min_accept_score: options[:min_accept_score],
      llm_enabled: options[:llm_enabled],
      llm_model: options[:llm_model],
      json: options[:json]
    }
  end

  def decision_record(intent:, confidence:, playbook_id:, reason:)
    {
      intent: intent,
      confidence: confidence,
      playbook_id: playbook_id,
      reason: reason,
      created_at: Time.now.utc.iso8601
    }
  end

  def step_result(step_id:, command:, ok:, exit_code:, stdout:, stderr:, latency_ms:, skipped: false, reason: nil)
    {
      step_id: step_id,
      command: command,
      ok: ok,
      exit_code: exit_code,
      stdout: stdout,
      stderr: stderr,
      latency_ms: latency_ms,
      skipped: skipped,
      reason: reason
    }
  end

  def evaluation_record(scores:, verdict:, reasons:, contract_pass:, error_count:)
    {
      scores: scores,
      total_score: scores.values.sum / scores.length.to_f,
      verdict: verdict,
      reasons: reasons,
      contract_pass: contract_pass,
      contract_error_count: error_count,
      created_at: Time.now.utc.iso8601
    }
  end

  def failure_record(type:, message:, retry_count:, step_id: nil)
    {
      type: type,
      message: message,
      retry_count: retry_count,
      step_id: step_id,
      created_at: Time.now.utc.iso8601
    }
  end
end
