import { useCallback, useEffect, useState } from "react";
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
    Spinner,
    Text,
    makeStyles,
    tokens,
} from "@fluentui/react-components";
import {
    ArrowClockwiseRegular,
    ArrowSyncRegular,
    CheckmarkCircleFilled,
    CircleRegular,
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
    error: string | null;
}

interface Snapshot {
    platforms: Platform[];
    runs: Record<string, RunInfo | null>;
    requests: RequestInfo[];
    loadedAt: Date;
}

interface StepView { name: string; kind: Kind; time: string; }

interface SectionView {
    kind: Kind;
    lastRun: string;
    steps: StepView[];
    failedName: string | null;
    error: string | null;
    active: boolean;
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
        borderTopWidth: "1px",
        borderRightWidth: "1px",
        borderBottomWidth: "1px",
        borderLeftWidth: "1px",
        borderStyle: "solid",
        borderColor: tokens.colorNeutralStroke2,
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
            "sanidi_dataflows", "sanidi_insightsflowname", "sanidi_insightsflowid"],
        filter: "statecode eq 0",
        orderBy: "sanidi_sortorder asc",
        pageSize: 50,
    });
    const platforms: Platform[] = platformResult.rows.map((r: any) => ({
        id: String(r.sanidi_integrationplatformid),
        name: String(r.sanidi_name || ""),
        key: String(r.sanidi_platformkey || "").toLowerCase(),
        configured: r.sanidi_isconfigured === true || r.sanidi_isconfigured === 1,
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

    const requestResult = await dataApi.queryTable("sanidi_integrationsyncrequest", {
        select: ["sanidi_status", "sanidi_synctype", "_sanidi_platform_value", "sanidi_startedon", "sanidi_errormessage"],
        filter: "statecode eq 0",
        orderBy: "sanidi_startedon desc",
        pageSize: 100,
    });
    const requests: RequestInfo[] = requestResult.rows.map((r: any) => ({
        id: String(r.sanidi_integrationsyncrequestid),
        platformId: String(r._sanidi_platform_value || "").toLowerCase(),
        type: Number(r.sanidi_synctype) === SYNC_TYPE_INSIGHTS ? "insights" : "data",
        status: Number(r.sanidi_status),
        startedOn: toDate(r.sanidi_startedon),
        error: typeof r.sanidi_errormessage === "string" ? r.sanidi_errormessage : null,
    }));

    return { platforms, runs, requests, loadedAt: new Date() };
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
    const stepViews: StepView[] = steps.map((s) => ({
        name: s.name,
        kind: s.run ? s.run.kind : "none",
        time: s.run ? formatShort(s.run.start) : "No runs yet",
    }));
    const base = { lastRun, steps: stepViews };

    if (isActive(req)) {
        return { ...base, kind: "running", failedName: null, error: null, active: true };
    }
    const outcome = requestOutcome(req, firstStart);
    if (outcome?.kind === "failed") {
        const failedName = isNotStarted(req) ? null : steps[0]?.name ?? null;
        return { ...base, kind: "failed", failedName, error: outcome.error, active: false };
    }
    if (outcome?.kind === "succeeded") {
        // The campaigns flow finished; the flows after it may still be running or not yet in the run history.
        return { ...base, kind: "succeeded", failedName: null, error: null, active: false };
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

    if (isActive(req)) return { ...base, kind: "running", error: null, active: true };
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

function StepIcon(props: { kind: Kind }) {
    if (props.kind === "succeeded") return <CheckmarkCircleFilled aria-hidden="true" style={{ color: tokens.colorStatusSuccessForeground1 }} />;
    if (props.kind === "failed") return <DismissCircleFilled aria-hidden="true" style={{ color: tokens.colorStatusDangerForeground1 }} />;
    if (props.kind === "running") return <ArrowSyncRegular aria-hidden="true" style={{ color: tokens.colorBrandForeground1 }} />;
    if (props.kind === "cancelled") return <DismissCircleFilled aria-hidden="true" style={{ color: tokens.colorStatusWarningForeground1 }} />;
    return <CircleRegular aria-hidden="true" style={{ color: tokens.colorNeutralForeground3 }} />;
}

function StepLabel(props: { kind: Kind }) {
    const labels: Record<Kind, string> = {
        succeeded: "Succeeded", failed: "Failed", running: "Running", cancelled: "Cancelled", none: "",
    };
    return <span>{labels[props.kind]}</span>;
}

function SyncSection(props: {
    title: string;
    view: SectionView;
    subtitle: string;
    canSync: boolean;
    busy: boolean;
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
            <Text className={styles.muted}>Last run {view.lastRun}{props.subtitle ? ` · ${props.subtitle}` : ""}</Text>
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
                    disabled={view.active || props.busy}
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
    return (
        <article className={styles.card} aria-labelledby={headingId}>
            <div className={styles.cardHeader}>
                <span className={styles.mark} style={{ backgroundColor: mark.bg, color: mark.fg }} aria-hidden="true">{mark.letter}</span>
                <Text id={headingId} as="h2" size={400} weight="semibold">{platform.name}</Text>
            </div>
            {platform.configured ? (
                <>
                    <SyncSection
                        title="Data"
                        subtitle=""
                        view={buildDataSection(platform, snap)}
                        canSync={props.canSync}
                        busy={props.busy}
                        buttonLabel="Sync Data"
                        divider={true}
                        onSync={() => props.onSync(platform, "data")}
                    />
                    <SyncSection
                        title="Insights"
                        subtitle={platform.insightsFlowName}
                        view={buildInsightsSection(platform, snap)}
                        canSync={props.canSync}
                        busy={props.busy}
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
                id: String(newId), platformId: platform.id.toLowerCase(), type, status: REQ_REQUESTED, startedOn: now, error: null,
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

            <Dialog open={!!pending} onOpenChange={(_, d) => { if (!d.open) setPending(null); }} modalType="non-modal">
                <DialogSurface mountNode={mountNode}>
                    <DialogBody>
                        <DialogTitle>{pendingTitle}</DialogTitle>
                        <DialogContent>{pendingBody}</DialogContent>
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
