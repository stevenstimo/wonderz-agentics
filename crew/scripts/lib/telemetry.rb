# frozen_string_literal: true

require 'json'
require 'securerandom'
require 'time'

class Telemetry
  def initialize(root:, run_id: nil)
    @root = root
    @run_id = run_id || "run-#{SecureRandom.hex(6)}"
    @dir = File.join(root, 'reports', 'runs')
    Dir.mkdir(@dir) unless Dir.exist?(@dir)
    @path = File.join(@dir, "#{@run_id}.jsonl")
  end

  attr_reader :run_id, :path

  def event(type, payload = {})
    row = {
      run_id: @run_id,
      type: type,
      ts: Time.now.utc.iso8601
    }.merge(payload)

    File.open(@path, 'a') { |f| f.puts(row.to_json) }
    row
  end
end
