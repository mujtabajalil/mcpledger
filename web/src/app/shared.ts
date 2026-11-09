import { Component, Pipe, PipeTransform, computed, input } from '@angular/core';
import { Severity, Status } from './api';

/** "3 min ago" style relative time; falls back to a date for anything older than a week. */
@Pipe({ name: 'ago' })
export class AgoPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    if (!value) return 'never';
    const t = new Date(value.endsWith('Z') || value.includes('+') ? value : value + 'Z').getTime();
    const s = Math.max(0, (Date.now() - t) / 1000);
    if (s < 60) return 'just now';
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    if (s < 7 * 86400) return `${Math.floor(s / 86400)} d ago`;
    return new Date(t).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  }
}

const STATUS_LABEL: Record<Status, string> = {
  pending: 'Needs review', approved: 'Approved', drift: 'Changed', blocked: 'Blocked',
};

@Component({
  selector: 'sg-status',
  template: `<span class="status {{ value() }}">{{ label() }}</span>`,
})
export class StatusBadge {
  value = input.required<Status>();
  label = computed(() => STATUS_LABEL[this.value()]);
}

@Component({
  selector: 'sg-sev',
  template: `<span class="sev {{ value() || 'none' }}">{{ value() || 'clean' }}</span>`,
})
export class SevBadge {
  value = input<Severity | null>(null);
}

/**
 * A hash drawn as 16 coloured segments. Two strips that look the same are the same
 * fingerprint; any change in tools or config produces a visibly different strip.
 */
@Component({
  selector: 'sg-print',
  template: `
    <span class="print" [class.compact]="compact()" [attr.title]="hash()" role="img" [attr.aria-label]="'Fingerprint ' + short()">
      @for (c of colours(); track $index) { <i [style.background]="c"></i> }
      @if (!compact()) { <code>{{ short() }}</code> }
    </span>`,
  styles: `
    .print { display: inline-flex; align-items: center; gap: 1px; }
    .print i { width: 7px; height: 18px; border-radius: 1px; display: inline-block; }
    .print.compact i { width: 4px; height: 12px; }
    .print code { margin-left: 8px; color: var(--ink-soft); font-size: 12px; }
  `,
})
export class Fingerprint {
  hash = input.required<string>();
  compact = input(false);
  short = computed(() => this.hash().slice(0, 12));
  colours = computed(() => {
    const h = this.hash().padEnd(64, '0');
    const out: string[] = [];
    for (let i = 0; i < 16; i++) {
      const n = parseInt(h.slice(i * 4, i * 4 + 4), 16);
      const hue = Math.round((n / 65535) * 360);
      const light = 34 + ((n >> 3) % 4) * 9;
      out.push(`hsl(${hue} 46% ${light}%)`);
    }
    return out;
  });
}

export const CLIENT_LABEL: Record<string, string> = {
  'claude-code': 'Claude Code', 'claude-desktop': 'Claude Desktop', 'claude-plugin': 'Claude plugin', cursor: 'Cursor',
  vscode: 'VS Code', windsurf: 'Windsurf', codex: 'Codex', 'gemini-cli': 'Gemini CLI', cline: 'Cline',
  'roo-code': 'Roo Code', zed: 'Zed', 'amazon-q': 'Amazon Q', agents: 'Agent skills',
};

@Pipe({ name: 'client' })
export class ClientPipe implements PipeTransform {
  transform(v: string): string { return CLIENT_LABEL[v] ?? v; }
}

