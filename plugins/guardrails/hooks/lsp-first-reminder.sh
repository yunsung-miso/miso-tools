#!/bin/bash
# Non-blocking PreToolUse hook on Grep: reminds the model to prefer LSP
# for symbol-level searches. Never prompts the user, never blocks the call.
cat > /dev/null  # consume stdin (hook input JSON, unused)
echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Reminder: if this Grep call is looking for a code SYMBOL (function/class/variable definition, references, usages, implementations, or type info), use the LSP tool instead (goToDefinition, findReferences, findImplementations, hover, documentSymbols). Grep is appropriate only for plain-text patterns: comments, strings, log messages, config values, or languages without an LSP server."}}'
