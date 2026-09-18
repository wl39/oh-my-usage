"""Provider response shapes -> unit-aware metrics (no credentials or account data)."""

import re
from .common import amount, badge, iso, number, obj, progress, rows, text, ProviderError


def claude(data):
    labels = {"five_hour": ("session", "Session", 300), "seven_day": ("weekly", "Weekly", 10080),
              "seven_day_sonnet": ("sonnet", "Sonnet", 10080), "seven_day_opus": ("opus", "Opus", 10080)}
    result = []
    for key, value in obj(data).items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", key) or not isinstance(value, dict):
            continue
        if key == "extra_usage":
            if value.get("is_enabled") is True:
                used, limit = number(value.get("used_credits")), number(value.get("monthly_limit"))
                result += rows(progress("extra", "Extra usage", used / 100 if used is not None else None,
                                        limit / 100 if limit is not None else None, "dollars"))
            continue
        id, label, minutes = labels.get(key, (key, key.replace("_", " "), None))
        result += rows(progress(id, label, value.get("utilization"), reset=value.get("resets_at"), minutes=minutes))
    return result


def codex(data):
    buckets = obj(data.get("rateLimitsByLimitId")) or {"codex": data.get("rateLimits")}
    result = []
    for key, bucket in buckets.items():
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", key):
            continue
        for slot in ("primary", "secondary"):
            value = obj(obj(bucket).get(slot))
            minutes = number(value.get("windowDurationMins"))
            period = {300: "session", 10080: "weekly"}.get(minutes, slot)
            id = period if key == "codex" else key + "." + period
            label = period.title() if key == "codex" else key + " " + period.title()
            result += rows(progress(id, label, value.get("usedPercent"), reset=value.get("resetsAt"), minutes=minutes))
    return result


def antigravity(data):
    result = []
    data = obj(data.get("response", data))
    labels = {"gemini-5h": ("geminiPro", "Gemini 5h", 300), "gemini-weekly": ("geminiWeekly", "Gemini Weekly", 10080),
              "3p-5h": ("claude", "Third-party 5h", 300), "3p-weekly": ("claudeWeekly", "Third-party Weekly", 10080)}
    for group in data.get("groups", []):
        for bucket in obj(group).get("buckets", []):
            bucket = obj(bucket)
            key, remaining = text(bucket.get("bucketId")), number(bucket.get("remainingFraction"))
            if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", key) or remaining is None or not 0 <= remaining <= 1:
                continue
            id, label, minutes = labels.get(key, (key, key, None))
            result += rows(progress(id, label, (1 - remaining) * 100, reset=bucket.get("resetTime"), minutes=minutes))
    return result


def copilot(data):
    result = []
    reset = data.get("quota_reset_date") or data.get("limited_user_reset_date")
    quotas = obj(data.get("quota_snapshots"))
    for key, id, label in (("premium_interactions", "premium", "Credits"), ("chat", "chat", "Chat"),
                           ("completions", "completions", "Completions")):
        value = obj(quotas.get(key))
        limit, remaining, percent = number(value.get("entitlement")), number(value.get("remaining")), number(value.get("percent_remaining"))
        if value.get("unlimited") is True or limit in (-1, 0) or remaining == -1:
            continue
        if percent is not None and 0 <= percent <= 100:
            result += rows(progress(id, label, 100 - percent, reset=reset))
        elif limit is not None and remaining is not None and limit > 0:
            result += rows(progress(id, label, max(0, limit - remaining), limit, "count", reset))
        if id == "premium" and result and value.get("overage_permitted") is True:
            result += rows(amount("overage", "Overage", value.get("overage_count"), "count"))
    if not result:
        for key in ("chat", "completions"):
            limit = number(obj(data.get("monthly_quotas")).get(key))
            remaining = number(obj(data.get("limited_user_quotas")).get(key))
            if limit is not None and remaining is not None and limit > 0 and remaining >= 0:
                result += rows(progress(key, key.title(), max(0, limit - remaining), limit, "count", reset))
    if not result:
        used = number(obj(quotas.get("premium_interactions")).get("credits_used"))
        if used is not None and used > 0:
            result += rows(amount("premiumUsed", "Credits used", used, "count"))
    return result


