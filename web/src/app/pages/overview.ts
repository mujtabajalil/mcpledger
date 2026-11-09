import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api, ComponentRow, Overview, errorText } from '../api';
import { AgoPipe, ClientPipe, SevBadge, StatusBadge } from '../shared';
import { EnrollSteps } from './enroll-steps';

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

@Component({
  selector: 'sg-overview',
  imports: [RouterLink, AgoPipe, ClientPipe, SevBadge, StatusBadge, EnrollSteps],
  template: `
    <div class="page">
      @if (error()) { <div class="error-box">{{ error() }}</div> }
      @if (data(); as d) {
        @if (d.devices === 0) {
          <div class="page-head"><div>
            <h1>Enroll your first machine</h1>
            <p class="sub">MCPLedger learns what's installed from the <code>mcpledger</code> CLI. Run these on any developer laptop
              (yours is a good start). It takes about a minute and changes nothing on the machine.</p>
          </div></div>
          <sg-enroll-steps />
        } @else {
          <header class="verdict">
            <h1>{{ headline() }}</h1>
            <p class="facts">
              {{ d.devices }} {{ d.devices === 1 ? 'machine' : 'machines' }} reporting,
              {{ d.mcp_servers }} MCP {{ d.mcp_servers === 1 ? 'server' : 'servers' }} and {{ d.skills }} {{ d.skills === 1 ? 'skill' : 'skills' }}
              across {{ d.installs }} installs.
              @if (d.stale_devices) { <a routerLink="/devices">{{ d.stale_devices }} haven't reported in a week.</a> }
            </p>
          </header>

          <div class="grid">
            <section class="panel decide">
              <header><h2>Waiting on a decision</h2><span class="spacer"></span>
                <a routerLink="/inventory" class="small">Open inventory</a></header>
              @if (queue().length === 0) {
                <div class="empty"><h3>Nothing waiting</h3><p>New servers, skills and changes will show up here.</p></div>
              } @else {
                <div class="table-wrap"><table class="ledger">
                  <thead><tr><th>Component</th><th>Status</th><th>Risk</th><th class="num hide-sm">Machines</th></tr></thead>
                  <tbody>
                    @for (c of queue(); track c.id) {
                      <tr class="clickable" (click)="open(c.id)">
                        <td><a [routerLink]="['/inventory', c.id]" (click)="$event.stopPropagation()"><strong>{{ c.name }}</strong></a>
                          <div class="faint small">{{ c.kind === 'skill' ? 'Skill' : 'MCP server' }} in
                            @for (cl of c.clients; track cl; let last = $last) { {{ cl | client }}{{ last ? '' : ', ' }} }</div></td>
                        <td><sg-status [value]="c.status" /></td>
                        <td><sg-sev [value]="c.max_severity" /></td>
                        <td class="num hide-sm">{{ c.devices }}</td>
                      </tr>
                    }
                  </tbody>
                </table></div>
              }
            </section>

            <section class="panel">
              <header><h2>Latest activity</h2><span class="spacer"></span><a routerLink="/alerts" class="small">All alerts</a></header>
              <ol class="feed">
                @for (e of d.recent_events; track e.id) {
                  <li [class]="'s-' + e.severity">
                    @if (e.component_id) { <a [routerLink]="['/inventory', e.component_id]">{{ e.title }}</a> } @else { <span>{{ e.title }}</span> }
                    <span class="faint small">{{ e.created_at | ago }}</span>
                  </li>
                } @empty { <li class="faint">No activity yet.</li> }
              </ol>
            </section>
          </div>
        }
      } @else if (!error()) { <p class="faint">Loading…</p> }
    </div>
  `,
  styles: `
    .verdict { margin-bottom: 28px; }
    .verdict h1 { font-size: clamp(26px, 3.2vw, 38px); line-height: 1.12; font-weight: 800; letter-spacing: -0.025em; max-width: 26ch; }
    .facts { margin-top: 10px; color: var(--ink-soft); font-size: 16px; max-width: 70ch; }
    .grid { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr); gap: 20px; align-items: start; }
    .grid .panel + .panel { margin-top: 0; }
    .feed { list-style: none; margin: 0; padding: 6px 0; }
    .feed li { padding: 9px 20px 9px 30px; position: relative; display: flex; flex-direction: column; font-size: 14px; }
    .feed li::before { content: ""; position: absolute; left: 16px; top: 16px; width: 6px; height: 6px; border-radius: 50%; background: var(--sev-info); }
    .feed li.s-critical::before, .feed li.s-high::before { background: var(--block); }
    .feed li.s-medium::before { background: var(--drift); }
    .feed li.s-low::before { background: var(--sev-low); }
    .feed a { color: var(--ink); font-weight: 500; text-decoration: none; }
    .feed a:hover { text-decoration: underline; }
    @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } }
  `,
})
export class OverviewPage implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  data = signal<Overview | null>(null);
  rows = signal<ComponentRow[]>([]);
  error = signal('');

  queue = computed(() =>
    this.rows()
      .filter(r => r.status === 'pending' || r.status === 'drift')
      .sort((a, b) => (a.status === 'drift' ? 0 : 1) - (b.status === 'drift' ? 0 : 1)
        || (SEV_ORDER[a.max_severity ?? 'info'] ?? 5) - (SEV_ORDER[b.max_severity ?? 'info'] ?? 5)
        || b.devices - a.devices)
      .slice(0, 12));

  headline = computed(() => {
    const d = this.data();
    if (!d) return '';
    const p = d.status_counts.pending, ch = d.status_counts.drift, b = d.status_counts.blocked;
    const parts: string[] = [];
    if (ch) parts.push(`${ch} changed since approval`);
    if (p) parts.push(`${p} ${p === 1 ? 'needs' : 'need'} review`);
    if (!parts.length) return b ? `Everything else is approved. ${b} blocked.` : 'Everything installed is approved.';
    const s = parts.join(', ');
    return s.charAt(0).toUpperCase() + s.slice(1) + '.';
  });

  async ngOnInit() {
    try {
      const [d, rows] = await Promise.all([
        this.api.get<Overview>('/api/org/overview'),
        this.api.get<ComponentRow[]>('/api/components'),
      ]);
      this.data.set(d); this.rows.set(rows);
    } catch (e) { this.error.set(errorText(e)); }
  }

  open(id: string) { this.router.navigate(['/inventory', id]); }
}
