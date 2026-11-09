import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Api, AuditRow, errorText } from '../api';

const ACTION_LABEL: Record<string, string> = {
  'org.created': 'Created the organization', 'policy.updated': 'Changed policy', 'slack.updated': 'Connected Slack',
  'slack.removed': 'Disconnected Slack', 'enroll_token.rotated': 'Rotated the enroll token', 'member.invited': 'Invited',
  'member.joined': 'Joined', 'member.removed': 'Removed member', 'member.role_changed': 'Changed role of',
  'invite.revoked': 'Revoked invite for', 'device.enrolled': 'Enrolled device', 'device.revoked': 'Revoked device',
  'component.approved': 'Approved', 'component.approval_revoked': 'Revoked approval of', 'component.blocked': 'Blocked',
  'component.unblocked': 'Unblocked', 'alerts.acknowledged_all': 'Marked all alerts read', 'billing.plan_changed': 'Plan changed',
};

@Component({
  selector: 'sg-audit',
  imports: [DatePipe, JsonPipe, RouterLink],
  template: `
    <div class="page">
      <div class="page-head">
        <div><h1>Audit log</h1><p class="sub">Who approved, blocked, enrolled or changed what, and when. Useful evidence for SOC 2 and vendor questionnaires.</p></div>
        @if (api.org()?.plan_info?.audit_export) {
          <a class="btn" href="/api/audit/export.csv" download>Export CSV</a>
        } @else {
          <a class="btn" routerLink="/settings" fragment="billing" title="Available on the Business plan">Export CSV (Business)</a>
        }
      </div>
      @if (error()) { <div class="error-box">{{ error() }}</div> }
      <section class="panel">
        <div class="table-wrap"><table class="ledger">
          <thead><tr><th>When</th><th>Who</th><th>Action</th><th class="hide-sm">Details</th></tr></thead>
          <tbody>
            @for (a of rows(); track a.id) {
              <tr>
                <td class="small" style="white-space:nowrap">{{ a.created_at + (a.created_at.endsWith('Z') || a.created_at.includes('+') ? '' : 'Z') | date: 'd MMM y, HH:mm' }}</td>
                <td class="small">{{ a.actor }}</td>
                <td>{{ label(a.action) }} <code class="small">{{ a.target }}</code></td>
                <td class="hide-sm faint small details">{{ hasDetails(a) ? (a.details | json) : '' }}</td>
              </tr>
            } @empty { <tr><td colspan="4" class="empty">No activity recorded yet.</td></tr> }
          </tbody>
        </table></div>
      </section>
    </div>
  `,
  styles: `.details { max-width: 360px; word-break: break-word; font-family: var(--mono); font-size: 11.5px; }`,
})
export class AuditPage implements OnInit {
  api = inject(Api);
  rows = signal<AuditRow[]>([]);
  error = signal('');
  label(a: string) { return ACTION_LABEL[a] ?? a; }
  hasDetails(a: AuditRow) { return a.details && Object.values(a.details).some(v => v !== null && v !== ''); }
  async ngOnInit() {
    try { this.rows.set(await this.api.get<AuditRow[]>('/api/audit', { limit: 500 })); } catch (e) { this.error.set(errorText(e)); }
  }
}
