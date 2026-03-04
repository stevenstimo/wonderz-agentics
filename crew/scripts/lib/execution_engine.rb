# frozen_string_literal: true

require 'open3'
require 'shellwords'
require 'time'
require_relative 'runtime_types'

class ExecutionEngine
  PATH_TOKEN = %r{\A(?:\.{0,2}/)?[A-Za-z0-9_\-./]+/?\z}.freeze
  IGNORED_PATH_TOKENS = %w[
    rg
    ruby
    bash
    cat
    sed
    grep
    awk
    sort
    uniq
    head
    tail
    wc
    xargs
    echo
    true
    false
    server
  ].freeze

  def initialize(shell: '/bin/zsh')
    @shell = shell
  end

  def render_cmd(template, vars)
    template.gsub(/\{([a-zA-Z0-9_]+)\}/) do |_m|
      key = Regexp.last_match(1)
      val = vars[key]
      if val.nil? || (val.respond_to?(:empty?) && val.empty?)
        "__MISSING_#{key}__"
      else
        shell_join_value(val)
      end
    end
  end

  def run_step(step, vars)
    step_id = step['id'] || 'unnamed_step'
    results = []

    Array(step['run']).each do |cmd_template|
      rendered = render_cmd(cmd_template, vars)
      if rendered.include?('__MISSING_')
        results << RuntimeTypes.step_result(
          step_id: step_id,
          command: cmd_template,
          ok: false,
          exit_code: nil,
          stdout: '',
          stderr: '',
          latency_ms: 0,
          skipped: true,
          reason: 'missing variables'
        )
        next
      end

      preflight_missing = detect_missing_paths(rendered)
      unless preflight_missing.empty?
        results << RuntimeTypes.step_result(
          step_id: step_id,
          command: rendered,
          ok: false,
          exit_code: nil,
          stdout: '',
          stderr: "missing path(s): #{preflight_missing.join(', ')}",
          latency_ms: 0,
          skipped: true,
          reason: 'missing_workspace_path'
        )
        next
      end

      start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      stdout, stderr, status = Open3.capture3(@shell, '-lc', rendered)
      latency_ms = ((Process.clock_gettime(Process::CLOCK_MONOTONIC) - start) * 1000).round

      no_matches = !status.success? && status.exitstatus == 1 && stderr.to_s.strip.empty?
      missing_path = !status.success? && stderr.to_s.match?(/No such file or directory|IO error.*os error 2/i)

      results << RuntimeTypes.step_result(
        step_id: step_id,
        command: rendered,
        ok: status.success? || no_matches,
        exit_code: status.exitstatus,
        stdout: stdout,
        stderr: stderr,
        latency_ms: latency_ms,
        skipped: missing_path,
        reason: if missing_path
                  'missing_workspace_path'
                elsif no_matches
                  'no_matches'
                else
                  nil
                end
      )
    end

    results
  end

  private

  def shell_join_value(value)
    case value
    when Array
      value.map { |v| Shellwords.escape(v.to_s) }.join(' ')
    else
      Shellwords.escape(value.to_s)
    end
  end

  def detect_missing_paths(command)
    candidates = command.split(/\s+/).map { |t| t.gsub(/\A['"]|['"]\z/, '') }
    paths = candidates.select { |tok| path_like_token?(tok) }
    missing = paths.select { |p| !File.exist?(p) }
    missing.uniq
  end

  def path_like_token?(token)
    return false if token.nil? || token.empty?
    return false if token.start_with?('-')
    return false unless token.match?(PATH_TOKEN)
    return false if token.include?('*') || token.include?('{') || token.include?('}') || token.include?('|')
    return false if token.include?(':') # avoid schema/pattern tokens
    return false if token.include?('=') # options and assignments
    return false unless token.include?('/') || token.end_with?('.rb') || token.end_with?('.yml') || token.end_with?('.yaml') || token.end_with?('.md') || token.end_with?('.jsx') || token.end_with?('.tsx') || token.end_with?('.py') || token.end_with?('.css')
    return false if IGNORED_PATH_TOKENS.include?(token)
    true
  end
end
