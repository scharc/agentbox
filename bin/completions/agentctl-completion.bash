# Bash completion for agentctl
# Source this file or install to /etc/bash_completion.d/

# Helper to use correct tmux server (respects TMUX env var for custom sockets)
_agentctl_tmux() {
    if [[ -n "${TMUX:-}" ]]; then
        tmux -S "${TMUX%%,*}" "$@"
    else
        tmux "$@"
    fi
}

_agentctl_completion() {
    local cur prev cmd
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Get subcommand if present
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        # Complete subcommands (actual CLI command names)
        COMPREPLY=( $(compgen -W "list attach detach peek kill worktree wt --help --version" -- "$cur") )
        return 0
    fi

    cmd="${COMP_WORDS[1]}"

    case "$cmd" in
        attach)
            # Complete with existing sessions first, then known agent names as fallback
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                local sessions=$(_agentctl_tmux list-sessions -F "#{session_name}" 2>/dev/null)
                local agents="claude superclaude codex supercodex gemini supergemini shell"
                COMPREPLY=( $(compgen -W "$sessions $agents" -- "$cur") )
            fi
            ;;
        peek)
            # Complete with existing sessions for peek
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                local sessions=$(_agentctl_tmux list-sessions -F "#{session_name}" 2>/dev/null)
                COMPREPLY=( $(compgen -W "$sessions" -- "$cur") )
            elif [[ ${COMP_CWORD} -eq 3 ]]; then
                # Line count or --follow flag
                COMPREPLY=( $(compgen -W "10 20 50 100 200 --follow -f" -- "$cur") )
            fi
            ;;
        kill)
            # Complete with existing sessions for kill
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                local sessions=$(_agentctl_tmux list-sessions -F "#{session_name}" 2>/dev/null)
                COMPREPLY=( $(compgen -W "$sessions" -- "$cur") )
            elif [[ ${COMP_CWORD} -eq 3 ]]; then
                COMPREPLY=( $(compgen -W "--force -f" -- "$cur") )
            fi
            ;;
        list)
            # Options for list
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "--json" -- "$cur") )
            fi
            ;;
        worktree|wt)
            # Worktree subcommands
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "list add remove prune switch" -- "$cur") )
            elif [[ ${COMP_CWORD} -eq 3 ]]; then
                local subcmd="${COMP_WORDS[2]}"
                case "$subcmd" in
                    list)
                        COMPREPLY=( $(compgen -W "--json" -- "$cur") )
                        ;;
                    add)
                        # Complete with git branches
                        local branches=$(git branch --format='%(refname:short)' 2>/dev/null)
                        COMPREPLY=( $(compgen -W "$branches --create" -- "$cur") )
                        ;;
                    remove)
                        # Complete with existing worktree branches
                        local worktrees=$(git worktree list --porcelain 2>/dev/null | grep "^branch" | sed 's/branch refs\/heads\///')
                        COMPREPLY=( $(compgen -W "$worktrees" -- "$cur") )
                        ;;
                    switch)
                        # Complete with git branches for first arg
                        local branches=$(git branch --format='%(refname:short)' 2>/dev/null)
                        COMPREPLY=( $(compgen -W "$branches" -- "$cur") )
                        ;;
                esac
            elif [[ ${COMP_CWORD} -eq 4 ]]; then
                local subcmd="${COMP_WORDS[2]}"
                case "$subcmd" in
                    remove)
                        COMPREPLY=( $(compgen -W "--force" -- "$cur") )
                        ;;
                    switch)
                        # Agent type for switch
                        local agents="claude superclaude codex supercodex gemini supergemini shell"
                        COMPREPLY=( $(compgen -W "$agents" -- "$cur") )
                        ;;
                esac
            fi
            ;;
    esac
}

complete -F _agentctl_completion agentctl

# Also complete for common aliases
complete -F _agentctl_completion ctl
