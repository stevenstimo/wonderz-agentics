#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'yaml'

EXIT_PASS = 0
EXIT_CONTRACT_FAIL = 1
EXIT_USAGE = 2

def parse_options(argv)
  options = { json: false }
  parser = OptionParser.new do |opts|
    opts.banner = 'Usage: ruby crew/scripts/validate_response_contract.rb [--json] <agent_profile.yml> <response.md>'
    opts.on('--json', 'Print machine-readable JSON summary') { options[:json] = true }
  end
  parser.parse!(argv)
  [options, argv]
rescue OptionParser::ParseError => e
  warn e.message
  exit EXIT_USAGE
end

def parse_sections(response)
  sections = {}
  current = nil

  response.each_line do |line|
    header = line.match(/^([^\n:]+):\s*$/)
    if header
      current = header[1].strip
      sections[current] = []
      next
    end
    sections[current] << line if current
  end

  sections.transform_values { |lines| lines.join.strip }
end

def evidence_lines(found_section_text)
  return [] if found_section_text.nil? || found_section_text.empty?
  found_section_text.lines.map(&:strip).select { |line| line.start_with?('- ') }
end

def validate_evidence(found_section_text, pattern)
  errs = []
  lines = evidence_lines(found_section_text)
  if lines.empty?
    errs << 'Gevonden section has no evidence bullet lines'
    return errs
  end

  regex = Regexp.new(pattern)
  lines.each_with_index do |line, idx|
    unless regex.match?(line)
      errs << "Evidence line #{idx + 1} has invalid format: #{line}"
    end
  end

  errs
end

def output_result(json_mode, payload)
  if json_mode
    puts JSON.pretty_generate(payload)
  else
    puts payload[:status]
    payload[:errors].each { |e| puts "- #{e}" } unless payload[:errors].empty?
  end
end

options, args = parse_options(ARGV.dup)

if args.length < 2
  warn 'Usage: ruby crew/scripts/validate_response_contract.rb [--json] <agent_profile.yml> <response.md>'
  exit EXIT_USAGE
end

profile_path = args[0]
response_path = args[1]

unless File.exist?(profile_path)
  warn "Profile not found: #{profile_path}"
  exit EXIT_USAGE
end

unless File.exist?(response_path)
  warn "Response file not found: #{response_path}"
  exit EXIT_USAGE
end

profile = YAML.load_file(profile_path)
contract = profile.fetch('response_contract', {})
response = File.read(response_path)
sections = parse_sections(response)

errors = []

required_sections = contract.fetch('required_sections', [])
required_sections.each do |section|
  errors << "Missing required section header: #{section}:" unless sections.key?(section)
end

banned_patterns = contract.fetch('banned_patterns', [])
banned_patterns.each do |pattern|
  errors << "Contains banned pattern: #{pattern}" if response.include?(pattern)
end

evidence_pattern = contract['evidence_line_pattern'] || '^\\s*-\\s*`[^`]+:\\d+`\\s*->\\s*`.+`\\s*$'
if sections.key?('Gevonden')
  errors.concat(validate_evidence(sections['Gevonden'], evidence_pattern))
else
  errors << 'Missing Gevonden section for evidence validation'
end

closing_question = contract['closing_question']
if closing_question && !closing_question.strip.empty?
  errors << 'Missing required closing question' unless response.include?(closing_question)
end

status = errors.empty? ? 'PASS: response_contract validation succeeded' : 'FAIL: response_contract validation failed'
payload = {
  status: status,
  pass: errors.empty?,
  error_count: errors.length,
  errors: errors,
  profile: profile['agent_id'],
  response_file: response_path
}

output_result(options[:json], payload)
exit(errors.empty? ? EXIT_PASS : EXIT_CONTRACT_FAIL)
