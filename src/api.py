"""Autohome API endpoints, request helpers, and fetch functions."""
import time
import re
import requests

from .brands import MONTHS


def get_latest_month():
    """Return the latest available month (YYYY-MM) from autohome."""
    months = fetch_available_months(1)
    return months[0] if months else MONTHS[-1]


def get_months(count=6):
    """Return the latest N available months as YYYY-MM list, newest first."""
    return fetch_available_months(count)


def fetch_available_months(count=6):
    """Fetch available month options from autohome ranking page data."""
    try:
        url = f"{NEXTJS_DATA}/rank/1-1-0-0_9000-x-x-x/{MONTHS[-1]}.html.json?slug=1-1-0-0_9000-x-x-x&slug={MONTHS[-1]}.html"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        subranklist = data["pageProps"]["options"].get("subranklist", [])
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
                    print(f"Available months: {months[0]} ~ {months[-1]} ({len(months)})")
                    return months
    except Exception as e:
        print(f"Failed to fetch months, using defaults: {e}")
    return MONTHS[:count]

# API endpoints
RANK_API = "https://www.autohome.com.cn/web-main/car/rank/getList"
CONFIG_API = "https://www.autohome.com.cn/web-main/car/param/getParamConf"
NEXTJS_DATA = "https://www.autohome.com.cn/_next/data/nextweb-prod-c_1.0.234-p_2.36.0"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"https://www.autohome.com.cn/rank/1-1-0-0_9000-x-x-x/{MONTHS[-1]}.html",
}


def fetch_brand_map():
    """Build brandid -> brandname mapping from brand monthly ranking (subranktypeid=3)."""
    brand_map = {}
    for page in range(1, 3):
        params = {
            "from": 28, "pm": 2, "pluginversion": "11.75.8",
            "model": 1, "channel": 0, "pageindex": page, "pagesize": 200,
            "typeid": 1, "subranktypeid": 3, "entitytype": "1071",
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
        "from": 28, "pm": 2, "pluginversion": "11.75.8",
        "model": 1, "channel": 0, "pageindex": 1, "pagesize": 50,
        "typeid": 1, "subranktypeid": 1, "levelid": levelid,
        "price": "0-9000", "date": month,
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
        url = f"{NEXTJS_DATA}/price/levelid_{levelid}.json"
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
        url = f"{NEXTJS_DATA}/{seriesid}/.json"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None, None
        info = r.json().get("pageProps", {}).get("seriesBaseInfo", {})
        bname = info.get("brandName", "")
        fname = info.get("fctName", "")
        if bname:
            if fname and bname and fname.endswith(bname):
                fname = fname[:-len(bname)]
            if fname:
                from .brands import clean_manu_name  # deferred to avoid circular import
                fname = clean_manu_name(fname)
            return bname, fname or bname
    except Exception:
        pass
    return None, None
