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