def copilot_org(data):
    items = obj(data).get("usageItems", [])
    relevant = [x for x in items if isinstance(x, dict) and str(x.get("product", "")).lower() == "copilot"
                and str(x.get("unitType", "")).lower() in ("ai-units", "ai-credits")]
    credits = [number(x.get("grossQuantity")) for x in relevant]
    spend = [number(x.get("netAmount")) for x in relevant]
    return rows(amount("orgCredits", "Organization credits", sum(x for x in credits if x is not None), "count") if any(x is not None for x in credits) else None,
                amount("orgSpend", "Organization spend", sum(x for x in spend if x is not None)) if any(x is not None for x in spend) else None)


def cursor(data, rest=False):
    result = []
    reset = data.get("billingCycleEnd")
    plan = obj(obj(data.get("individualUsage")).get("plan")) if rest else obj(data.get("planUsage"))
    total = number(plan.get("totalPercentUsed"))
    limit, used = number(plan.get("limit")), number(plan.get("totalSpend"))
    remaining = number(plan.get("remaining"))
    if used is None and limit is not None and remaining is not None:
        used = max(0, limit - remaining)
    if total is None and limit is not None and used is not None and limit > 0:
        total = used / limit * 100
    spend = obj(obj(data.get("individualUsage")).get("onDemand")) if rest else obj(data.get("spendLimitUsage"))
    team = not rest and (text(spend.get("limitType")).lower() == "team" or (number(spend.get("pooledLimit")) or 0) > 0)
    if data.get("enabled") is not False:
        total_row = progress("total", "Total usage", used / 100 if used is not None else None,
                             limit / 100 if limit is not None else None, "dollars", reset) if team else progress("total", "Total usage", total, reset=reset)
        result += rows(total_row,
                       progress("auto", "Auto", plan.get("autoPercentUsed"), reset=reset),
                       progress("api", "API", plan.get("apiPercentUsed"), reset=reset))
    used = number(spend.get("used" if rest else "individualUsed"))
    limit = number(spend.get("limit" if rest else "individualLimit"))
    remaining = number(spend.get("remaining" if rest else "individualRemaining"))
    if used is None and limit is not None and remaining is not None:
        used = max(0, limit - remaining)
    if used is None and not rest:
        used = number(spend.get("totalSpend"))
    if not rest and (spend.get("limitType") in ("team", "LIMIT_TYPE_TEAM") or number(spend.get("pooledLimit"))):
        pooled, pooled_used = number(spend.get("pooledLimit")), number(spend.get("pooledUsed"))
        result += rows(progress("team", "Team usage", pooled_used / 100 if pooled_used is not None else None,
                                pooled / 100 if pooled is not None else None, "dollars", reset))
    if spend.get("enabled") is not False and used is not None:
        result += rows(progress("onDemand", "On-demand", used / 100, limit / 100, "dollars", reset)
                       if limit is not None and limit > 0 else amount("onDemand", "On-demand", used / 100))
    return result


def cursor_requests(data):
    value = obj(data.get("gpt-4"))
    return rows(progress("requests", "Requests", value.get("numRequests", value.get("numRequestsTotal")),
                         value.get("maxRequestUsage"), "count"))


def cursor_credits(data):
    if data.get("hasCreditGrants") is not True:
        return []
    used, total = number(data.get("usedCents")), number(data.get("totalCents"))
    return rows(progress("credits", "Credit grants", used / 100 if used is not None else None,
                         total / 100 if total is not None else None, "dollars"))


def cursor_grok(data):
    if data.get("usesPooledEnterpriseAllowance") is True or data.get("hasNonZeroIncludedLimit") is False or data.get("includedLimitZero") is True:
        return []
    return rows(progress("grok", "Grok", data.get("usagePercent"), reset=data.get("nextResetTimestampUtc")))


