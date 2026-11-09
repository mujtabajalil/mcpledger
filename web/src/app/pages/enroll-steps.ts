import { Component, inject } from '@angular/core';
import { Api } from '../api';

/** The three commands a developer runs. Used on the empty overview and in Settings. */
@Component({
  selector: 'sg-enroll-steps',
  template: `
    <ol class="steps">
      <li>
        <h3>Install the CLI</h3>
        <p class="muted small">Python 3.9+, no other dependencies. <code>pipx</code> or <code>uv tool</code> keeps it isolated.</p>
        <div class="cmd"><code>{{ install }}</code><button class="btn small" (click)="api.copy(install)">Copy</button></div>
      </li>
      <li>
        <h3>Join this machine to {{ api.org()?.name }}</h3>
        @if (api.org()?.enroll_command; as cmd) {
          <p class="muted small">The token only lets a machine join. Rotate it in Settings if it leaks.</p>
          <div class="cmd"><code>{{ cmd }}</code><button class="btn small" (click)="api.copy(cmd, 'Enroll command copied')">Copy</button></div>
        } @else {
          <p class="muted small">Ask an admin of {{ api.org()?.name }} for the enroll command.</p>
        }
      </li>
      <li>
        <h3>Scan</h3>
        <p class="muted small">Reads MCP configs and skill folders for Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Codex,
          Gemini CLI, Cline and Zed. Add <code>--introspect</code> to record each server's tool definitions,
          which is what catches a server that changes after you approve it.</p>
        <div class="cmd"><code>{{ scan }}</code><button class="btn small" (click)="api.copy(scan)">Copy</button></div>
      </li>
      <li>
        <h3>Keep it current</h3>
        <p class="muted small">Re-scan every 6 hours in the background, and fail CI or a git hook when something blocked is configured.</p>
        <div class="cmd"><code>{{ schedule }}</code><button class="btn small" (click)="api.copy(schedule)">Copy</button></div>
      </li>
    </ol>
  `,
  styles: `
    .steps { list-style: none; counter-reset: s; margin: 0; padding: 0; display: grid; gap: 22px; max-width: 820px; }
    .steps li { counter-increment: s; position: relative; padding-left: 44px; }
    .steps li::before { content: counter(s); position: absolute; left: 0; top: -2px; width: 28px; height: 28px; border-radius: 50%;
      background: var(--petrol); color: #fff; font-weight: 700; font-size: 14px; display: grid; place-items: center; }
    .steps h3 { margin-bottom: 4px; }
    .steps p { margin-bottom: 10px; }
  `,
})
export class EnrollSteps {
  api = inject(Api);
  install = 'pipx install mcpledger';
  scan = 'mcpledger scan --introspect';
  schedule = 'mcpledger schedule --every 6     # CI / pre-commit:  mcpledger check';
}
