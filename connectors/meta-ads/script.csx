// Custom code for the Meta custom connector (Meta Graph API, Marketing API).
//
// Only GetPeriodInsights runs here (see scriptoperations); every other action goes straight to graph.facebook.com.
// The connection's access token arrives as the access_token query parameter of the incoming request (api key in
// query), and is passed on to every Graph call.
//
// GetPeriodInsights reads /act_{account_id}/insights for one level (campaign / adset / ad) with time_increment=1
// (one row per day) or monthly (one row per calendar month, totalled by Meta), deleted and archived items included,
// follows every page, and returns flat rows whose keys are the Dataverse column names without the sanidi_ prefix,
// computed the same way as the lifetime "Get Meta Insights" flow (purchases from actions, and so on).
public class Script : ScriptBase
{
    private const int RawPayloadMaxLength = 100000;
    private const string Fields =
        "campaign_id,adset_id,ad_id,date_start,date_stop,account_currency,impressions,reach,frequency,spend,cpm,cpp," +
        "clicks,ctr,cpc,cost_per_unique_click,inline_link_clicks,inline_link_click_ctr,cost_per_inline_link_click," +
        "cost_per_unique_inline_link_click,inline_post_engagement,cost_per_inline_post_engagement," +
        "landing_page_view_per_link_click,purchase_per_landing_page_view,actions,action_values,cost_per_action_type," +
        "purchase_roas,outbound_clicks";

