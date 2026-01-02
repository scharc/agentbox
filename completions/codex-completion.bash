# Codex bash completion
# Usage: source completions/codex-completion.bash

_codex_completion_commands() {
    local cmd="$1"
    "$cmd" --help 2>/dev/null | awk '
        BEGIN { in_cmd=0 }
        tolower($0) ~ /^commands:/ { in_cmd=1; next }
        tolower($0) ~ /^available commands:/ { in_cmd=1; next }
        in_cmd && /^[[:space:]]{2,}[[:alnum:]][^[:space:]]*/ { print $1; next }
        in_cmd && /^[^[:space:]]/ { in_cmd=0 }
    ' | sort -u
}

_codex_completion_options() {
    local cmd="$1"
    "$cmd" --help 2>/dev/null | awk '
        {
            for (i = 1; i <= NF; i++) {
                if ($i ~ /^--?[A-Za-z0-9]/) {
                    gsub(/[][(),.;:]+$/, "", $i)
                    print $i
                }
            }
        }
    ' | sort -u
}

_codex_completion() {
    local cur prev
    local -a completions
    local cmd="codex"

    command -v "$cmd" >/dev/null 2>&1 || return 0

    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    if [[ "$cur" == -* ]]; then
        mapfile -t completions < <(_codex_completion_options "$cmd")
    elif [[ ${COMP_CWORD} -le 1 || "$prev" == "help" ]]; then
        mapfile -t completions < <(_codex_completion_commands "$cmd")
    fi

    if [[ ${#completions[@]} -gt 0 ]]; then
        COMPREPLY=( $(compgen -W "${completions[*]}" -- "$cur") )
        return 0
    fi
}

complete -F _codex_completion codex
