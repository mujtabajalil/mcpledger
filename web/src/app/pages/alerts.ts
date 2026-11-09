import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, EventItem, errorText } from '../api';
import { AgoPipe, SevBadge } from '../shared';

const TYPE_LABEL: Record<string, string> = {
  new_component: 'New', drift: 'Changed', blocked_in_use: 'Blocked install', device_enrolled: 'Device',
};

@Component({
  selector: 'sg-alerts',
  imports: [RouterLink, AgoPipe, SevBadge],
  template: `
    <div class="page">
      <div class="page-head">
        <div><h1>Alerts</h1><p class="sub">New components, changes after approval, and blocked items showing up on a machine.
          @if (!api.org()?.slack_configured) { <a routerLink="/settings" fragment="alerts">Send these to Slack</a> }</p></div>
        <div class="row">
          <div class="segmented"><button [class.on]="!showAll()" (click)="showAll.set(false)">Open</button><button [class.on]="showAll()" (click)="showAll.set(true)">All</button></div>
          @if (openCount() > 0) { <button class="btn" (click)="ackAll()">Mark all as read</button> }
        </div>
      </div>
      @if (error()) { <div class="error-box">{{ error() }}</div> }
      <section class="panel">
        @if (visible().length === 0) {
          <div class="empty"><h3>{{ showAll() ? 'No alerts yet' : 'All caught up' }}</h3><p>Alerts appear when a scan finds something new or changed.</p></div>
        } @else {
          <ul class="alerts">
            @for (e of visible(); track e.id) {
              <li [class.read]="e.acknowledged">
                <sg-sev [value]="e.severity" />
                <div class="main">
                  <div class="row"><span class="type">{{ typeLabel(e.type) }}</span>
                    @if (e.component_id) { <a [routerLink]="['/inventory', e.component_id]"><strong>{{ e.title }}</strong></a> } @else { <strong>{{ e.title }}</strong> }</div>
                  <p class="muted small">{{ e.detail }}</p>
                </div>
                <div class="meta faint small">{{ e.created_at | ago }}
                  @if (!e.acknowledged) { <button class="btn small ghost" (click)="ack(e)">Mark read</button> }</div>
              </li>
            }
          </ul>
        }
      </section>
    </div>
  `,
  styles: `
    .alerts { list-style: none; margin: 0; padding: 0; }
    .alerts li { display: grid; grid-template-columns: 90px 1fr auto; gap: 14px; padding: 14px 20px; border-bottom: 1px solid var(--rule); align-items: start; }
    .alerts li:last-child { border-bottom: 0; }
    .alerts li.read { opacity: .6; }
    .main p { margin-top: 3px; max-width: 80ch; }
    .type { font-size: 12px; font-weight: 600; color: var(--ink-soft); background: #e8ebe6; padding: 1px 7px; border-radius: var(--r-sm); }
    .meta { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; white-space: nowrap; }
    @media (max-width: 760px) { .alerts li { grid-template-columns: 1fr; } .meta { align-items: flex-start; } }
  `,
})
export class AlertsPage implements OnInit {
  api = inject(Api);
  events = signal<EventItem[]>([]);
  showAll = signal(false);
  error = signal('');
  visible = computed(() => this.showAll() ? this.events() : this.events().filter(e => !e.acknowledged));
  openCount = computed(() => this.events().filter(e => !e.acknowledged).length);

  typeLabel(t: string) { return TYPE_LABEL[t] ?? t; }
  async ngOnInit() { await this.load(); }
  async load() {
    try { this.events.set(await this.api.get<EventItem[]>('/api/events', { limit: 300 })); } catch (e) { this.error.set(errorText(e)); }
  }
  async ack(e: EventItem) { await this.api.post(`/api/events/${e.id}/ack`); e.acknowledged = true; this.events.set([...this.events()]); }
  async ackAll() { await this.api.post('/api/events/ack-all'); this.api.notify('All alerts marked as read'); await this.load(); }
}
