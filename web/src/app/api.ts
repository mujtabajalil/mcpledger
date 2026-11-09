import { HttpClient, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

export type Status = 'pending' | 'approved' | 'drift' | 'blocked';
export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';

export interface Me {
  user: { id: string; email: string; name: string };
  orgs: { id: string; name: string; role: string; plan: string }[];
}
export interface PlanInfo { label: string; price: number; max_devices: number; slack: boolean; audit_export: boolean; history_days: number }
export interface Org {
  id: string; name: string; role: 'owner' | 'admin' | 'member'; plan: string; plan_info: PlanInfo;
  subscription_status: string | null; policy_mode: 'monitor' | 'enforce'; default_action: 'warn' | 'block';
  alert_min_severity: Severity; slack_configured: boolean; device_count: number;
  enroll_token: string | null; enroll_command: string | null; server_url: string;
}
export interface Finding { rule: string; severity: Severity; title: string; detail: string; location: string; evidence?: string }
export interface EventItem {
  id: string; type: string; severity: Severity; title: string; detail: string; component_id: string | null;
  device_id: string | null; acknowledged: boolean; created_at: string; hostname?: string | null;
}
export interface ComponentRow {
  id: string; kind: 'mcp_server' | 'skill'; name: string; identity: string; status: Status; max_severity: Severity | null;
  installs: number; devices: number; clients: string[]; local_names: string[]; versions: number; introspected: boolean;
  tool_count: number; last_seen_at: string; first_seen_at: string;
}
export interface Tool { name: string; description: string; inputSchema: any; annotations?: any }
export interface Version {
  id: string; fingerprint: string; launch_hash: string; tools_hash: string | null; version_label: string;
  max_severity: Severity | null; findings: Finding[]; approved: boolean; trusted: boolean; approved_by: string | null;
  approved_at: string | null; first_seen_at: string; installs: number; snapshot: any;
}
export interface Install {
  device_id: string; hostname: string; owner: string; client: string; scope: string; location: string;
  local_name: string; version_id: string; trusted: boolean; last_seen_at: string;
}
export interface ComponentDetail {
  id: string; kind: 'mcp_server' | 'skill'; name: string; identity: string; status: Status; blocked_reason: string | null;
  notes: string | null; first_seen_at: string; last_seen_at: string; versions: Version[]; installs: Install[]; events: EventItem[];
}
export interface Overview {
  components: number; mcp_servers: number; skills: number; status_counts: Record<Status, number>; devices: number;
  stale_devices: number; installs: number; open_alerts: number; policy_mode: string;
  risky: { id: string; name: string; kind: string; status: Status; max_severity: Severity; installs: number }[];
  recent_events: EventItem[];
}
export interface Device {
  id: string; hostname: string; os: string; username: string; owner_email: string | null; cli_version: string;
  revoked: boolean; last_seen_at: string | null; created_at: string; installs: number;
}
export interface AuditRow { id: number; actor: string; action: string; target: string; details: any; ip: string | null; created_at: string }
export interface Members {
  members: { user_id: string; email: string; name: string; role: string; joined_at: string }[];
  invites: { id: string; email: string; role: string; created_at: string }[];
}

/** Turns FastAPI error bodies into one readable sentence. */
export function errorText(e: unknown): string {
  if (e instanceof HttpErrorResponse) {
    const d = e.error?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d) && d.length) {
      const first = d[0];
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
      return `${field ? field + ': ' : ''}${first.msg}`;
    }
    if (e.status === 0) return 'Cannot reach the server. Check your connection.';
    return `Request failed (${e.status}).`;
  }
  return 'Something went wrong.';
}

export const orgHeaderInterceptor: HttpInterceptorFn = (req, next) => {
  const orgId = localStorageGet('ml_org');
  return next(orgId && req.url.startsWith('/api/') ? req.clone({ setHeaders: { 'X-Org-Id': orgId } }) : req);
};

function localStorageGet(k: string): string | null {
  try { return localStorage.getItem(k); } catch { return null; }
}
function localStorageSet(k: string, v: string | null) {
  try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode */ }
}

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);
  private router = inject(Router);

  readonly me = signal<Me | null>(null);
  readonly org = signal<Org | null>(null);
  readonly isAdmin = computed(() => ['admin', 'owner'].includes(this.org()?.role ?? ''));
  readonly toast = signal<string | null>(null);
  private toastTimer: any;

  get<T>(url: string, params?: Record<string, any>) {
    const clean: Record<string, string> = {};
    for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== null && v !== '') clean[k] = String(v);
    return firstValueFrom(this.http.get<T>(url, { params: clean }));
  }
  post<T>(url: string, body: any = {}) { return firstValueFrom(this.http.post<T>(url, body)); }
  patch<T>(url: string, body: any) { return firstValueFrom(this.http.patch<T>(url, body)); }
  put<T>(url: string, body: any) { return firstValueFrom(this.http.put<T>(url, body)); }
  delete<T>(url: string) { return firstValueFrom(this.http.delete<T>(url)); }

  async loadSession(): Promise<boolean> {
    try {
      const me = await this.get<Me>('/api/auth/me');
      this.me.set(me);
      const saved = localStorageGet('ml_org');
      if (!saved || !me.orgs.some(o => o.id === saved)) localStorageSet('ml_org', me.orgs[0]?.id ?? null);
      await this.refreshOrg();
      return true;
    } catch {
      this.me.set(null);
      this.org.set(null);
      return false;
    }
  }

  async refreshOrg() { this.org.set(await this.get<Org>('/api/org')); }

  async switchOrg(id: string) {
    localStorageSet('ml_org', id);
    await this.refreshOrg();
    this.router.navigateByUrl('/overview');
  }

  async logout() {
    await this.post('/api/auth/logout').catch(() => null);
    this.me.set(null);
    this.org.set(null);
    this.router.navigateByUrl('/login');
  }

  notify(msg: string) {
    this.toast.set(msg);
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => this.toast.set(null), 2600);
  }

  async copy(text: string, what = 'Copied') {
    try { await navigator.clipboard.writeText(text); this.notify(what); } catch { this.notify('Select the text to copy it'); }
  }
}
