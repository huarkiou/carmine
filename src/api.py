"""Autohome API endpoints, request helpers, and fetch functions."""

import json
import time
import re
from datetime import datetime

import requests


# API endpoints
RANK_API = "https://www.autohome.com.cn/web-main/car/rank/getList"
CONFIG_API = "https://www.autohome.com.cn/web-main/car/param/getParamConf"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.autohome.com.cn/rank/",
}

_nextjs_base = None
_api_params = None


def _get_nextjs_base():
    """Resolve the NextJS data base URL dynamically.

    Extracts the buildId from autohome rank index page's __NEXT_DATA__ script
    tag so that the hash stays in sync with deployments. Cached after first call.
    Raises RuntimeError if extraction fails.
    """
    global _nextjs_base
    if _nextjs_base is not None:
        return _nextjs_base
    r = requests.get("https://www.autohome.com.cn/rank/", headers=HEADERS, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch autohome page for NextJS buildId: HTTP {r.status_code}"
        )
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r.text,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("Could not find __NEXT_DATA__ script tag on autohome page")
    nd = json.loads(m.group(1))
    bid = nd.get("buildId", "")
    if not bid:
        raise RuntimeError("buildId not found in __NEXT_DATA__")
    _nextjs_base = f"https://www.autohome.com.cn/_next/data/{bid}"
    return _nextjs_base


_API_PARAMS_FALLBACK = {
    "from": 28,
    "pm": 2,
    "pluginversion": "11.75.8",
    "model": 1,
    "channel": 0,
}


def _resolve_api_params():
    """Extract from/pm/pluginversion from autohome's own JS bundle.

    Searches JS chunks loaded by the rank page for the client params object
    used in RANK_API calls. Cached after first call.
    """
    global _api_params
    if _api_params is not None:
        return _api_params
    try:
        r = requests.get(
            "https://www.autohome.com.cn/rank/", headers=HEADERS, timeout=10
        )
        js_urls = set()
        for m in re.finditer(r'src="(https?://[^"]+\.js[^"]*)"', r.text):
            js_urls.add(m.group(1))
        for m in re.finditer(r'src="(//[^"]+\.js[^"]*)"', r.text):
            js_urls.add("https:" + m.group(1))
        for url in js_urls:
            try:
                js = requests.get(url, headers=HEADERS, timeout=10).text
                m = re.search(
                    r'from:(\d+),\s*pm:(\d+),\s*pluginversion:"([^"]+)",\s*model:(\d+),\s*channel:(\d+)',
                    js,
                )
                if m:
                    _api_params = {
                        "from": int(m.group(1)),
                        "pm": int(m.group(2)),
                        "pluginversion": m.group(3),
                        "model": int(m.group(4)),
                        "channel": int(m.group(5)),
                    }
                    return _api_params
            except Exception:
                continue
    except Exception as e:
        print(f"Failed to resolve API params from JS, using fallback: {e}")
    _api_params = dict(_API_PARAMS_FALLBACK)
    return _api_params


def _get_api_params():
    """Return a copy of the resolved API params dict."""
    return dict(_resolve_api_params())


def _fallback_months(count=6):
    """Probe RANK_API backward from current month to find latest with data.

    Used when the NextJS-based month detection fails. Queries RANK_API with
    levelid=1/pagesize=1, stepping back up to 12 months until data is found.
    Returns the latest N months in YYYY-MM format, newest first.
    """
    now = datetime.now()
    for _ in range(12):
        month = f"{now.year}-{now.month:02d}"
        params = {
            **_get_api_params(),
            "pageindex": 1,
            "pagesize": 1,
            "typeid": 1,
            "subranktypeid": 1,
            "levelid": 1,
            "price": "0-9000",
            "date": month,
        }
        try:
            r = requests.get(RANK_API, params=params, headers=HEADERS, timeout=10)
            if r.json().get("result", {}).get("list", []):
                break
        except Exception:
            pass
        if now.month == 1:
            now = datetime(now.year - 1, 12, 1)
        else:
            now = datetime(now.year, now.month - 1, 1)
    y, m = now.year, now.month
    months = []
    for _ in range(count):
        months.append(f"{y}-{m:02d}")
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return months