def devin(data):
    plan = obj(obj(data.get("userStatus")).get("planStatus"))
    daily, weekly = number(plan.get("dailyQuotaRemainingPercent")), number(plan.get("weeklyQuotaRemainingPercent"))
    # The protobuf JSON endpoint omits a scalar when its value equals zero.
    if "weeklyQuotaRemainingPercent" not in plan and number(plan.get("weeklyQuotaResetAtUnix")):
        weekly = 0
    if "dailyQuotaRemainingPercent" not in plan and number(plan.get("dailyQuotaResetAtUnix")):
        daily = 0
    extra = number(plan.get("overageBalanceMicros"))
    return rows(progress("daily", "Daily", 100 - daily if daily is not None else None,
                         reset=plan.get("dailyQuotaResetAtUnix"), minutes=1440)
                if obj(plan.get("planInfo")).get("hideDailyQuota") is not True else None,
                progress("weekly", "Weekly", 100 - weekly if weekly is not None else None,
                         reset=plan.get("weeklyQuotaResetAtUnix"), minutes=10080),
                amount("balance", "Extra balance", extra / 1e6 if extra is not None else None))


def grok(data):
    value = obj(data.get("config"))
    period = obj(value.get("currentPeriod"))
    used = number(value.get("creditUsagePercent"))
    start, end = iso(period.get("start")), iso(period.get("end"))
    if not start or not end or start >= end or not text(period.get("type")):
        raise ProviderError("invalid_response")
    if "creditUsagePercent" not in value and start and end and start < end:
        used = 0  # protobuf default; an absent config is never treated as zero usage
    if used is None:
        raise ProviderError("invalid_response")
    weekly = period.get("type") == "USAGE_PERIOD_TYPE_WEEKLY"
    return rows(progress("weekly" if weekly else "period", "Weekly" if weekly else "Current period", used,
                         reset=period.get("end"), minutes=10080 if weekly else None),
                amount("onDemandCap", "On-demand cap", obj(value.get("onDemandCap")).get("val"), "count"))


def ollama(data):
    result = []
    for id, minutes in (("session", None), ("weekly", None)):
        used = number(obj(obj(data.get("limits")).get(id)).get("usage"))
        result += rows(progress(id, id.title(), used * 100 if used is not None else None, minutes=minutes))
    return result + rows(amount("last4Weeks", "Last 4 weeks", obj(data.get("activity")).get("cost")))


def opencode(data):
    result = []
    usage = obj(data.get("usage"))
    for key, id, label in (("rolling", "session", "Session"), ("weekly", "weekly", "Weekly"), ("monthly", "monthly", "Monthly")):
        value = obj(usage.get(key))
        result += rows(progress(id, label, value.get("percent"), reset=value.get("resetsAt")))
    return result


def openrouter(credits, key):
    credits, key = obj(credits.get("data")), obj(key.get("data"))
    used, total = number(credits.get("total_usage")), number(credits.get("total_credits"))
    limit, remaining = number(key.get("limit")), number(key.get("limit_remaining"))
    return rows(progress("credits", "Credits", used, total, "dollars"),
                amount("balance", "Balance", max(0, total - used)) if total is not None and used is not None else None,
                progress("keyLimit", "Key limit", max(0, limit - remaining), limit, "dollars") if limit is not None and remaining is not None else None,
                amount("today", "Today", key.get("usage_daily")), amount("week", "This week", key.get("usage_weekly")),
                amount("month", "This month", key.get("usage_monthly")))


def zai(data):
    if data.get("success") is False:
        raise ProviderError("no_subscription" if "coding plan" in text(data.get("msg")).lower() else "invalid_response")
    result = []
    for value in obj(data.get("data", data)).get("limits", []):
        value = obj(value)
        kind = value.get("type", value.get("name"))
        if kind in ("CREDIT_LIMIT", "TOKENS_LIMIT"):
            unit, count = number(value.get("unit")), number(value.get("number"))
            if count is None or count <= 0 or unit not in (3, 4, 5, 6):
                continue
            minutes = {3: 60, 4: 1440, 6: 10080}.get(unit)
            minutes = minutes * count if minutes else None
            period = "monthly" if unit == 5 else "session" if minutes and minutes < 1440 else "weekly"
            result += rows(progress(period, period.title(), value.get("percentage"), reset=value.get("nextResetTime"), minutes=minutes))
        elif kind == "TIME_LIMIT":
            result += rows(progress("search", "Web searches", value.get("currentValue"), value.get("usage"), "count", value.get("nextResetTime")))
    return result
