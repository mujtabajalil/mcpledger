import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, Device, errorText } from '../api';
import { AgoPipe } from '../shared';

@Component({
  selector: 'sg-devices',
  imports: [AgoPipe, RouterLink],
  template: `
    <div class="page">
      <div class="page-head">
        <div><h1>Devices</h1>
          <p class="sub">Machines enrolled with <code>mcpledger enroll</code>.
            @if ((api.org()?.plan_info?.max_devices ?? 0) >= 1000000) { {{ api.org()?.device_count }} enrolled, no limit on the {{ api.org()?.plan_info?.label }} edition. }
            @else { {{ api.org()?.device_count }} of {{ api.org()?.plan_info?.max_devices }} on the {{ api.org()?.plan_info?.label }} plan. }</p></div>
        <a class="btn" routerLink="/settings" fragment="enroll">Enroll a machine</a>
      </div>
      @if (error()) { <div class="error-box">{{ error() }}</div> }
      <section class="panel">
        @if (devices().length === 0) {
          <div class="empty"><h3>No machines yet</h3><p>Copy the enroll command from <a routerLink="/settings">Settings</a> and run it on a laptop.</p></div>
        } @else {
          <div class="table-wrap"><table class="ledger">
            <thead><tr><th>Machine</th><th class="hide-sm">System</th><th class="num">Installs</th><th>Last report</th><th></th></tr></thead>
            <tbody>
              @for (d of devices(); track d.id) {
                <tr [class.revoked]="d.revoked">
                  <td><strong>{{ d.hostname }}</strong><div class="faint small">{{ d.owner_email || d.username || 'unknown user' }}</div></td>
                  <td class="hide-sm small">{{ d.os }}<div class="faint">CLI {{ d.cli_version || '?' }}</div></td>
                  <td class="num">{{ d.installs }}</td>
                  <td class="small" [class.stale]="isStale(d)">{{ d.revoked ? 'Revoked' : (d.last_seen_at | ago) }}</td>
                  <td style="text-align:right">
                    @if (api.isAdmin() && !d.revoked) {
                      @if (confirm() === d.id) {
                        <button class="btn small solid-danger" (click)="revoke(d)">Revoke key</button>
                        <button class="btn small ghost" (click)="confirm.set(null)">Cancel</button>
                      } @else { <button class="btn small danger" (click)="confirm.set(d.id)">Revoke</button> }
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table></div>
        }
      </section>
      <p class="faint small" style="margin-top:12px">Revoking deletes the machine's key and its inventory, and frees a seat. The machine can enroll again later.</p>
    </div>
  `,
  styles: `tr.revoked td { opacity: .5; } .stale { color: var(--drift); font-weight: 600; }`,
})
export class DevicesPage implements OnInit {
  api = inject(Api);
  devices = signal<Device[]>([]);
  error = signal('');
  confirm = signal<string | null>(null);

  async ngOnInit() { await this.load(); }
  async load() {
    try { this.devices.set(await this.api.get<Device[]>('/api/devices')); } catch (e) { this.error.set(errorText(e)); }
  }
  isStale(d: Device) {
    return !d.revoked && (!d.last_seen_at || Date.now() - new Date(d.last_seen_at + (d.last_seen_at.includes('+') || d.last_seen_at.endsWith('Z') ? '' : 'Z')).getTime() > 7 * 86400e3);
  }
  async revoke(d: Device) {
    try { await this.api.delete(`/api/devices/${d.id}`); this.api.notify(`Revoked ${d.hostname}`); this.confirm.set(null); await this.load(); await this.api.refreshOrg(); }
    catch (e) { this.api.notify(errorText(e)); }
  }
}
