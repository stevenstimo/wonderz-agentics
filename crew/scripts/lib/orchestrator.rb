# frozen_string_literal: true

require 'json'
require 'time'
require 'yaml'
require_relative 'decision_engine'
require_relative 'execution_engine'
require_relative 'evaluator'
require_relative 'governance'
require_relative 'llm_client'
require_relative 'memory_manager'
require_relative 'response_builder'
require_relative 'runtime_types'
require_relative 'telemetry'

class Orchestrator
  ROOT = File.expand_path('../..', __dir__)
  AGENTS_DIR = File.join(ROOT, 'agents')
  PLAYBOOKS_DIR = File.join(ROOT, 'playbooks')

  def initialize(options)
    @ctx = RuntimeTypes.run_context(options)
    @started_at = Time.now
    @state = 'intake'
    @retry_count = 0

    @profile = load_agent(@ctx[:agent_id])
    apply_runtime_defaults!
    @playbooks = load_playbooks
    @decision_engine = DecisionEngine.new(profile: @profile, playbooks: @playbooks)
    @execution_engine = ExecutionEngine.new
    @evaluator = Evaluator.new(root: ROOT, min_accept_score: @ctx[:min_accept_score])
    @governance = Governance.new(profile: @profile, approval_mode: @ctx[:approval_mode])
    @llm = LlmClient.new(config: @ctx[:llm])
    @memory = MemoryManager.new(root: ROOT)
    @telemetry = Telemetry.new(root: ROOT, run_id: @ctx[:run_id])

    @decision = nil
    @lessons = []
    @step_results = []
    @response = nil
    @evaluation = nil
    @llm_result = nil
    @failures = []
    @classification_confidence = 0.0
    @classification_reason = nil
    @classification_margin = 0.0
    @classification_candidates = []
    @needs_clarification = false
  end

  def run
    @telemetry.event('run_started', agent_id: @ctx[:agent_id], intent: @ctx[:intent], input: @ctx[:input])

    loop do
      enforce_runtime_limits
      case @state
      when 'intake'
        @state = 'classify'
      when 'classify'
        handle_classify
        @state = @needs_clarification ? 'persist' : 'route'
      when 'route'
        handle_route
        @state = 'preload_lessons'
      when 'preload_lessons'
        handle_preload_lessons
        @state = 'plan'
      when 'plan'
        @plan = Array(current_playbook['steps'])
        @state = 'execute'
      when 'execute'
        handle_execute
        @state = 'evaluate'
      when 'evaluate'
        handle_evaluate
        @state = 'decide'
      when 'decide'
        outcome = @decision_engine.decide_next(
          evaluation: @evaluation,
          retry_count: @retry_count,
          max_retries: @ctx[:max_retries]
        )
        @telemetry.event('decision_made', outcome: outcome, retry_count: @retry_count, evaluation: @evaluation)
        case outcome
        when 'accept'
          @state = 'learn'
        when 'retry'
          @retry_count += 1
          @state = 'execute'
        else
          emit_failure('retry_exhausted', 'Evaluation did not reach accept threshold', nil)
          @state = 'persist'
        end
      when 'learn'
        handle_learn
        @state = 'persist'
      when 'persist'
        summary = build_summary
        @telemetry.event('run_completed', summary: summary)
        return summary
      else
        raise "Unknown runtime state: #{@state}"
      end
    end
  rescue StandardError => e
    emit_failure(map_exception_type(e), e.message, nil)
    @telemetry.event('run_failed', error: e.message, state: @state, retry_count: @retry_count)
    raise
  end

  private

  def handle_classify
    classification = @decision_engine.classify_intent(
      requested_intent: @ctx[:intent],
      query: @ctx[:query] || @ctx[:input]
    )
    @ctx[:intent] = classification[:intent]
    @classification_confidence = classification[:confidence]
    @classification_reason = classification[:reason]
    @classification_margin = classification[:margin]
    @classification_candidates = classification[:candidates]
    @needs_clarification = classification[:ambiguous]
    @telemetry.event(
      'intent_classified',
      intent: classification[:intent],
      confidence: classification[:confidence],
      margin: classification[:margin],
      ambiguous: classification[:ambiguous],
      reason: classification[:reason],
      candidates: classification[:candidates]
    )
    return unless @needs_clarification

    emit_failure('intent_ambiguous', 'Intent confidence too low or margin too small', nil)
    @response = build_clarification_response
  end

  def handle_route
    @decision = @decision_engine.route(
      @ctx[:intent],
      confidence: @classification_confidence > 0 ? @classification_confidence : 0.9,
      reason: @classification_reason
    )
    @telemetry.event('playbook_routed', decision: @decision)
  end

  def handle_preload_lessons
    context_type = current_playbook.dig('learning', 'context_type') || @ctx[:intent]
    selected = @memory.select_lessons(
      agent_id: @ctx[:agent_id],
      context_type: context_type,
      path_hint: @ctx[:path_hint],
      limit: 2
    )
    @lessons = @memory.apply_influence(selected, @ctx[:max_lesson_influence])
    @telemetry.event('lessons_loaded', selected: @lessons.length, context_type: context_type)
  end

  def handle_execute
    vars = build_vars
    @step_results = []

    @plan.each do |step|
      if step['condition'] && step['condition'].include?('root_cause_confidence')
        # Skip conditional steps for now; deterministic MVP.
        next
      end

      results = @execution_engine.run_step(step, vars)
      results.each do |res|
        if res[:skipped] && res[:reason] == 'missing_workspace_path'
          emit_failure('missing_workspace_path', "Workspace path missing for command: #{res[:command]}", step['id'])
        elsif !res[:ok] && !res[:skipped]
          emit_failure('tool_execution_failed', "Step command failed: #{res[:command]}", step['id'])
        end

        gov = @governance.check_command(res[:command])
        if gov[:status] == 'blocked'
          emit_failure('governance_blocked', "Blocked command: #{res[:command]} (#{gov[:reason]})", step['id'])
          raise "Governance blocked command: #{res[:command]} (#{gov[:reason]})"
        end

        if gov[:status] == 'propose_only' && @ctx[:approval_mode] != 'auto'
          res[:ok] = false
          res[:reason] = gov[:reason]
          res[:stderr] = "governance: #{gov[:reason]}"
          emit_failure('governance_blocked', "Command requires approval: #{res[:command]}", step['id'])
        end
      end

      if step['id'] == 'locate_component'
        vars['target_files'] = collect_target_files(results)
      end

      @step_results.concat(results)
      @telemetry.event('step_finished', step_id: step['id'], result_count: results.length)
    end

    evidence_items = response_evidence_items
    cause, fix = ResponseBuilder.derive(intent: @ctx[:intent], evidence_items: evidence_items, lessons: @lessons)
    @llm_result = @llm.generate_diagnosis(
      intent: @ctx[:intent],
      query: @ctx[:query] || @ctx[:input],
      evidence_items: evidence_items,
      lessons: @lessons,
      fallback_cause: cause,
      fallback_fix: fix
    )
    if @llm_result[:used]
      cause = @llm_result[:cause]
      fix = @llm_result[:fix]
      @telemetry.event(
        'llm_call',
        provider: @llm_result[:provider],
        model: @llm_result[:model],
        latency_ms: @llm_result[:latency_ms],
        usage: @llm_result[:usage]
      )
    else
      @telemetry.event('llm_skipped', reason: @llm_result[:reason])
    end

    @response = ResponseBuilder.build_markdown(
      evidence_items: evidence_items,
      cause: cause,
      fix: fix,
      closing_question: @profile.dig('response_contract', 'closing_question') || 'Wil je dat ik deze wijziging direct doorvoer?'
    )
  end

  def handle_evaluate
    @evaluation = @evaluator.evaluate(
      profile_path: File.join(AGENTS_DIR, "#{@ctx[:agent_id]}.profile.yml"),
      response_text: @response,
      evidence_items: response_evidence_items,
      step_results: @step_results
    )
    emit_failure('contract_failed', 'Response failed contract validation', nil) unless @evaluation[:contract_pass]
    @telemetry.event('evaluation_finished', evaluation: @evaluation)
  end

  def handle_learn
    return unless @profile.dig('learning', 'enable_lessons_log')

    context_type = current_playbook.dig('learning', 'context_type') || @ctx[:intent]
    lesson = @memory.append_lesson(
      agent_id: @ctx[:agent_id],
      context_type: context_type,
      evidence: response_evidence_items,
      what_worked: ['Use orchestrator evidence-first flow with selected lessons'],
      source: 'task_success',
      confidence: @evaluation[:total_score],
      ttl_days: @profile.dig('learning', 'decay_days') || 30
    )
    @telemetry.event('lesson_appended', lesson_id: lesson['id'])
  end

  def current_playbook
    @playbooks.fetch(@decision[:playbook_id])
  end

  def build_vars
    frontend_search_roots = existing_paths_or_fallback(
      Array(@profile.dig('project_structure_map', 'frontend_pages')) + Array(@profile.dig('project_structure_map', 'frontend_layouts')),
      ['.']
    )
    backend_paths = existing_paths_or_fallback(
      Array(@profile.dig('project_structure_map', 'backend_api')),
      ['.']
    )
    global_style_files = existing_paths_or_fallback(
      Array(@profile.dig('project_structure_map', 'global_styles')),
      ['.']
    )

    {
      'page_name' => @ctx[:page_name],
      'baseline_file' => @ctx[:baseline_file] || @profile.dig('known_baselines', 'layout_reference_file'),
      'keyword' => @ctx[:keyword],
      'service_hint' => @ctx[:service_hint],
      'target_files' => [],
      'root_paths' => @profile.dig('project_structure_map', 'frontend_layouts'),
      'frontend_search_roots' => frontend_search_roots,
      'backend_paths' => backend_paths,
      'global_style_files' => global_style_files
    }
  end

  def collect_target_files(step_results)
    files = []
    step_results.each do |r|
      next unless r[:ok]
      r[:stdout].to_s.lines.each do |line|
        candidate = line.strip
        next unless candidate.match?(/\.(jsx|tsx|js|ts|rb|py|yml|yaml|md|css)$/)
        files << candidate
      end
    end
    files.uniq
  end

  def existing_paths_or_fallback(paths, fallback)
    existing = Array(paths).select { |p| !p.to_s.strip.empty? && File.exist?(p) }
    existing.empty? ? fallback : existing
  end

  def response_evidence_items
    items = ResponseBuilder.to_evidence_items(ResponseBuilder.parse_evidence_lines(@step_results))
    if items.empty? && @lessons.any?
      items = Array(@lessons.first['evidence']).map do |ev|
        next unless ev.is_a?(Hash)
        next unless ev['file'] && ev['line'] && ev['matched_text']
        { 'file' => ev['file'].to_s, 'line' => ev['line'].to_i, 'matched_text' => ev['matched_text'].to_s }
      end.compact
    end
    items = [{ 'file' => 'unknown', 'line' => 1, 'matched_text' => 'no evidence captured' }] if items.empty?
    items
  end

  def load_agent(agent_id)
    path = File.join(AGENTS_DIR, "#{agent_id}.profile.yml")
    raise "Agent profile not found: #{path}" unless File.exist?(path)

    YAML.load_file(path)
  end

  def load_playbooks
    out = {}
    Dir.glob(File.join(PLAYBOOKS_DIR, '*.yml')).sort.each do |path|
      data = YAML.load_file(path)
      out[data['id']] = data
    end
    out
  end

  def apply_runtime_defaults!
    runtime = @profile.fetch('runtime', {})
    @ctx[:max_retries] ||= runtime['max_retries'] || 1
    @ctx[:max_depth] ||= runtime['max_depth'] || 3
    @ctx[:max_runtime_seconds] ||= runtime['max_runtime_seconds'] || 90
    @ctx[:max_lesson_influence] ||= runtime['max_lesson_influence'] || 2
    @ctx[:min_accept_score] ||= runtime['min_accept_score'] || 0.75
    @ctx[:approval_mode] ||= 'manual'
    llm_cfg = @profile.fetch('llm', {})
    @ctx[:llm] = {
      'enabled' => @ctx[:llm_enabled].nil? ? llm_cfg.fetch('enabled', false) : @ctx[:llm_enabled],
      'provider' => llm_cfg.fetch('provider', 'openai_compatible'),
      'model' => @ctx[:llm_model] || llm_cfg.fetch('model', 'gpt-4o-mini'),
      'endpoint' => llm_cfg.fetch('endpoint', 'https://api.openai.com/v1/chat/completions'),
      'api_key_env' => llm_cfg.fetch('api_key_env', 'OPENAI_API_KEY'),
      'timeout_seconds' => llm_cfg.fetch('timeout_seconds', 20)
    }
  end

  def enforce_runtime_limits
    raise 'Max retry depth exceeded' if @retry_count > @ctx[:max_depth]

    elapsed = Time.now - @started_at
    raise 'Max runtime exceeded' if elapsed > @ctx[:max_runtime_seconds]
  end

  def emit_failure(type, message, step_id)
    record = RuntimeTypes.failure_record(
      type: type,
      message: message,
      retry_count: @retry_count,
      step_id: step_id
    )
    @failures << record
    @telemetry.event('failure', failure: record)
  end

  def map_exception_type(error)
    message = error.message.to_s
    return 'timeout' if message.include?('Max runtime exceeded')
    return 'retry_exhausted' if message.include?('Max retry depth exceeded')
    return 'governance_blocked' if message.include?('Governance blocked command')

    'runtime_error'
  end

  def build_summary
    executed = @step_results.reject { |r| r[:skipped] || r['skipped'] }
    success_count = executed.count { |r| r[:ok] || r['ok'] }
    total_latency_ms = executed.sum { |r| (r[:latency_ms] || r['latency_ms'] || 0).to_i }
    step_success_ratio = executed.empty? ? 0.0 : (success_count.to_f / executed.length)
    llm_usage = @llm_result && @llm_result[:usage] ? @llm_result[:usage] : { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }

    {
      status: if @needs_clarification
                'needs_clarification'
              elsif @evaluation && @evaluation[:verdict] == 'accept'
                'success'
              else
                'needs_approval'
              end,
      run_id: @telemetry.run_id,
      runtime_log: @telemetry.path,
      agent_id: @ctx[:agent_id],
      intent: @ctx[:intent],
      playbook: @decision && @decision[:playbook_id],
      retry_count: @retry_count,
      lessons_used: @lessons.length,
      metrics: {
        step_count: executed.length,
        step_success_ratio: step_success_ratio.round(4),
        total_step_latency_ms: total_latency_ms,
        llm_usage: llm_usage
      },
      evaluation: @evaluation,
      llm: @llm_result,
      failures: @failures,
      response: @response
    }
  end

  def build_clarification_response
    suggestion_lines = @classification_candidates.first(2).map do |c|
      "- Mogelijke intent: `#{c[:intent]}` (score=#{format('%.3f', c[:score])})"
    end
    suggestion_lines = ['- Mogelijke intent: `layout_inconsistency`'] if suggestion_lines.empty?
    closing_question = @profile.dig('response_contract', 'closing_question') || 'Wil je dat ik deze wijziging direct doorvoer?'

    <<~MD
      Gevonden:
      - `unknown:1` -> `intent classification ambiguous`

      Oorzaak:
      - De vraag matcht meerdere intent-routes met te kleine scoremarge (margin=#{format('%.3f', @classification_margin)}).

      Fix voorstel:
      #{suggestion_lines.join("\n")}
      - Specificeer of je vooral layout/frontend of backend/data wilt analyseren.

      Vraag:
      - Bedoel je `layout_inconsistency` of `api_or_data_issue` (of `architecture_or_explanation`)?
      - #{closing_question}
    MD
  end
end