_latest_month_cache = None


def get_latest_month():
    """Return the latest available month (YYYY-MM) from autohome.

    Result is cached after first call — brand/series lookups don't need
    per-invocation freshness.
    """
    global _latest_month_cache
    if _latest_month_cache is not None:
        return _latest_month_cache
    months = fetch_available_months(1)
    _latest_month_cache = months[0] if months else _fallback_months(1)[0]
    return _latest_month_cache


def get_months(count=6):
    """Return the latest N available months as YYYY-MM list, newest first."""
    return fetch_available_months(count)


def fetch_available_months(count=6):
    """Fetch available month options from autohome ranking page data."""
    try:
        now = datetime.now()
        for _ in range(3):
            probe_month = f"{now.year}-{now.month:02d}"
            url = (
                f"{_get_nextjs_base()}/rank/1-1-0-0_9000-x-x-x/{probe_month}.html.json"
                f"?slug=1-1-0-0_9000-x-x-x&slug={probe_month}.html"
            )
            r = requests.get(url, headers=HEADERS, timeout=10)
            data = r.json()
            if "__N_REDIRECT" in data.get("pageProps", {}):
                if now.month == 1:
                    now = datetime(now.year - 1, 12, 1)
                else:
                    now = datetime(now.year, now.month - 1, 1)
                continue
            subranklist = data["pageProps"]["options"].get("subranklist", [])
            break
        else:
            subranklist = []
        for sr in subranklist:
            for top in sr.get("toplist", []):
                if top.get("parameter") == "date":
                    months = []
                    for item in top.get("list", []):
                        v = item["value"]
                        if "_" not in v and len(v) == 7:
                            months.append(v)
                        if len(months) >= count:
                            break
                    print(
                        f"Available months: {months[0]} ~ {months[-1]} ({len(months)})"
                    )
                    return months
    except Exception as e:
        print(f"Failed to fetch months via NextJS, probing RANK_API: {e}")
    return _fallback_months(count)


def fetch_brand_map():
    """Build brandid -> brandname mapping from brand monthly ranking (subranktypeid=3)."""
    brand_map = {}
    for page in range(1, 3):
        params = {
            **_get_api_params(),
            "pageindex": page,
            "pagesize": 200,
            "typeid": 1,
            "subranktypeid": 3,
            "entitytype": "1071",
            "date": get_latest_month(),
        }
        try:
            r = requests.get(RANK_API, params=params, headers=HEADERS, timeout=15)
            r.encoding = "utf-8"
            data = r.json()
            items = data.get("result", {}).get("list", [])
            if not items:
                break
            for item in items:
                bname = item.get("seriesname", "")
                args = item.get("pvitem", {}).get("argvs", {})
                brandid = args.get("brandid")
                if not brandid:
                    m = re.search(r"brandid=(\d+)", item.get("linkurl", ""))
                    if m:
                        brandid = m.group(1)
                if brandid and bname and int(brandid) not in brand_map:
                    brand_map[int(brandid)] = bname
        except Exception as e:
            print(f"  Brand page {page} error: {e}")
        time.sleep(0.3)
    print(f"Fetched {len(brand_map)} brands from ranking")
    return brand_map


