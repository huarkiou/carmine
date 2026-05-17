"""Autohome API endpoints, request helpers, and fetch functions."""
import time
import re
import requests

from .brands import MONTHS, CATEGORIES

LATEST_MONTH = MONTHS[-1]  # "2026-04" — used as default for brand/ref data

# API endpoints
RANK_API = "https://www.autohome.com.cn/web-main/car/rank/getList"
CONFIG_API = "https://www.autohome.com.cn/web-main/car/param/getParamConf"
NEXTJS_DATA = "https://www.autohome.com.cn/_next/data/nextweb-prod-c_1.0.234-p_2.36.0"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"https://www.autohome.com.cn/rank/1-1-0-0_9000-x-x-x/{LATEST_MONTH}.html",
}


def fetch_brand_map():
    """Build brandid -> brandname mapping from brand monthly ranking (subranktypeid=3)."""
    brand_map = {}
    for page in range(1, 3):
        params = {
            "from": 28, "pm": 2, "pluginversion": "11.75.8",
            "model": 1, "channel": 0, "pageindex": page, "pagesize": 200,
            "typeid": 1, "subranktypeid": 3, "entitytype": "1071",
            "date": LATEST_MONTH,
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


def fetch_all_series():
    """Collect all unique series from ranking data across all categories."""
    all_series = {}
    for cat_big, subcats in CATEGORIES.items():
        for sub_name, levelid in subcats:
            items = fetch_series(levelid, LATEST_MONTH)
            for item in items:
                sid = str(item.get("seriesid", ""))
                if sid and sid not in all_series:
                    all_series[sid] = {
                        "name": item.get("seriesname", ""),
                        "brandid": item.get("brandid", 0),
                    }
            time.sleep(0.2)
    print(f"Collected {len(all_series)} unique series")
    return all_series


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
