# frozen_string_literal: true

class Governance
  DANGEROUS_PATTERNS = [
    /\brm\s+-rf\b/i,
    /\bgit\s+reset\s+--hard\b/i,
    /\bgit\s+checkout\s+--\b/i,
    /\bdd\s+if=/i
  ].freeze

  def initialize(profile:, approval_mode: 'manual')
    @profile = profile
    @approval_mode = approval_mode
  end

  def check_command(command)
    return block('command is empty') if command.to_s.strip.empty?

    return block('dangerous command pattern detected') if DANGEROUS_PATTERNS.any? { |p| command.match?(p) }

    policy = @profile.fetch('governance', {})
    allow = Array(policy.fetch('allowed_prefixes', []))
    propose_only = Array(policy.fetch('propose_only_prefixes', []))

    return allow_result if allow.any? { |prefix| command.start_with?(prefix) }

    if propose_only.any? { |prefix| command.start_with?(prefix) }
      return @approval_mode == 'auto' ? allow_result : propose('requires explicit approval class')
    end

    @approval_mode == 'auto' ? allow_result : propose('command outside allowlist')
  end

  private

  def allow_result
    { status: 'allowed', reason: nil }
  end

  def propose(reason)
    { status: 'propose_only', reason: reason }
  end

  def block(reason)
    { status: 'blocked', reason: reason }
  end
end