def fetch_series(levelid, month):
    """Fetch series ranking list for one level and month (subranktypeid=1)."""
    params = {
        **_get_api_params(),
        "pageindex": 1,
        "pagesize": 50,
        "typeid": 1,
        "subranktypeid": 1,
        "levelid": levelid,
        "price": "0-9000",
        "date": month,
    }
    try:
        r = requests.get(RANK_API, params=params, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        return r.json().get("result", {}).get("list", [])
    except Exception:
        return []


def fetch_series_by_level(levelid):
    """Fetch all series for a given levelid from the price page API.

    Used as fallback for categories without sales ranking data (e.g., 皮卡, 轻客).
    """
    try:
        url = f"{_get_nextjs_base()}/price/levelid_{levelid}.json"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        data = r.json()
        sgl = data.get("pageProps", {}).get("seriesList", {}).get("seriesgrouplist", [])
        series_list = {}
        for s in sgl:
            sid = str(s.get("seriesid", ""))
            if sid and sid not in series_list:
                series_list[sid] = {
                    "name": s.get("seriesname", ""),
                    "brandid": 0,  # will be resolved later
                    "fctname": s.get("fctname", ""),
                }
        return series_list
    except Exception:
        return {}


def get_param_config(seriesid):
    """Fetch parameter configuration table for a series."""
    try:
        url = f"{CONFIG_API}?mode=1&site=1&seriesid={seriesid}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        return r.json().get("result", {})
    except Exception:
        return {}


def lookup_brand_from_series(brandid, seriesid):
    """Look up brand name and manufacturer from a series detail page (NextJS data)."""
    try:
        url = f"{_get_nextjs_base()}/{seriesid}/.json"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None, None
        info = r.json().get("pageProps", {}).get("seriesBaseInfo", {})
        bname = info.get("brandName", "")
        fname = info.get("fctName", "")
        if bname:
            if fname and bname and fname.endswith(bname):
                fname = fname[: -len(bname)]
            if fname:
                from .brands import clean_manu_name  # deferred to avoid circular import

                fname = clean_manu_name(fname)
            return bname, fname or bname
    except Exception:
        pass
    return None, None


def fetch_brand_index():
    """Parse grade/carhtml/{A-Z}.html pages to build brand->manufacturer->series tree.

    Returns list of dicts:
        [{brandid, brand_name, manufacturers: [{name, series: [{seriesid, name}]}]}]
    """
    result = []
    seen_series = set()
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        url = f"https://www.autohome.com.cn/grade/carhtml/{letter}.html"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
        except Exception as e:
            print(f"  Failed to fetch {url}: {e}")
            continue

        html = r.text
        # Each brand is a <dl id="BRANDID">...</dl> block
        dl_pattern = re.compile(r'<dl id="(\d+)"(.*?)</dl>', re.DOTALL)
        for m in dl_pattern.finditer(html):
            brandid = int(m.group(1))
            section = m.group(2)

            # Brand name from <dt><div><a>...
            brand_name = ""
            bm = re.search(r"<dt>.*?<div><a.*?>(.*?)</a>", section, re.DOTALL)
            if bm:
                brand_name = bm.group(1).strip()

            # Manufacturers: each <div class="h3-tit"><a>FCT</a></div>
            # followed by <ul class="rank-list-ul"> with <li id="sSERIESID"> series
            # Split by h3-tit boundaries
            parts = re.split(r'(<div class="h3-tit">.*?</div>)', section)
            current_fct = ""
            manufacturers = []
            fct_series = []  # (fct_name, series_list)

            for part in parts:
                fct_m = re.search(r'class="h3-tit"><a.*?>(.*?)</a>', part)
                if fct_m:
                    # Flush previous fct if it had series
                    if current_fct and fct_series:
                        manufacturers.append(
                            {"name": current_fct, "series": fct_series}
                        )
                        fct_series = []
                    current_fct = fct_m.group(1).strip()
                else:
                    # Look for series in this part
                    for sm in re.finditer(
                        r'<li id="s(\d+)".*?<h4><a.*?>(.*?)</a>', part, re.DOTALL
                    ):
                        sid = sm.group(1)
                        sname = sm.group(2).strip()
                        if sid not in seen_series:
                            fct_series.append({"seriesid": sid, "name": sname})
                            seen_series.add(sid)

            # Flush last fct
            if current_fct and fct_series:
                manufacturers.append({"name": current_fct, "series": fct_series})

            if brand_name and manufacturers:
                result.append(
                    {
                        "brandid": brandid,
                        "brand_name": brand_name,
                        "manufacturers": manufacturers,
                    }
                )

        time.sleep(0.2)

    total_series = sum(
        len(s) for b in result for m in b["manufacturers"] for s in m["series"]
    )
    print(f"Brand index: {len(result)} brands, {total_series} series")
    return result
