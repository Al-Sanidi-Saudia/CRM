import { useCallback, useEffect, useRef, useState } from "react";
import type { GeneratedComponentProps } from "./RuntimeTypes";
import {
    Badge,
    Button,
    Dialog,
    DialogActions,
    DialogBody,
    DialogContent,
    DialogSurface,
    DialogTitle,
    MessageBar,
    MessageBarBody,
    MessageBarTitle,
    Spinner,
    Text,
    makeStyles,
    shorthands,
    tokens,
} from "@fluentui/react-components";
import {
    ArrowClockwiseRegular,
    ArrowSyncRegular,
    CheckmarkCircleFilled,
    CircleRegular,
    ClockRegular,
    DismissCircleFilled,
    ErrorCircleRegular,
} from "@fluentui/react-icons";

// Security roles that may start a sync. Add role names here to give more roles the buttons.
// The Integration Sync Request table's create privilege must be granted to the same roles.
const SYNC_ROLES = ["System Administrator"];

const SYNC_TYPE_DATA = 100000000;
const SYNC_TYPE_INSIGHTS = 100000001;
const REQ_REQUESTED = 100000000;
const REQ_RUNNING = 100000001;
const REQ_SUCCEEDED = 100000002;
const REQ_FAILED = 100000003;

// The dispatcher flow picks a request up within seconds. One still waiting after this long was never
// picked up (for example the flow was off), so it must not keep the button disabled.
const NOT_STARTED_AFTER_MS = 15 * 60 * 1000;

// While a sync is running, check its request this often and refresh the page once it finishes.
const POLL_MS = 5000;
// After a data sync finishes, run history can take a few minutes to show its runs: check this often,
// for up to this long, then refresh once more.
const CATCH_UP_POLL_MS = 15000;
const CATCH_UP_MAX_MS = 10 * 60 * 1000;
// A flow run counts as part of a sync if it started no earlier than this before the sync's start time.
const RUN_MATCH_SLACK_MS = 60 * 1000;

const CACHE_KEY = "__ppSyncControl_dataCache";
const INFLIGHT_KEY = "__ppSyncControl_dataInflight";

type Kind = "succeeded" | "failed" | "running" | "cancelled" | "none";
type SyncKind = "data" | "insights";

interface FlowRef { name: string; id: string; }

interface Platform {
    id: string;
    name: string;
    key: string;
    configured: boolean;
    // False while the platform's connection isn't working yet: the card shows a notice and no sync can start.
    connectionActive: boolean;
    dataFlows: FlowRef[];
    insightsFlowName: string;
    insightsFlowId: string;
}

interface RunInfo { kind: Kind; start: Date | null; error: string | null; }

interface RequestInfo {
    id: string;
    platformId: string;
    type: SyncKind;
    status: number;
    startedOn: Date | null;
    completedOn: Date | null;
    error: string | null;
}

interface Snapshot {
    platforms: Platform[];
    runs: Record<string, RunInfo | null>;
    // Start of the latest successful run of each flow a button starts (campaigns and insights flows).
    lastSuccess: Record<string, Date | null>;
    // Median duration in minutes of the last successful runs of the same flows.
    usualMinutes: Record<string, number | null>;
    requests: RequestInfo[];
    loadedAt: Date;
}

type AgeLevel = "ok" | "warn" | "late";
interface AgeView { text: string; level: AgeLevel; }

type StepKind = Kind | "updating";
interface StepView { name: string; kind: StepKind; time: string; }

interface SectionView {
    kind: Kind;
    lastRun: string;
    steps: StepView[];
    failedName: string | null;
    error: string | null;
    active: boolean;
    startedAt?: string;
    // Flows of a finished sync that run history doesn't show yet.
    catchingUp?: boolean;
    waitingFlowIds?: string[];
    waitingSince?: Date;
    waitingUntil?: Date;
}

interface PendingSync { platform: Platform; type: SyncKind; }

