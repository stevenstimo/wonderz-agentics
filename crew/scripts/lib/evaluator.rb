# frozen_string_literal: true

require 'json'
require 'open3'
require 'tempfile'
require_relative 'runtime_types'

class Evaluator
  def initialize(root:, min_accept_score: 0.75)
    @root = root
    @min_accept_score = min_accept_score
    @validator = File.join(root, 'scripts', 'validate_response_contract.rb')
  end

  def evaluate(profile_path:, response_text:, evidence_items:, step_results:)
    contract_pass, contract_errors = run_contract_check(profile_path, response_text)
    evidence_score = evidence_items.empty? ? 0.2 : 1.0
    execution_ok = Array(step_results).count { |r| r[:ok] || r['ok'] }
    execution_total = Array(step_results).reject { |r| r[:skipped] || r['skipped'] }.length
    execution_score = execution_total.zero? ? 0.4 : (execution_ok.to_f / execution_total)

    security_score = response_text.include?('rm -rf') ? 0.0 : 1.0
    contract_score = contract_pass ? 1.0 : 0.0
    fixability_score = response_text.include?('Fix voorstel:') ? 1.0 : 0.2

    scores = {
      contract: contract_score,
      evidence: evidence_score,
      execution: execution_score,
      security: security_score,
      fixability: fixability_score
    }

    total = scores.values.sum / scores.length.to_f
    verdict = (contract_pass && total >= @min_accept_score) ? 'accept' : 'retry'
    reasons = []
    reasons << 'response contract failed' unless contract_pass
    reasons << 'score below threshold' if total < @min_accept_score
    reasons = ['accepted'] if reasons.empty?

    RuntimeTypes.evaluation_record(
      scores: scores,
      verdict: verdict,
      reasons: reasons,
      contract_pass: contract_pass,
      error_count: contract_errors.length
    )
  end

  private

  def run_contract_check(profile_path, response_text)
    tf = Tempfile.new(['crew-response', '.md'])
    tf.write(response_text)
    tf.flush

    stdout, _stderr, status = Open3.capture3('ruby', @validator, '--json', profile_path, tf.path)
    payload = JSON.parse(stdout) rescue {}
    [status.success?, Array(payload['errors'])]
  ensure
    tf.close!
  end
end
