#compdef agentctl ctl

# Zsh completion for agentctl

# Helper to use correct tmux server (respects TMUX env var for custom sockets)
_agentctl_tmux() {
    if [[ -n "${TMUX:-}" ]]; then
        tmux -S "${TMUX%%,*}" "$@"
    else
        tmux "$@"
    fi
}

_agentctl() {
    local -a commands
    commands=(
        'list:List tmux sessions'
        'attach:Attach to agent session (create if missing)'
        'detach:Detach current client'
        'peek:View session scrollback without attaching'
        'kill:Kill a tmux session'
        'worktree:Git worktree management'
        'wt:Git worktree management (alias)'
    )

    local -a agents
    agents=(
        'claude:Attach to Claude session'
        'superclaude:Attach to Super Claude session'
        'codex:Attach to Codex session'
        'supercodex:Attach to Super Codex session'
        'gemini:Attach to Gemini session'
        'supergemini:Attach to Super Gemini session'
        'shell:Attach to shell session'
    )

    local -a worktree_commands
    worktree_commands=(
        'list:List git worktrees'
        'add:Create a new worktree'
        'remove:Remove a worktree'
        'prune:Clean up stale worktree metadata'
        'switch:Switch to worktree and create agent session'
    )

    _arguments -C \
        '1: :->command' \
        '*:: :->args'

    case $state in
        command)
            _describe 'command' commands
            ;;
        args)
            case "$words[1]" in
                attach)
                    # Complete with existing sessions first, then agent names as fallback
                    local -a sessions
                    sessions=(${(f)"$(_agentctl_tmux list-sessions -F "#{session_name}" 2>/dev/null)"})
                    if [[ ${#sessions} -gt 0 ]]; then
                        _describe 'session' sessions
                    fi
                    _describe 'agent' agents
                    ;;
                peek|kill)
                    # Get list of current tmux sessions
                    local -a sessions
                    sessions=(${(f)"$(_agentctl_tmux list-sessions -F "#{session_name}" 2>/dev/null)"})
                    if [[ ${#sessions} -gt 0 ]]; then
                        _describe 'session' sessions
                    fi

                    # For peek, also suggest line counts and --follow
                    if [[ "$words[1]" == "peek" && $CURRENT -eq 3 ]]; then
                        _values 'lines' 10 20 50 100 200
                        _arguments '--follow[Follow output like tail -f]' '-f[Follow output]'
                    fi

                    # For kill, suggest --force flag
                    if [[ "$words[1]" == "kill" && $CURRENT -eq 3 ]]; then
                        _arguments '--force[Skip confirmation]' '-f[Skip confirmation]'
                    fi
                    ;;
                list)
                    _arguments '--json[Output as JSON]'
                    ;;
                worktree|wt)
                    # Worktree subcommands
                    if [[ $CURRENT -eq 2 ]]; then
                        _describe 'worktree command' worktree_commands
                    else
                        local subcmd="$words[2]"
                        case "$subcmd" in
                            list)
                                _arguments '--json[Output as JSON]'
                                ;;
                            add)
                                # Complete with git branches
                                if [[ $CURRENT -eq 3 ]]; then
                                    local -a branches
                                    branches=(${(f)"$(git branch --format='%(refname:short)' 2>/dev/null)"})
                                    if [[ ${#branches} -gt 0 ]]; then
                                        _describe 'branch' branches
                                    fi
                                elif [[ $CURRENT -eq 4 ]]; then
                                    _arguments '--create[Create branch if it does not exist]'
                                fi
                                ;;
                            switch)
                                if [[ $CURRENT -eq 3 ]]; then
                                    # Complete with git branches for first arg
                                    local -a branches
                                    branches=(${(f)"$(git branch --format='%(refname:short)' 2>/dev/null)"})
                                    if [[ ${#branches} -gt 0 ]]; then
                                        _describe 'branch' branches
                                    fi
                                elif [[ $CURRENT -eq 4 ]]; then
                                    # Complete with agent types for second arg
                                    _describe 'agent' agents
                                fi
                                ;;
                            remove)
                                if [[ $CURRENT -eq 3 ]]; then
                                    # Complete with existing worktree branches
                                    local -a worktrees
                                    worktrees=(${(f)"$(git worktree list --porcelain 2>/dev/null | grep '^branch' | sed 's/branch refs\/heads\///')"})
                                    if [[ ${#worktrees} -gt 0 ]]; then
                                        _describe 'worktree' worktrees
                                    fi
                                elif [[ $CURRENT -eq 4 ]]; then
                                    _arguments '--force[Force removal]'
                                fi
                                ;;
                        esac
                    fi
                    ;;
            esac
            ;;
    esac
}

_agentctl "$@"