const useStyles = makeStyles({
    root: {
        position: "relative",
        contain: "layout",
        height: "100%",
        overflowY: "auto",
        boxSizing: "border-box",
        backgroundColor: tokens.colorNeutralBackground2,
        color: tokens.colorNeutralForeground1,
        paddingTop: tokens.spacingVerticalXL,
        paddingBottom: tokens.spacingVerticalXXL,
        paddingLeft: tokens.spacingHorizontalXXL,
        paddingRight: tokens.spacingHorizontalXXL,
        display: "flex",
        flexDirection: "column",
        rowGap: tokens.spacingVerticalL,
        "@media (max-width: 600px)": {
            paddingLeft: tokens.spacingHorizontalL,
            paddingRight: tokens.spacingHorizontalL,
        },
    },
    header: {
        display: "flex",
        flexWrap: "wrap",
        alignItems: "flex-end",
        justifyContent: "space-between",
        columnGap: tokens.spacingHorizontalL,
        rowGap: tokens.spacingVerticalS,
    },
    titleBlock: { display: "flex", flexDirection: "column", rowGap: tokens.spacingVerticalXXS },
    subtitle: { color: tokens.colorNeutralForeground2 },
    headerActions: { display: "flex", alignItems: "center", columnGap: tokens.spacingHorizontalM },
    updated: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200 },
    grid: {
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
        gap: tokens.spacingHorizontalL,
        alignItems: "start",
    },
    card: {
        backgroundColor: tokens.colorNeutralBackground1,
        ...shorthands.border("1px", "solid", tokens.colorNeutralStroke2),
        borderRadius: tokens.borderRadiusLarge,
        boxShadow: tokens.shadow2,
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
    },
    cardHeader: {
        display: "flex",
        alignItems: "center",
        columnGap: tokens.spacingHorizontalM,
        paddingTop: tokens.spacingVerticalM,
        paddingBottom: tokens.spacingVerticalM,
        paddingLeft: tokens.spacingHorizontalXL,
        paddingRight: tokens.spacingHorizontalXL,
        borderBottomWidth: "1px",
        borderBottomStyle: "solid",
        borderBottomColor: tokens.colorNeutralStroke3,
    },
    mark: {
        width: "32px",
        height: "32px",
        borderRadius: tokens.borderRadiusMedium,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: tokens.fontWeightBold,
        flexShrink: 0,
    },
    section: {
        display: "flex",
        flexDirection: "column",
        rowGap: tokens.spacingVerticalS,
        paddingTop: tokens.spacingVerticalL,
        paddingBottom: tokens.spacingVerticalL,
        paddingLeft: tokens.spacingHorizontalXL,
        paddingRight: tokens.spacingHorizontalXL,
    },
    sectionDivider: {
        borderBottomWidth: "1px",
        borderBottomStyle: "solid",
        borderBottomColor: tokens.colorNeutralStroke3,
    },
    sectionHead: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        columnGap: tokens.spacingHorizontalS,
    },
    muted: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200 },
    inlineIcon: { verticalAlign: "middle" },
    runningNote: {
        paddingTop: tokens.spacingVerticalS,
        paddingBottom: tokens.spacingVerticalS,
        paddingLeft: tokens.spacingHorizontalM,
        paddingRight: tokens.spacingHorizontalM,
        borderRadius: tokens.borderRadiusMedium,
        backgroundColor: tokens.colorBrandBackground2,
        color: tokens.colorBrandForeground2,
        fontSize: tokens.fontSizeBase200,
    },
    lastRunRow: { display: "flex", flexWrap: "wrap", alignItems: "center", columnGap: tokens.spacingHorizontalS, rowGap: tokens.spacingVerticalXXS },
    age: {
        display: "inline-flex",
        alignItems: "center",
        columnGap: tokens.spacingHorizontalXXS,
        paddingTop: "1px",
        paddingBottom: "1px",
        paddingLeft: tokens.spacingHorizontalS,
        paddingRight: tokens.spacingHorizontalS,
        borderRadius: tokens.borderRadiusCircular,
        borderTopWidth: "1px",
        borderRightWidth: "1px",
        borderBottomWidth: "1px",
        borderLeftWidth: "1px",
        borderTopStyle: "solid",
        borderRightStyle: "solid",
        borderBottomStyle: "solid",
        borderLeftStyle: "solid",
        fontSize: tokens.fontSizeBase200,
        fontWeight: tokens.fontWeightSemibold,
        whiteSpace: "nowrap",
    },
    legend: {
        display: "flex",
        flexWrap: "wrap",
        columnGap: tokens.spacingHorizontalL,
        rowGap: tokens.spacingVerticalXS,
        color: tokens.colorNeutralForeground3,
        fontSize: tokens.fontSizeBase200,
    },
    legendItem: { display: "inline-flex", alignItems: "center", columnGap: tokens.spacingHorizontalXS },
    legendSwatch: {
        width: "10px",
        height: "10px",
        borderRadius: tokens.borderRadiusCircular,
        borderTopWidth: "1px",
        borderRightWidth: "1px",
        borderBottomWidth: "1px",
        borderLeftWidth: "1px",
        borderTopStyle: "solid",
        borderRightStyle: "solid",
        borderBottomStyle: "solid",
        borderLeftStyle: "solid",
    },
    steps: {
        listStyleType: "none",
        marginTop: 0,
        marginBottom: 0,
        paddingTop: tokens.spacingVerticalS,
        paddingBottom: tokens.spacingVerticalS,
        paddingLeft: tokens.spacingHorizontalM,
        paddingRight: tokens.spacingHorizontalM,
        backgroundColor: tokens.colorNeutralBackground3,
        borderRadius: tokens.borderRadiusMedium,
        display: "flex",
        flexDirection: "column",
        rowGap: tokens.spacingVerticalXS,
    },
    step: {
        display: "flex",
        alignItems: "center",
        columnGap: tokens.spacingHorizontalS,
        fontSize: tokens.fontSizeBase200,
    },
    stepName: { flexGrow: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
    stepTime: { color: tokens.colorNeutralForeground3, whiteSpace: "nowrap" },
    errorBox: {
        display: "flex",
        columnGap: tokens.spacingHorizontalS,
        paddingTop: tokens.spacingVerticalS,
        paddingBottom: tokens.spacingVerticalS,
        paddingLeft: tokens.spacingHorizontalM,
        paddingRight: tokens.spacingHorizontalM,
        borderRadius: tokens.borderRadiusMedium,
        backgroundColor: tokens.colorStatusDangerBackground1,
        color: tokens.colorStatusDangerForeground1,
        fontSize: tokens.fontSizeBase200,
        wordBreak: "break-word",
    },
    errorIcon: { flexShrink: 0, marginTop: "2px" },
    notSetUp: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        rowGap: tokens.spacingVerticalXS,
        textAlign: "center",
        paddingTop: tokens.spacingVerticalXXL,
        paddingBottom: tokens.spacingVerticalXXL,
        paddingLeft: tokens.spacingHorizontalXL,
        paddingRight: tokens.spacingHorizontalXL,
        color: tokens.colorNeutralForeground3,
    },
    center: { display: "flex", justifyContent: "center", paddingTop: tokens.spacingVerticalXXXL },
});

const MARKS: Record<string, { letter: string; bg: string; fg: string }> = {
    meta: { letter: "M", bg: "#0866FF", fg: "#FFFFFF" },
    snap: { letter: "S", bg: "#FFFC00", fg: "#1A1A1A" },
    google: { letter: "G", bg: "#1A73E8", fg: "#FFFFFF" },
    tiktok: { letter: "T", bg: "#1A1A1A", fg: "#FFFFFF" },
};

function toDate(v: unknown): Date | null {
    if (v instanceof Date) return isNaN(v.getTime()) ? null : v;
    if (typeof v === "string" && v) {
        const d = new Date(v);
        return isNaN(d.getTime()) ? null : d;
    }
    return null;
}

