#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'time'

module LessonContract
  module_function

  def validate(schema, record, path = '$')
    errors = []
    schema_type = schema['type']

    case schema_type
    when 'object'
      unless record.is_a?(Hash)
        return ["#{path}: expected object, got #{record.class}"]
      end

      Array(schema['required']).each do |key|
        errors << "#{path}: missing required key '#{key}'" unless record.key?(key)
      end

      props = schema['properties'] || {}
      props.each do |key, prop_schema|
        next unless record.key?(key)
        errors.concat(validate(prop_schema, record[key], "#{path}.#{key}"))
      end
    when 'array'
      unless record.is_a?(Array)
        return ["#{path}: expected array, got #{record.class}"]
      end

      min_items = schema['minItems']
      if min_items && record.length < min_items
        errors << "#{path}: expected at least #{min_items} items"
      end

      item_schema = schema['items']
      if item_schema
        record.each_with_index do |item, idx|
          errors.concat(validate(item_schema, item, "#{path}[#{idx}]"))
        end
      end
    when 'string'
      errors << "#{path}: expected string" unless record.is_a?(String)
      if schema['enum'] && !schema['enum'].include?(record)
        errors << "#{path}: must be one of #{schema['enum'].join(', ')}"
      end
      if schema['format'] == 'date-time'
        begin
          Time.iso8601(record)
        rescue ArgumentError
          errors << "#{path}: invalid date-time format"
        end
      end
    when 'integer'
      errors << "#{path}: expected integer" unless record.is_a?(Integer)
      if record.is_a?(Integer)
        min = schema['minimum']
        max = schema['maximum']
        errors << "#{path}: must be >= #{min}" if min && record < min
        errors << "#{path}: must be <= #{max}" if max && record > max
      end
    when 'number'
      errors << "#{path}: expected number" unless record.is_a?(Numeric)
      if record.is_a?(Numeric)
        min = schema['minimum']
        max = schema['maximum']
        errors << "#{path}: must be >= #{min}" if min && record < min
        errors << "#{path}: must be <= #{max}" if max && record > max
      end
    else
      # Unknown or unsupported type in schema; skip strict check.
    end

    errors
  end

  def validate_record(schema_path, record)
    schema = JSON.parse(File.read(schema_path))
    validate(schema, record)
  end
end
