import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api, ComponentRow, errorText } from '../api';
import { AgoPipe, ClientPipe, SevBadge, StatusBadge } from '../shared';

type StatusFilter = '' | 'pending' | 'drift' | 'approved' | 'blocked';

@Component({
  selector: 'sg-inventory',
  imports: [FormsModule, RouterLink, AgoPipe, ClientPipe, SevBadge, StatusBadge],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Inventory</h1>
          <p class="sub">Every MCP server and skill reported by your team's machines. Approving pins the exact version you reviewed.</p>
        </div>
      </div>

      <div class="filters">
        <div class="segmented" role="group" aria-label="Status">
          @for (s of statuses; track s.v) {
            <button [class.on]="status() === s.v" (click)="setStatus(s.v)">{{ s.label }}
              <span class="n">{{ countFor(s.v) }}</span></button>
          }
        </div>
        <div class="segmented" role="group" aria-label="Kind">
          <button [class.on]="kind() === ''" (click)="kind.set('')">All</button>
          <button [class.on]="kind() === 'mcp_server'" (click)="kind.set('mcp_server')">MCP servers</button>
          <button [class.on]="kind() === 'skill'" (click)="kind.set('skill')">Skills</button>
        </div>
        <input type="search" placeholder="Search name or package" [ngModel]="q()" (ngModelChange)="q.set($event)" aria-label="Search">
      </div>

      @if (error()) { <div class="error-box">{{ error() }}</div> }
      <section class="panel">
        @if (!loaded()) { <p class="empty">Loading…</p> }
        @else if (visible().length === 0) {
          <div class="empty">
            @if (rows().length === 0) {
              <h3>Nothing reported yet</h3><p>Run <code>mcpledger scan</code> on an enrolled machine. <a routerLink="/settings">Get the enroll command</a></p>
            } @else { <h3>No matches</h3><p>Try a different filter.</p> }
          </div>
        } @else {
          <div class="table-wrap"><table class="ledger">
            <thead><tr>
              <th>Component</th><th>Status</th><th>Risk</th><th class="num">Machines</th><th class="hide-sm">Used in</th><th class="hide-sm">Last seen</th>
            </tr></thead>
            <tbody>
              @for (c of visible(); track c.id) {
                <tr class="clickable" (click)="open(c.id)">
                  <td>
                    <a [routerLink]="['/inventory', c.id]" (click)="$event.stopPropagation()"><strong>{{ c.name }}</strong></a>
                    <div class="faint small">{{ c.kind === 'skill' ? 'Skill' : 'MCP server' }}
                      @if (c.kind === 'mcp_server') { · {{ c.introspected ? c.tool_count + (c.tool_count === 1 ? ' tool' : ' tools') : 'tools not recorded' }} }
                      @if (c.versions > 1) { · {{ c.versions }} versions seen }</div>
                  </td>
                  <td><sg-status [value]="c.status" /></td>
                  <td><sg-sev [value]="c.max_severity" /></td>
                  <td class="num">{{ c.devices }}</td>
                  <td class="hide-sm">@for (cl of c.clients; track cl) { <span class="tag">{{ cl | client }}</span> }</td>
                  <td class="hide-sm faint small">{{ c.last_seen_at | ago }}</td>
                </tr>
              }
            </tbody>
          </table></div>
        }
      </section>
    </div>
  `,
  styles: `
    .filters { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
    .filters input { max-width: 280px; }
    .n { font-weight: 500; opacity: .7; margin-left: 4px; }
  `,
})
export class InventoryPage implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  rows = signal<ComponentRow[]>([]);
  loaded = signal(false);
  error = signal('');
  status = signal<StatusFilter>('');
  kind = signal<'' | 'mcp_server' | 'skill'>('');
  q = signal('');
  statuses: { v: StatusFilter; label: string }[] = [
    { v: '', label: 'All' }, { v: 'pending', label: 'Needs review' }, { v: 'drift', label: 'Changed' },
    { v: 'approved', label: 'Approved' }, { v: 'blocked', label: 'Blocked' },
  ];

  visible = computed(() => {
    const q = this.q().trim().toLowerCase();
    return this.rows().filter(r =>
      (!this.status() || r.status === this.status()) &&
      (!this.kind() || r.kind === this.kind()) &&
      (!q || r.name.toLowerCase().includes(q) || r.identity.toLowerCase().includes(q) ||
        r.local_names.some(n => n.toLowerCase().includes(q))));
  });

  countFor(s: StatusFilter) {
    return this.rows().filter(r => (!s || r.status === s) && (!this.kind() || r.kind === this.kind())).length;
  }

  async ngOnInit() {
    const s = this.route.snapshot.queryParamMap.get('status') as StatusFilter | null;
    if (s) this.status.set(s);
    try { this.rows.set(await this.api.get<ComponentRow[]>('/api/components')); }
    catch (e) { this.error.set(errorText(e)); }
    finally { this.loaded.set(true); }
  }

  setStatus(s: StatusFilter) {
    this.status.set(s);
    this.router.navigate([], { queryParams: { status: s || null }, replaceUrl: true });
  }

  open(id: string) { this.router.navigate(['/inventory', id]); }
}