function formatDateTime(d: Date | null): string {
    if (!d) return "Never";
    return d.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatShort(d: Date | null): string {
    if (!d) return "";
    return d.toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function flowStatusKind(status: unknown): Kind {
    switch (String(status || "").toLowerCase()) {
        case "succeeded": return "succeeded";
        case "failed": return "failed";
        case "running":
        case "waiting": return "running";
        case "cancelled": return "cancelled";
        default: return "none";
    }
}

// flowrun.errormessage is usually a JSON object with code and message.
function readFlowError(raw: unknown): string | null {
    if (typeof raw !== "string" || !raw.trim()) return null;
    try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.message === "string") return parsed.message;
    } catch {
        // Not JSON: show as is.
    }
    return raw;
}

// A lookup can come back as a bare id or as "/table(id)": keep only the id.
function readGuid(raw: unknown): string {
    const m = String(raw ?? "").match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    return m ? m[0].toLowerCase() : "";
}

function parseFlows(raw: unknown): FlowRef[] {
    if (typeof raw !== "string" || !raw.trim()) return [];
    try {
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed
            .filter((f) => f && typeof f.id === "string" && typeof f.name === "string")
            .map((f) => ({ id: f.id.toLowerCase(), name: f.name }));
    } catch {
        return [];
    }
}

function canCurrentUserSync(): boolean {
    try {
        const ctx = (window as any).Xrm?.Utility?.getGlobalContext?.();
        const roles = ctx?.userSettings?.roles;
        const list: Array<{ name?: string }> = typeof roles?.get === "function" ? roles.get() : [];
        return list.some((r) => !!r?.name && SYNC_ROLES.includes(r.name));
    } catch {
        return false;
    }
}

async function loadSnapshot(dataApi: GeneratedComponentProps["dataApi"]): Promise<Snapshot> {
    const platformResult = await dataApi.queryTable("sanidi_integrationplatform", {
        select: ["sanidi_name", "sanidi_platformkey", "sanidi_sortorder", "sanidi_isconfigured",
            "sanidi_connectionactive", "sanidi_dataflows", "sanidi_insightsflowname", "sanidi_insightsflowid"],
        filter: "statecode eq 0",
        orderBy: "sanidi_sortorder asc",
        pageSize: 50,
    });
    const platforms: Platform[] = platformResult.rows.map((r: any) => ({
        id: String(r.sanidi_integrationplatformid),
        name: String(r.sanidi_name || ""),
        key: String(r.sanidi_platformkey || "").toLowerCase(),
        configured: r.sanidi_isconfigured === true || r.sanidi_isconfigured === 1,
        // Empty counts as active, so only a platform explicitly set to No shows the notice.
        connectionActive: r.sanidi_connectionactive !== false && r.sanidi_connectionactive !== 0,
        dataFlows: parseFlows(r.sanidi_dataflows),
        insightsFlowName: String(r.sanidi_insightsflowname || ""),
        insightsFlowId: String(r.sanidi_insightsflowid || "").toLowerCase(),
    }));

    const flowIds = new Set<string>();
    platforms.filter((p) => p.configured).forEach((p) => {
        p.dataFlows.forEach((f) => flowIds.add(f.id));
        if (p.insightsFlowId) flowIds.add(p.insightsFlowId);
    });

    const runEntries = await Promise.all(Array.from(flowIds).map(async (id) => {
        try {
            const res = await dataApi.queryTable("flowrun", {
                select: ["status", "starttime", "errormessage"],
                filter: `_workflow_value eq ${id}`,
                orderBy: "starttime desc",
                pageSize: 1,
            });
            const row: any = res.rows[0];
            const info: RunInfo | null = row
                ? { kind: flowStatusKind(row.status), start: toDate(row.starttime), error: readFlowError(row.errormessage) }
                : null;
            return [id, info] as const;
        } catch {
            return [id, null] as const;
        }
    }));
    const runs: Record<string, RunInfo | null> = {};
    runEntries.forEach(([id, info]) => { runs[id] = info; });

    // Flows a button starts: the first data flow and the insights flow of each platform.
    const leadIds = new Set<string>();
    platforms.filter((p) => p.configured).forEach((p) => {
        if (p.dataFlows[0]) leadIds.add(p.dataFlows[0].id);
        if (p.insightsFlowId) leadIds.add(p.insightsFlowId);
    });
    const successEntries = await Promise.all(Array.from(leadIds).map(async (id) => {
        try {
            const res = await dataApi.queryTable("flowrun", {
                select: ["starttime", "endtime", "duration"],
                filter: `_workflow_value eq ${id} and status eq 'Succeeded'`,
                orderBy: "starttime desc",
                pageSize: 5,
            });
            const rows: any[] = res.rows.slice(0, 5);
            const durations = rows
                .map((r) => {
                    const ms = Number(r.duration);
                    if (Number.isFinite(ms) && ms > 0) return ms;
                    const a = toDate(r.starttime);
                    const b = toDate(r.endtime);
                    return a && b ? b.getTime() - a.getTime() : NaN;
                })
                .filter((ms) => Number.isFinite(ms) && ms > 0)
                .sort((a, b) => a - b);
            const median = durations.length ? durations[Math.floor((durations.length - 1) / 2)] : null;
            const usual = median === null ? null : Math.max(1, Math.round(median / 60000));
            return [id, rows[0] ? toDate(rows[0].starttime) : null, usual] as const;
        } catch {
            return [id, null, null] as const;
        }
    }));
    const lastSuccess: Record<string, Date | null> = {};
    const usualMinutes: Record<string, number | null> = {};
    successEntries.forEach(([id, d, u]) => { lastSuccess[id] = d; usualMinutes[id] = u; });

    const requestResult = await dataApi.queryTable("sanidi_integrationsyncrequest", {
        select: ["sanidi_status", "sanidi_synctype", "_sanidi_platform_value", "sanidi_startedon", "sanidi_completedon", "sanidi_errormessage"],
        filter: "statecode eq 0",
        orderBy: "sanidi_startedon desc",
        pageSize: 100,
    });
    const requests: RequestInfo[] = requestResult.rows.map((r: any) => ({
        id: readGuid(r.sanidi_integrationsyncrequestid),
        platformId: readGuid(r._sanidi_platform_value),
        type: Number(r.sanidi_synctype) === SYNC_TYPE_INSIGHTS ? "insights" : "data",
        status: Number(r.sanidi_status),
        startedOn: toDate(r.sanidi_startedon),
        completedOn: toDate(r.sanidi_completedon),
        error: typeof r.sanidi_errormessage === "string" ? r.sanidi_errormessage : null,
    }));

    return { platforms, runs, lastSuccess, usualMinutes, requests, loadedAt: new Date() };
}