/** Minimal line diff (LCS) for comparing tool descriptions and skill files. */
export interface DiffLine { kind: 'same' | 'add' | 'del'; text: string }
export function lineDiff(a: string, b: string): DiffLine[] {
  const A = a.split('\n'), B = b.split('\n');
  if (A.length * B.length > 250_000) {
    return [...A.map(t => ({ kind: 'del' as const, text: t })), ...B.map(t => ({ kind: 'add' as const, text: t }))];
  }
  const dp: number[][] = Array.from({ length: A.length + 1 }, () => new Array(B.length + 1).fill(0));
  for (let i = A.length - 1; i >= 0; i--)
    for (let j = B.length - 1; j >= 0; j--)
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: DiffLine[] = [];
  let i = 0, j = 0;
  while (i < A.length && j < B.length) {
    if (A[i] === B[j]) { out.push({ kind: 'same', text: A[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ kind: 'del', text: A[i++] });
    else out.push({ kind: 'add', text: B[j++] });
  }
  while (i < A.length) out.push({ kind: 'del', text: A[i++] });
  while (j < B.length) out.push({ kind: 'add', text: B[j++] });
  return out;
}

const circle = (cx: number, cy: number, r: number) => `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;

/** Line icons (Lucide-style, 24px grid) drawn as paths so they inherit currentColor. */
const ICONS: Record<string, string[]> = {
  overview: ['M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z'],
  inventory: ['m12 2 9 5-9 5-9-5z', 'm3 12 9 5 9-5', 'm3 17 9 5 9-5'],
  alerts: ['M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9', 'M10.3 21a1.94 1.94 0 0 0 3.4 0'],
  devices: ['M5 4h14a1 1 0 0 1 1 1v10H4V5a1 1 0 0 1 1-1z', 'M2 19h20'],
  audit: ['M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z', 'M14 3v5h5', 'M9 13h6', 'M9 17h6'],
  settings: ['M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z', circle(12, 12, 3)],
  docs: ['M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z', 'M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z'],
  logout: ['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4', 'm16 17 5-5-5-5', 'M21 12H9'],
  plus: ['M12 5v14', 'M5 12h14'],
  'arrow-right': ['M5 12h14', 'm12 5 7 7-7 7'],
  'arrow-up': ['M12 19V5', 'm5 12 7-7 7 7'],
  'arrow-down': ['M12 5v14', 'm19 12-7 7-7-7'],
  chart: ['M3 3v18h18', 'M8 17v-5', 'M13 17V8', 'M18 17v-3'],
  shield: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z', 'M12 8v4', 'M12 16h.01'],
  activity: ['M22 12h-4l-3 9L9 3l-3 9H2'],
  inbox: ['M22 12h-6l-2 3h-4l-2-3H2', 'M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z'],
  compare: [circle(18, 18, 3), circle(6, 6, 3), 'M13 6h3a2 2 0 0 1 2 2v7', 'M11 18H8a2 2 0 0 1-2-2V9'],
  check: [circle(12, 12, 9), 'm8.5 12 2.5 2.5 4.5-5'],
  alert: [circle(12, 12, 9), 'M12 8v4', 'M12 16h.01'],
  chevron: ['m9 18 6-6-6-6'],
  external: ['M7 17 17 7', 'M8 7h9v9'],
};

@Component({
  selector: 'sg-icon',
  template: `<svg [attr.width]="size()" [attr.height]="size()" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    [attr.stroke-width]="stroke()" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    @for (d of paths(); track $index) { <path [attr.d]="d" /> }</svg>`,
  styles: `:host { display: inline-flex; flex: none; } svg { display: block; }`,
})
export class Icon {
  name = input.required<string>();
  size = input(18);
  stroke = input(1.7);
  paths = computed(() => ICONS[this.name()] ?? []);
}

/** Two-letter monogram for a component: "@scope/server-github" -> "SG", "https://mcp.linear.app/mcp" -> "LI". */
export function monogram(name: string): string {
  let n = name.trim();
  try {
    if (/^https?:\/\//.test(n)) {
      const host = new URL(n).hostname.split('.').filter(p => !['www', 'mcp', 'api'].includes(p));
      n = host.length > 1 ? host[host.length - 2] : host[0] ?? n;
      return n.slice(0, 2).toUpperCase();
    }
  } catch { /* not a URL */ }
  const words = n.replace(/^@[^/]+\//, '').split(/[-_/.\s]+/).filter(Boolean);
  if (words.length >= 2) return (words[words.length - 2][0] + words[words.length - 1][0]).toUpperCase();
  return (words[0] ?? '?').slice(0, 2).toUpperCase();
}

@Component({
  selector: 'sg-avatar',
  template: `<span class="av" [class.skill]="kind() === 'skill'" aria-hidden="true">{{ letters() }}</span>`,
  styles: `
    .av { width: 34px; height: 34px; border-radius: 9px; display: inline-grid; place-items: center; flex: none;
      font-size: 11.5px; font-weight: 600; letter-spacing: .02em; background: #eef0fd; color: #3f48b8; border: 1px solid #e1e4fb; }
    .av.skill { background: #fdf3e3; color: #9a5208; border-color: #f8e6c6; }
  `,
})
export class Avatar {
  name = input.required<string>();
  kind = input<string>('mcp_server');
  letters = computed(() => monogram(this.name()));
}
