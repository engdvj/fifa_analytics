# Skill: /sync-profile

Sincroniza skills e configurações do claude-profile para o projeto atual, propagando mudanças locais para o profile antes de aplicar o pull.

## Comportamento

1. Leia `.claude/profile-config.json` para obter `profile_path` e `project`
   - Se não existir: informe que o projeto precisa de bootstrap e interrompa
     ```
     Execute: bootstrap.ps1 --Project <nome-do-projeto>
     ```
2. Verifique que `profile_path` existe no filesystem — se não, informe e interrompa
3. Execute `git -C <profile_path> pull` para puxar o latest do repositório
4. **Detecte mudanças locais** — compare cada arquivo em `.claude/commands/` contra o profile:
   - Para cada `.md` em `.claude/commands/`:
     - Se diferente do profile (global ou project) → marcar para push
     - Se não existe no profile → marcar para push (arquivo novo)
     - Se idêntico → ignorar
5. **Push local → profile** — se houver arquivos marcados:
   - Copie cada arquivo marcado para `projects/<project>/commands/` (project tem precedência sobre global)
   - `git -C <profile_path> add projects/<project>/commands/`
   - `git -C <profile_path> commit -m "feat(<project>): sync local changes\n\nArquivos: <lista>"`
   - `git -C <profile_path> push`
   - Não empurre `.claude/settings.json` automaticamente — apenas commands
6. **Sync profile → local**:
   - Copie `global/commands/*` para `.claude/commands/` (sobrescreve)
   - Copie `projects/<project>/commands/*` para `.claude/commands/` (sobrescreve global — project tem precedência)
7. Para o `settings.json`:
   - Se `.claude/settings.json` já existe: pergunte ao usuário se deseja sobrescrever
   - Se não existe: copie `projects/<project>/settings.json` (ou `global/settings-base.json` como fallback)
8. **Commita os skills no repo local** — se `.claude/commands/` tiver arquivos novos ou modificados:
   - `git add .claude/commands/ .claude/profile-config.json`
   - `git commit -m "chore(claude): sync skills from claude-profile\n\nArquivos: <lista>"`
9. Informe o resultado:
   - Arquivos empurrados para o profile
   - Arquivos atualizados localmente (novos vs. modificados vs. sem alteração)
   - Versão final do profile: `git -C <profile_path> log -1 --format="%h %s"`

## Regras

- Nunca apague arquivos em `.claude/commands/` que não existam no profile — apenas adicione/atualize
- Mudanças locais sempre têm precedência — vão para `projects/<project>/commands/` mesmo que o arquivo original venha de `global/`
- Se `profile_path` não existir, interrompa imediatamente com mensagem clara
- Sempre confirme com o usuário antes de sobrescrever `.claude/settings.json`
- Se não houver mudanças locais, pule o passo 5 silenciosamente e prossiga para o sync normal