function isNotStarted(req: RequestInfo | undefined): boolean {
    return !!req && req.status === REQ_REQUESTED
        && (!req.startedOn || Date.now() - req.startedOn.getTime() > NOT_STARTED_AFTER_MS);
}

function isActive(req: RequestInfo | undefined): boolean {
    if (!req || isNotStarted(req)) return false;
    return req.status === REQ_REQUESTED || req.status === REQ_RUNNING;
}

const NOT_STARTED_MESSAGE = "The sync didn't start. Check that the Sync Control - Run Sync Request flow is on, then try again.";

// A finished request that is newer than the run history decides the status: run history can take
// several minutes to show a run.
function requestOutcome(req: RequestInfo | undefined, runStart: Date | null): { kind: Kind; error: string | null } | null {
    if (!req?.startedOn) return null;
    if (runStart && req.startedOn.getTime() <= runStart.getTime()) return null;
    if (isNotStarted(req)) return { kind: "failed", error: NOT_STARTED_MESSAGE };
    if (req.status === REQ_FAILED) return { kind: "failed", error: req.error };
    if (req.status === REQ_SUCCEEDED) return { kind: "succeeded", error: null };
    return null;
}

// Time since the last successful run, measured when the page loaded (it doesn't tick).
function lastSuccessAge(p: Platform, snap: Snapshot, type: SyncKind): AgeView {
    const flowId = type === "data" ? p.dataFlows[0]?.id : p.insightsFlowId;
    let last = flowId ? snap.lastSuccess[flowId] ?? null : null;
    snap.requests
        .filter((r) => r.platformId === p.id.toLowerCase() && r.type === type && r.status === REQ_SUCCEEDED)
        .forEach((r) => { last = newer(last, r.completedOn ?? r.startedOn); });
    if (!last) return { text: "No successful run yet", level: "late" };
    const hours = Math.max(0, (snap.loadedAt.getTime() - last.getTime()) / 3600000);
    let text: string;
    if (hours < 1) text = "Less than an hour ago";
    else if (hours < 24) { const h = Math.round(hours); text = `${h} ${h === 1 ? "hour" : "hours"} ago`; }
    else { const d = Math.round(hours / 24); text = `${d} ${d === 1 ? "day" : "days"} ago`; }
    return { text, level: hours > 24 ? "late" : hours > 12 ? "warn" : "ok" };
}

function usualText(minutes: number | null | undefined, sentence: boolean): string {
    if (!minutes) return "";
    const unit = minutes === 1 ? "minute" : "minutes";
    return sentence ? `It usually takes about ${minutes} ${unit}.` : `Usually takes about ${minutes} ${unit}`;
}

function usualMinutesFor(p: Platform, snap: Snapshot, type: SyncKind): number | null {
    const flowId = type === "data" ? p.dataFlows[0]?.id : p.insightsFlowId;
    return flowId ? snap.usualMinutes?.[flowId] ?? null : null;
}