    // Effective statuses per level, so deleted and archived items are returned too.
    private static readonly Dictionary<string, string[]> Statuses = new Dictionary<string, string[]>
    {
        ["campaign"] = new[] { "ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "IN_PROCESS", "WITH_ISSUES" },
        ["adset"] = new[] { "ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "IN_PROCESS", "WITH_ISSUES", "CAMPAIGN_PAUSED" },
        ["ad"] = new[] { "ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "IN_PROCESS", "WITH_ISSUES", "CAMPAIGN_PAUSED",
                         "ADSET_PAUSED", "DISAPPROVED", "PENDING_REVIEW", "PREAPPROVED", "PENDING_BILLING_INFO" },
    };
    private static readonly Dictionary<string, string> IdField = new Dictionary<string, string>
    {
        ["campaign"] = "campaign_id", ["adset"] = "adset_id", ["ad"] = "ad_id",
    };
    private static readonly Dictionary<string, string> IdColumn = new Dictionary<string, string>
    {
        ["campaign"] = "campaignid", ["adset"] = "adsetid", ["ad"] = "advertisementid",
    };

    // Meta field -> (Dataverse column, kind). int / money (2 decimals) / rate (4 decimals) / text.
    private static readonly string[][] Plain =
    {
        new[] { "impressions", "impressions", "int" }, new[] { "reach", "reach", "int" },
        new[] { "frequency", "frequency", "money" }, new[] { "spend", "spend", "money" },
        new[] { "cpm", "cpm", "money" }, new[] { "cpp", "cpp", "money" }, new[] { "clicks", "clicks", "int" },
        new[] { "ctr", "ctr", "rate" }, new[] { "cpc", "cpc", "money" },
        new[] { "cost_per_unique_click", "costperuniqueclick", "money" },
        new[] { "inline_link_clicks", "inlinelinkclicks", "int" },
        new[] { "inline_link_click_ctr", "inlinelinkclickctr", "rate" },
        new[] { "cost_per_inline_link_click", "costperinlinelinkclick", "money" },
        new[] { "cost_per_unique_inline_link_click", "costperuniqueinlinelinkclick", "money" },
        new[] { "inline_post_engagement", "inlinepostengagement", "int" },
        new[] { "cost_per_inline_post_engagement", "costperinlinepostengagement", "money" },
        new[] { "landing_page_view_per_link_click", "landingpageviewperlinkclick", "rate" },
        new[] { "purchase_per_landing_page_view", "purchaseperlandingpageview", "rate" },
        new[] { "account_currency", "accountcurrency", "text" },
    };
    // Values taken from Meta's action lists: (list field, action_type, Dataverse column, kind).
    private static readonly string[][] FromActions =
    {
        new[] { "actions", "purchase", "purchases", "int" },
        new[] { "action_values", "purchase", "purchasevalue", "money" },
        new[] { "cost_per_action_type", "purchase", "costperpurchase", "money" },
        new[] { "actions", "landing_page_view", "landingpageviews", "int" },
        new[] { "purchase_roas", "omni_purchase", "purchaseroas", "rate" },
        new[] { "outbound_clicks", "outbound_click", "outboundclicks", "int" },
    };

    public override async Task<HttpResponseMessage> ExecuteAsync()
    {
        try
        {
            if (Context.OperationId == "GetPeriodInsights") return await GetPeriodInsights().ConfigureAwait(false);
            return await Context.SendAsync(Context.Request, CancellationToken).ConfigureAwait(false);
        }
        catch (ArgumentException ex)
        {
            return Error(HttpStatusCode.BadRequest, ex.Message);
        }
        catch (MetaException ex)
        {
            return Error(ex.Status, ex.Message);
        }
    }

    private async Task<HttpResponseMessage> GetPeriodInsights()
    {
        var query = Query(Context.Request.RequestUri.Query);
        var token = Arg(query, "access_token");
        if (string.IsNullOrEmpty(token)) throw new ArgumentException("The connection has no access token.");
        var account = (Arg(query, "account_id") ?? "").Trim();
        if (account.StartsWith("act_")) account = account.Substring(4);
        if (account.Length == 0 || !account.All(char.IsDigit)) throw new ArgumentException("account_id must be a Meta ad account ID.");
        var level = (Arg(query, "level") ?? "campaign").ToLowerInvariant();
        if (!IdField.ContainsKey(level)) throw new ArgumentException("level must be campaign, adset or ad.");
        var period = (Arg(query, "period") ?? "day").ToLowerInvariant();
        if (period != "day" && period != "month") throw new ArgumentException("period must be day or month.");
        var start = ParseDay(Arg(query, "start_date"), "start_date");
        var end = ParseDay(Arg(query, "end_date"), "end_date");
        if (end < start) throw new ArgumentException("end_date is before start_date.");

        var filtering = new JArray(new JObject
        {
            ["field"] = level + ".effective_status", ["operator"] = "IN", ["value"] = new JArray(Statuses[level]),
        });
        var args = new Dictionary<string, string>
        {
            ["level"] = level,
            ["time_increment"] = period == "day" ? "1" : "monthly",
            ["time_range"] = new JObject { ["since"] = start.ToString("yyyy-MM-dd"), ["until"] = end.ToString("yyyy-MM-dd") }
                .ToString(Newtonsoft.Json.Formatting.None),
            ["fields"] = Fields,
            ["filtering"] = filtering.ToString(Newtonsoft.Json.Formatting.None),
            ["limit"] = "500",
            ["access_token"] = token,
        };
        var baseUrl = Context.Request.RequestUri.GetLeftPart(UriPartial.Authority) + VersionPath() + "/act_" + account + "/insights";
        string url = baseUrl + "?" + string.Join("&", args.Select(kv => Uri.EscapeDataString(kv.Key) + "=" + Uri.EscapeDataString(kv.Value)));
        var now = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
        var rows = new JArray();
        while (!string.IsNullOrEmpty(url))
        {
            var page = await Get(url).ConfigureAwait(false);
            foreach (JObject r in (JArray)page["data"] ?? new JArray())
                rows.Add(Row(r, level, period, now));
            url = (string)page["paging"]?["next"];
        }
        return Ok(new JObject
        {
            ["account_id"] = account, ["level"] = level, ["period"] = period,
            ["start_date"] = start.ToString("yyyy-MM-dd"), ["end_date"] = end.ToString("yyyy-MM-dd"),
            ["row_count"] = rows.Count, ["rows"] = rows,
        });
    }

    private JObject Row(JObject r, string level, string period, string now)
    {
        var day = (string)r["date_start"] ?? "";
        if (period == "month" && day.Length >= 7) day = day.Substring(0, 7) + "-01";
        var row = new JObject
        {
            [IdColumn[level]] = (string)r[IdField[level]], ["date"] = day,
            ["datestart"] = (string)r["date_start"], ["datestop"] = (string)r["date_stop"],
            ["lastsyncedon"] = now,
        };
        foreach (var f in Plain) row[f[1]] = Value(r[f[0]], f[2]);
        foreach (var f in FromActions)
        {
            var match = (r[f[0]] as JArray)?.FirstOrDefault(a => (string)a["action_type"] == f[1]);
            row[f[2]] = Value(match?["value"], f[3]);
        }
        var raw = r.ToString(Newtonsoft.Json.Formatting.None);
        row["rawpayload"] = raw.Length > RawPayloadMaxLength ? raw.Substring(0, RawPayloadMaxLength) : raw;
        return row;
    }

    private static JToken Value(JToken v, string kind)
    {
        if (v == null || v.Type == JTokenType.Null || (v.Type == JTokenType.String && string.IsNullOrEmpty((string)v)))
            return JValue.CreateNull();
        if (kind == "text") return (string)v;
        if (!decimal.TryParse(v.ToString(), System.Globalization.NumberStyles.Float,
                              System.Globalization.CultureInfo.InvariantCulture, out var d))
            return JValue.CreateNull();
        if (kind == "int") return (long)Math.Round(d);
        return Math.Round(d, kind == "rate" ? 4 : 2);
    }

    private string VersionPath()
    {
        // The definition's base path (e.g. /v26.0) is the first segment of the incoming request's path.
        var segments = Context.Request.RequestUri.AbsolutePath.Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
        return segments.Length > 0 && segments[0].StartsWith("v") ? "/" + segments[0] : "/v26.0";
    }

    private async Task<JObject> Get(string url)
    {
        for (var attempt = 0; ; attempt++)
        {
            var response = await Context.SendAsync(new HttpRequestMessage(HttpMethod.Get, url), CancellationToken).ConfigureAwait(false);
            var text = response.Content != null ? await response.Content.ReadAsStringAsync().ConfigureAwait(false) : "";
            JObject json;
            try { json = string.IsNullOrWhiteSpace(text) ? new JObject() : JObject.Parse(text); }
            catch (JsonException) { throw new MetaException(HttpStatusCode.BadGateway, "Meta returned: " + Cut(text, 500)); }
            if (response.IsSuccessStatusCode && json["error"] == null) return json;
            var error = json["error"] as JObject;
            var code = error?["code"]?.Value<int>() ?? 0;
            // 4 / 17 / 80000-80014: rate limits; one short retry, then the flow's retry policy takes over.
            var throttled = code == 4 || code == 17 || code == 613 || (code >= 80000 && code <= 80014);
            if (throttled && attempt == 0) { await Task.Delay(5000).ConfigureAwait(false); continue; }
            var message = (string)error?["message"] ?? Cut(text, 500);
            var status = throttled ? (HttpStatusCode)429 : (response.IsSuccessStatusCode ? HttpStatusCode.BadRequest : response.StatusCode);
            throw new MetaException(status, "Meta error " + code + ": " + message + " (fbtrace_id " + (string)error?["fbtrace_id"] + ")");
        }
    }

    private static string Arg(Dictionary<string, string> query, string name) => query.TryGetValue(name, out var v) ? v : null;

    private static Dictionary<string, string> Query(string queryString)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var part in (queryString ?? "").TrimStart('?').Split('&'))
        {
            if (part.Length == 0) continue;
            var i = part.IndexOf('=');
            var key = Uri.UnescapeDataString((i < 0 ? part : part.Substring(0, i)).Replace('+', ' '));
            result[key] = i < 0 ? "" : Uri.UnescapeDataString(part.Substring(i + 1).Replace('+', ' '));
        }
        return result;
    }

    private static DateTime ParseDay(string value, string name)
    {
        if (!DateTime.TryParseExact((value ?? "").Trim(), "yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture,
                                    System.Globalization.DateTimeStyles.None, out var day))
            throw new ArgumentException(name + " must be a date in the format YYYY-MM-DD.");
        return day;
    }

    private static string Cut(string text, int length) => text == null || text.Length <= length ? text : text.Substring(0, length);

    private static HttpResponseMessage Ok(JObject body)
    {
        var response = new HttpResponseMessage(HttpStatusCode.OK);
        response.Content = CreateJsonContent(body.ToString(Newtonsoft.Json.Formatting.None));
        return response;
    }

    private static HttpResponseMessage Error(HttpStatusCode status, string message)
    {
        var response = new HttpResponseMessage(status);
        response.Content = CreateJsonContent(new JObject { ["error"] = new JObject { ["message"] = message } }
            .ToString(Newtonsoft.Json.Formatting.None));
        return response;
    }

    private class MetaException : Exception
    {
        public HttpStatusCode Status { get; }
        public MetaException(HttpStatusCode status, string message) : base(message) { Status = status; }
    }
}