function formatTime(d: Date | null): string {
    if (!d) return "";
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// Data syncs that finished but whose later flows aren't in run history yet.
function catchUpTargets(snap: Snapshot | null): { flowIds: string[]; since: Date; until: Date }[] {
    if (!snap) return [];
    return snap.platforms
        .filter((p) => p.configured)
        .map((p) => buildDataSection(p, snap))
        .filter((v) => v.catchingUp && v.waitingFlowIds && v.waitingSince && v.waitingUntil)
        .map((v) => ({ flowIds: v.waitingFlowIds as string[], since: v.waitingSince as Date, until: v.waitingUntil as Date }));
}

// Ids of the requests still running (or just requested), the ones the page waits on.
function activeRequestIds(snap: Snapshot | null): string[] {
    if (!snap) return [];
    const ids = new Set<string>();
    snap.platforms.filter((p) => p.configured).forEach((p) => {
        (["data", "insights"] as SyncKind[]).forEach((t) => {
            const req = latestRequest(snap.requests, p.id, t);
            if (req && req.id && isActive(req)) ids.add(req.id);
        });
    });
    return Array.from(ids).sort();
}

const AGE_COLORS: Record<AgeLevel, { bg: string; fg: string; border: string }> = {
    ok: { bg: tokens.colorNeutralBackground3, fg: tokens.colorNeutralForeground2, border: tokens.colorNeutralStroke2 },
    warn: { bg: "#FFF4CE", fg: "#7A4D00", border: "#E6C35C" },
    late: { bg: "#FDE7E9", fg: "#A4262C", border: "#EEACB2" },
};

function AgeBadge(props: { age: AgeView }) {
    const styles = useStyles();
    const c = AGE_COLORS[props.age.level];
    return (
        <span
            className={styles.age}
            style={{ backgroundColor: c.bg, color: c.fg, borderColor: c.border }}
            title="Time since the last successful run, as of the last refresh"
        >
            <ClockRegular aria-hidden="true" />
            Last success: {props.age.text}
        </span>
    );
}

function latestRequest(requests: RequestInfo[], platformId: string, type: SyncKind): RequestInfo | undefined {
    return requests.find((r) => r.platformId === platformId.toLowerCase() && r.type === type);
}

function newer(a: Date | null, b: Date | null): Date | null {
    if (!a) return b;
    if (!b) return a;
    return a.getTime() >= b.getTime() ? a : b;
}

function buildDataSection(p: Platform, snap: Snapshot): SectionView {
    const steps = p.dataFlows.map((f) => ({ name: f.name, run: snap.runs[f.id] ?? null }));
    const req = latestRequest(snap.requests, p.id, "data");
    const firstStart = steps[0]?.run?.start ?? null;
    const lastRun = formatDateTime(newer(firstStart, req?.startedOn ?? null));
    // Once the sync request has finished, it is the source of truth for the flow the button started; the
    // flows after it show "Updating…" until run history has their runs from this sync.
    const reqDone = !!req && !!req.startedOn && !isActive(req) && !isNotStarted(req)
        && (req.status === REQ_SUCCEEDED || req.status === REQ_FAILED);
    const since = reqDone ? (req!.startedOn as Date).getTime() - RUN_MATCH_SLACK_MS : 0;
    const doneAt = reqDone ? (req!.completedOn ?? req!.startedOn as Date) : null;
    const recent = !!doneAt && snap.loadedAt.getTime() - doneAt.getTime() < CATCH_UP_MAX_MS;
    const waitingFlowIds: string[] = [];
    const stepViews: StepView[] = steps.map((s, i) => {
        const recorded = !!s.run?.start && s.run.start.getTime() >= since;
        if (reqDone && !recorded) {
            if (i === 0) {
                return { name: s.name, kind: req!.status === REQ_SUCCEEDED ? "succeeded" : "failed", time: formatShort(req!.startedOn) };
            }
            if (recent && req!.status === REQ_SUCCEEDED) {
                waitingFlowIds.push(p.dataFlows[i].id);
                return { name: s.name, kind: "updating", time: "" };
            }
        }
        return { name: s.name, kind: s.run ? s.run.kind : "none", time: s.run ? formatShort(s.run.start) : "No runs yet" };
    });
    const catchUp = waitingFlowIds.length > 0 && doneAt
        ? { catchingUp: true, waitingFlowIds, waitingSince: new Date(since), waitingUntil: new Date(doneAt.getTime() + CATCH_UP_MAX_MS) }
        : {};
    const base = { lastRun, steps: stepViews, ...catchUp };

    if (isActive(req)) {
        return { ...base, kind: "running", failedName: null, error: null, active: true, startedAt: formatTime(req?.startedOn ?? null) };
    }
    const outcome = requestOutcome(req, firstStart);
    if (outcome?.kind === "failed") {
        const failedName = isNotStarted(req) ? null : steps[0]?.name ?? null;
        return { ...base, kind: "failed", failedName, error: outcome.error, active: false };
    }
    if (outcome?.kind === "succeeded" || (reqDone && req!.status === REQ_SUCCEEDED)) {
        // The campaigns flow finished. A later flow of this same sync that run history shows as failed wins.
        const laterFailed = steps.find((st, i) => i > 0 && stepViews[i].kind === "failed"
            && !!st.run?.start && st.run.start.getTime() >= since);
        if (laterFailed) {
            return { ...base, kind: "failed", failedName: laterFailed.name, error: laterFailed.run?.error ?? null, active: false };
        }
        if (outcome?.kind === "succeeded") {
            return { ...base, kind: "succeeded", failedName: null, error: null, active: false };
        }
    }
    const failed = steps.find((s) => s.run?.kind === "failed");
    if (failed) {
        return { ...base, kind: "failed", failedName: failed.name, error: failed.run?.error ?? null, active: false };
    }
    if (steps.some((s) => s.run?.kind === "running")) {
        return { ...base, kind: "running", failedName: null, error: null, active: false };
    }
    if (steps.some((s) => s.run?.kind === "cancelled")) {
        return { ...base, kind: "cancelled", failedName: null, error: null, active: false };
    }
    if (steps.length > 0 && steps.every((s) => s.run?.kind === "succeeded")) {
        return { ...base, kind: "succeeded", failedName: null, error: null, active: false };
    }
    return { ...base, kind: steps.some((s) => s.run) ? "succeeded" : "none", failedName: null, error: null, active: false };
}

function buildInsightsSection(p: Platform, snap: Snapshot): SectionView {
    const run = snap.runs[p.insightsFlowId] ?? null;
    const req = latestRequest(snap.requests, p.id, "insights");
    const lastRun = formatDateTime(newer(run?.start ?? null, req?.startedOn ?? null));
    const base = { lastRun, steps: [] as StepView[], failedName: null };

    if (isActive(req)) return { ...base, kind: "running", error: null, active: true, startedAt: formatTime(req?.startedOn ?? null) };
    const outcome = requestOutcome(req, run?.start ?? null);
    if (outcome) return { ...base, kind: outcome.kind, error: outcome.error, active: false };
    if (run) return { ...base, kind: run.kind, error: run.kind === "failed" ? run.error : null, active: false };
    return { ...base, kind: "none", error: null, active: false };
}

function StatusBadge(props: { kind: Kind }) {
    const map: Record<Kind, { label: string; color: "success" | "danger" | "brand" | "warning" | "informative" }> = {
        succeeded: { label: "Succeeded", color: "success" },
        failed: { label: "Failed", color: "danger" },
        running: { label: "Running", color: "brand" },
        cancelled: { label: "Cancelled", color: "warning" },
        none: { label: "No runs yet", color: "informative" },
    };
    const m = map[props.kind];
    return <Badge appearance="tint" color={m.color} shape="rounded">{m.label}</Badge>;
}

function StepIcon(props: { kind: StepKind }) {
    if (props.kind === "updating") return <ArrowClockwiseRegular aria-hidden="true" style={{ color: tokens.colorNeutralForeground3 }} />;
    if (props.kind === "succeeded") return <CheckmarkCircleFilled aria-hidden="true" style={{ color: tokens.colorStatusSuccessForeground1 }} />;
    if (props.kind === "failed") return <DismissCircleFilled aria-hidden="true" style={{ color: tokens.colorStatusDangerForeground1 }} />;
    if (props.kind === "running") return <ArrowSyncRegular aria-hidden="true" style={{ color: tokens.colorBrandForeground1 }} />;
    if (props.kind === "cancelled") return <DismissCircleFilled aria-hidden="true" style={{ color: tokens.colorStatusWarningForeground1 }} />;
    return <CircleRegular aria-hidden="true" style={{ color: tokens.colorNeutralForeground3 }} />;
}

function StepLabel(props: { kind: StepKind }) {
    const labels: Record<StepKind, string> = {
        succeeded: "Succeeded", failed: "Failed", running: "Running", cancelled: "Cancelled", none: "", updating: "Updating…",
    };
    return <span>{labels[props.kind]}</span>;
}

function SyncSection(props: {
    title: string;
    view: SectionView;
    age: AgeView;
    usual: string;
    subtitle: string;
    canSync: boolean;
    busy: boolean;
    // The platform's other sync is running.
    blockedBy: string | null;
    // Set when no sync can start at all (connection not active yet).
    disabledReason: string | null;
    buttonLabel: string;
    divider: boolean;
    onSync: () => void;
}) {
    const styles = useStyles();
    const { view } = props;
    const titleId = `sec-${props.title.replace(/\s+/g, "-").toLowerCase()}-${props.subtitle.replace(/\W+/g, "")}`;
    return (
        <section aria-labelledby={titleId} className={props.divider ? `${styles.section} ${styles.sectionDivider}` : styles.section}>
            <div className={styles.sectionHead}>
                <Text id={titleId} weight="semibold">{props.title}</Text>
                <StatusBadge kind={view.kind} />
            </div>
            <div className={styles.lastRunRow}>
                <Text className={styles.muted}>Last run {view.lastRun}{props.subtitle ? ` · ${props.subtitle}` : ""}</Text>
                <AgeBadge age={props.age} />
            </div>
            {props.usual && (
                <Text className={styles.muted}>
                    <ClockRegular aria-hidden="true" className={styles.inlineIcon} /> {props.usual}
                </Text>
            )}
            {view.active && (
                <div className={styles.runningNote} role="status">
                    {view.startedAt ? `Started at ${view.startedAt}. ` : ""}This page updates itself when it finishes.
                </div>
            )}
            {view.steps.length > 0 && (
                <ul className={styles.steps} aria-label={`${props.title} flows`}>
                    {view.steps.map((s) => (
                        <li key={s.name} className={styles.step}>
                            <StepIcon kind={s.kind} />
                            <span className={styles.stepName} title={s.name}>{s.name}</span>
                            <StepLabel kind={s.kind} />
                            <span className={styles.stepTime}>{s.time}</span>
                        </li>
                    ))}
                </ul>
            )}
            {view.catchingUp && (
                <Text className={styles.muted} role="status">
                    <ArrowClockwiseRegular aria-hidden="true" className={styles.inlineIcon} /> The latest runs can take a few minutes to appear in run history. This page checks again automatically.
                </Text>
            )}
            {view.kind === "failed" && (
                <div className={styles.errorBox} role="alert">
                    <ErrorCircleRegular className={styles.errorIcon} aria-hidden="true" />
                    <span>
                        <strong>{view.failedName ? `${view.failedName} failed.` : "The last run failed."}</strong>{" "}
                        {view.error || "No error message was recorded. Check the flow's run history in Power Automate."}
                    </span>
                </div>
            )}
            {props.canSync && (
                <Button
                    appearance="primary"
                    icon={<ArrowSyncRegular />}
                    disabled={view.active || props.busy || !!props.blockedBy || !!props.disabledReason}
                    title={props.disabledReason
                        ?? (!view.active && props.blockedBy ? `Waiting for the ${props.blockedBy} sync to finish` : undefined)}
                    onClick={props.onSync}
                >
                    {view.active ? "Running…" : props.buttonLabel}
                </Button>
            )}
        </section>
    );
}

function PlatformCard(props: {
    platform: Platform;
    snap: Snapshot;
    canSync: boolean;
    busy: boolean;
    onSync: (p: Platform, type: SyncKind) => void;
}) {
    const styles = useStyles();
    const { platform, snap } = props;
    const mark = MARKS[platform.key] ?? { letter: platform.name.charAt(0).toUpperCase(), bg: tokens.colorNeutralBackground5, fg: tokens.colorNeutralForeground1 };
    const headingId = `platform-${platform.id}`;
    const dataView = platform.configured ? buildDataSection(platform, snap) : null;
    const insightsView = platform.configured ? buildInsightsSection(platform, snap) : null;
    const disabledReason = platform.connectionActive ? null : `The ${platform.name} connection is not active yet`;
    return (
        <article className={styles.card} aria-labelledby={headingId}>
            <div className={styles.cardHeader}>
                <span className={styles.mark} style={{ backgroundColor: mark.bg, color: mark.fg }} aria-hidden="true">{mark.letter}</span>
                <Text id={headingId} as="h2" size={400} weight="semibold">{platform.name}</Text>
            </div>
            {platform.configured ? (
                <>
                    {!platform.connectionActive && (
                        <MessageBar intent="warning">
                            <MessageBarBody>
                                <MessageBarTitle>Connection not active yet</MessageBarTitle>
                                {" "}Sync is turned off until the {platform.name} connection is set up.
                            </MessageBarBody>
                        </MessageBar>
                    )}
                    <SyncSection
                        title="Data"
                        subtitle=""
                        view={dataView as SectionView}
                        age={lastSuccessAge(platform, snap, "data")}
                        usual={usualText(usualMinutesFor(platform, snap, "data"), false)}
                        canSync={props.canSync}
                        busy={props.busy}
                        blockedBy={insightsView?.active ? `${platform.name} insights` : null}
                        disabledReason={disabledReason}
                        buttonLabel="Sync Data"
                        divider={true}
                        onSync={() => props.onSync(platform, "data")}
                    />
                    <SyncSection
                        title="Insights"
                        subtitle={platform.insightsFlowName}
                        view={insightsView as SectionView}
                        age={lastSuccessAge(platform, snap, "insights")}
                        usual={usualText(usualMinutesFor(platform, snap, "insights"), false)}
                        canSync={props.canSync}
                        busy={props.busy}
                        blockedBy={dataView?.active ? `${platform.name} data` : null}
                        disabledReason={disabledReason}
                        buttonLabel="Sync Insights"
                        divider={false}
                        onSync={() => props.onSync(platform, "insights")}
                    />
                </>
            ) : (
                <div className={styles.notSetUp}>
                    <Text weight="semibold">Not set up yet</Text>
                    <Text size={200}>Appears here with its own buttons once its flows are added to the configuration.</Text>
                </div>
            )}
        </article>
    );
}

const GeneratedComponent = (props: GeneratedComponentProps) => {
    const { dataApi } = props;
    const styles = useStyles();
    const winAny = window as any;
    const dataReady = !!dataApi;

    const [mountNode, setMountNode] = useState<HTMLElement | null>(null);
    const setContainer = useCallback((node: HTMLDivElement | null) => setMountNode(node), []);

    const [{ snap, loading, error }, setData] = useState<{ snap: Snapshot | null; loading: boolean; error: string | null }>(() => {
        const cached = winAny[CACHE_KEY] as Snapshot | undefined;
        return { snap: cached ?? null, loading: cached === undefined, error: null };
    });
    const [reloadKey, setReloadKey] = useState(0);
    const [canSync] = useState<boolean>(() => canCurrentUserSync());
    const [pending, setPending] = useState<PendingSync | null>(null);
    const [{ busy, actionError }, setAction] = useState<{ busy: boolean; actionError: string | null }>({ busy: false, actionError: null });

    // The host hands a new dataApi every render; the poll reads the latest one through this ref.
    const dataApiRef = useRef(dataApi);
    dataApiRef.current = dataApi;
    const loadingRef = useRef(loading);
    loadingRef.current = loading;
    const watchKey = activeRequestIds(snap).join(",");

    useEffect(() => {
        if (!dataReady) return;
        const cached = winAny[CACHE_KEY] as Snapshot | undefined;
        if (cached !== undefined) {
            if (snap !== cached) setData({ snap: cached, loading: false, error: null });
            return;
        }
        let cancelled = false;
        let inflight = winAny[INFLIGHT_KEY] as Promise<Snapshot> | undefined;
        if (!inflight) {
            const p: Promise<Snapshot> = loadSnapshot(dataApi)
                .then((s) => { winAny[CACHE_KEY] = s; return s; })
                .finally(() => { if (winAny[INFLIGHT_KEY] === p) delete winAny[INFLIGHT_KEY]; });
            inflight = p;
            winAny[INFLIGHT_KEY] = p;
        }
        inflight
            .then((s) => { if (!cancelled) setData({ snap: s, loading: false, error: null }); })
            .catch(() => {
                if (!cancelled) setData({ snap: null, loading: false, error: "Unable to load the sync status. Check that you have access, then select Refresh." });
            });
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataReady, reloadKey]);

    const refresh = () => {
        delete winAny[CACHE_KEY];
        delete winAny[INFLIGHT_KEY];
        setData({ snap, loading: true, error: null });
        setReloadKey((k) => k + 1);
    };
    const refreshRef = useRef(refresh);
    refreshRef.current = refresh;

    // While any sync is running, check its request every few seconds; once it has finished
    // (succeeded or failed), refresh the page exactly as the Refresh button does.
    useEffect(() => {
        if (!dataReady || !watchKey) return;
        const watched = watchKey.split(",");
        let checking = false;
        let stopped = false;
        const timer = window.setInterval(async () => {
            if (checking || stopped || loadingRef.current) return;
            checking = true;
            try {
                const res = await dataApiRef.current.queryTable("sanidi_integrationsyncrequest", {
                    select: ["sanidi_status"],
                    filter: `statecode eq 0 and (sanidi_status eq ${REQ_REQUESTED} or sanidi_status eq ${REQ_RUNNING})`,
                    pageSize: 50,
                });
                const stillActive = new Set(res.rows.map((r: any) => readGuid(r.sanidi_integrationsyncrequestid)));
                if (!stopped && watched.some((id) => !stillActive.has(id))) {
                    stopped = true;
                    refreshRef.current();
                }
            } catch {
                // Try again on the next tick.
            } finally {
                checking = false;
            }
        }, POLL_MS);
        return () => { stopped = true; window.clearInterval(timer); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataReady, watchKey]);

    // After a data sync finishes, check run history every 15 seconds until it shows this sync's runs of
    // the later flows (or 10 minutes have passed), then refresh once more.
    const catchUp = catchUpTargets(snap);
    const catchUpKey = catchUp.map((t) => `${t.flowIds.join("+")}@${t.since.getTime()}`).join(",");
    useEffect(() => {
        if (!dataReady || !catchUpKey) return;
        const targets = catchUp;
        let checking = false;
        let stopped = false;
        const timer = window.setInterval(async () => {
            if (checking || stopped || loadingRef.current) return;
            checking = true;
            try {
                let allRecorded = true;
                for (const t of targets) {
                    if (Date.now() > t.until.getTime()) continue;
                    for (const id of t.flowIds) {
                        const res = await dataApiRef.current.queryTable("flowrun", {
                            select: ["starttime"],
                            filter: `_workflow_value eq ${id} and starttime ge ${t.since.toISOString()}`,
                            pageSize: 1,
                        });
                        if (!res.rows.length) { allRecorded = false; break; }
                    }
                    if (!allRecorded) break;
                }
                if (!stopped && allRecorded) {
                    stopped = true;
                    refreshRef.current();
                }
            } catch {
                // Try again on the next tick.
            } finally {
                checking = false;
            }
        }, CATCH_UP_POLL_MS);
        return () => { stopped = true; window.clearInterval(timer); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataReady, catchUpKey]);

    const startSync = async () => {
        if (!pending || !snap) return;
        const { platform, type } = pending;
        const now = new Date();
        setPending(null);
        setAction({ busy: true, actionError: null });
        try {
            const newId = await dataApi.createRow("sanidi_integrationsyncrequest", {
                sanidi_name: `${platform.name} - ${type === "data" ? "Data" : "Insights"} - ${formatDateTime(now)}`,
                _sanidi_platform_value: `/sanidi_integrationplatform(${platform.id})`,
                sanidi_synctype: (type === "data" ? SYNC_TYPE_DATA : SYNC_TYPE_INSIGHTS) as any,
                sanidi_status: REQ_REQUESTED as any,
                sanidi_startedon: now,
            } as any);
            const request: RequestInfo = {
                id: readGuid(typeof newId === "string" ? newId : JSON.stringify(newId)), platformId: platform.id.toLowerCase(), type, status: REQ_REQUESTED, startedOn: now, completedOn: null, error: null,
            };
            const next: Snapshot = { ...snap, requests: [request, ...snap.requests] };
            winAny[CACHE_KEY] = next;
            setData({ snap: next, loading: false, error: null });
            setAction({ busy: false, actionError: null });
        } catch {
            setAction({ busy: false, actionError: `Couldn't start the ${platform.name} ${type} sync. Check that you have permission, then try again.` });
        }
    };

    const pendingTitle = pending ? `Start ${pending.platform.name} ${pending.type === "data" ? "data" : "insights"} sync?` : "";
    const pendingBody = pending
        ? (pending.type === "data"
            ? `This runs ${pending.platform.dataFlows[0]?.name ?? "the data flow"}. The next levels down to the ads then update automatically. It can take several minutes.`
            : `This runs ${pending.platform.insightsFlowName || "the insights flow"} and updates the metrics on campaigns, ad groups and ads. It can take several minutes.`)
        : "";

    return (
        <div ref={setContainer} className={styles.root}>
            <header className={styles.header}>
                <div className={styles.titleBlock}>
                    <Text as="h1" size={600} weight="semibold">Sync Control</Text>
                    <Text className={styles.subtitle}>Latest run of each platform's data and insights sync.</Text>
                </div>
                <div className={styles.headerActions}>
                    {snap && <Text className={styles.updated}>Updated {formatDateTime(snap.loadedAt)}</Text>}
                    <Button icon={<ArrowClockwiseRegular />} onClick={refresh} disabled={loading}>Refresh</Button>
                </div>
            </header>

            {!canSync && (
                <MessageBar intent="info">
                    <MessageBarBody>You can see sync status here. Only System Administrators can start a sync.</MessageBarBody>
                </MessageBar>
            )}
            {actionError && (
                <MessageBar intent="error">
                    <MessageBarBody>{actionError}</MessageBarBody>
                </MessageBar>
            )}
            {error && (
                <MessageBar intent="error">
                    <MessageBarBody>{error}</MessageBarBody>
                </MessageBar>
            )}

            {loading && !snap ? (
                <div className={styles.center}><Spinner label="Loading sync status…" /></div>
            ) : snap ? (
                <div className={styles.grid} aria-busy={loading}>
                    {snap.platforms.map((p) => (
                        <PlatformCard
                            key={p.id}
                            platform={p}
                            snap={snap}
                            canSync={canSync}
                            busy={busy}
                            onSync={(platform, type) => setPending({ platform, type })}
                        />
                    ))}
                </div>
            ) : null}

            {snap && (
                <div className={styles.legend} aria-label="Last success colours">
                    <span className={styles.legendItem}><span className={styles.legendSwatch} style={{ backgroundColor: AGE_COLORS.ok.bg, borderColor: AGE_COLORS.ok.border }} />Successful run in the last 12 hours</span>
                    <span className={styles.legendItem}><span className={styles.legendSwatch} style={{ backgroundColor: AGE_COLORS.warn.bg, borderColor: AGE_COLORS.warn.border }} />More than 12 hours ago</span>
                    <span className={styles.legendItem}><span className={styles.legendSwatch} style={{ backgroundColor: AGE_COLORS.late.bg, borderColor: AGE_COLORS.late.border }} />More than 1 day ago</span>
                </div>
            )}

            <Dialog open={!!pending} onOpenChange={(_, d) => { if (!d.open) setPending(null); }} modalType="non-modal">
                <DialogSurface mountNode={mountNode}>
                    <DialogBody>
                        <DialogTitle>{pendingTitle}</DialogTitle>
                        <DialogContent>
                            <Text as="p" block>{pendingBody}</Text>
                            {pending && usualMinutesFor(pending.platform, snap as Snapshot, pending.type) ? (
                                <Text as="p" block weight="semibold">{usualText(usualMinutesFor(pending.platform, snap as Snapshot, pending.type), true)}</Text>
                            ) : null}
                            <Text as="p" block className={styles.muted}>The page updates itself and you'll get a notification when it finishes.</Text>
                        </DialogContent>
                        <DialogActions>
                            <Button appearance="secondary" onClick={() => setPending(null)}>Cancel</Button>
                            <Button appearance="primary" onClick={startSync}>Start sync</Button>
                        </DialogActions>
                    </DialogBody>
                </DialogSurface>
            </Dialog>
        </div>
    );
};

export default GeneratedComponent;
