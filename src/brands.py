"""Brand-to-manufacturer mapping, name cleaning, and lookup logic."""
import time
from collections import defaultdict

# Vehicle category definitions: (子分类名, levelid)
CATEGORIES = {
    "轿车": [
        ("微型车", "1"), ("小型车", "2"), ("紧凑型车", "3"),
        ("中型车", "4"), ("中大型车", "5"), ("大型车", "6"),
    ],
    "SUV": [
        ("小型SUV", "16"), ("紧凑型SUV", "17"), ("中型SUV", "18"),
        ("中大型SUV", "19"), ("大型SUV", "20"),
    ],
    "MPV": [
        ("紧凑型MPV", "21"), ("中型MPV", "22"),
        ("中大型MPV", "23"), ("大型MPV", "24"),
    ],
}

MONTHS = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]

# brand_name -> manufacturer_name
BRAND_TO_MANUFACTURER = {
    # 比亚迪集团
    "比亚迪": "比亚迪",
    "方程豹": "比亚迪",
    "腾势": "比亚迪",
    "仰望": "比亚迪",
    # 吉利集团
    "吉利汽车": "吉利",
    "吉利银河": "吉利",
    "吉利几何": "吉利",
    "领克": "吉利",
    "极氪": "吉利",
    "睿蓝汽车": "吉利",
    # 长城集团
    "哈弗": "长城",
    "魏牌": "长城",
    "坦克": "长城",
    "欧拉": "长城",
    # 长安集团
    "长安": "长安",
    "长安启源": "长安",
    "深蓝汽车": "长安",
    "阿维塔": "长安",
    "长安欧尚": "长安",
    "长安凯程": "长安",
    # 奇瑞集团
    "奇瑞": "奇瑞",
    "奇瑞QQ": "奇瑞",
    "奇瑞风云": "奇瑞",
    "捷途": "奇瑞",
    "捷途山海": "奇瑞",
    "星途": "奇瑞",
    "iCAR": "奇瑞",
    "凯翼": "奇瑞",
    # 蔚来集团
    "蔚来": "蔚来",
    "乐道": "蔚来",
    "firefly萤火虫": "蔚来",
    # 新势力
    "小鹏": "小鹏",
    "理想汽车": "理想",
    "零跑汽车": "零跑",
    "小米汽车": "小米",
    "特斯拉": "特斯拉",
    # 东风集团
    "东风风神": "东风",
    "东风奕派": "东风",
    "东风风行": "东风",
    "东风风度": "东风",
    "东风风光": "东风",
    "东风富康": "东风",
    "岚图汽车": "东风",
    "猛士": "东风",
    "蓝电": "东风",
    "纳米": "东风",
    # 上汽集团
    "荣威": "上汽",
    "名爵": "上汽",
    "智己汽车": "上汽",
    "大通": "上汽",
    # 上汽通用五菱
    "五菱汽车": "上汽通用五菱",
    "宝骏": "上汽通用五菱",
    # 广汽集团
    "广汽传祺": "广汽",
    "埃安": "广汽",
    "广汽昊铂": "广汽",
    # 北汽集团
    "ARCFOX极狐": "北汽",
    "北京汽车": "北汽",
    "北京汽车制造厂": "北汽",
    "北汽新能源": "北汽",
    "北京越野": "北汽",
    # 一汽集团
    "红旗": "一汽",
    "奔腾": "一汽",
    "捷达": "一汽",
    # 鸿蒙智行
    "鸿蒙智行": "鸿蒙智行",
    "AITO 问界": "赛力斯",
    "智界": "鸿蒙智行",
    "享界": "鸿蒙智行",
    "尊界": "鸿蒙智行",
    "尚界": "鸿蒙智行",
    # 江淮
    "江淮汽车": "江淮",
    "江淮瑞风": "江淮",
    "江淮钇为": "江淮",
    # 其他中国品牌
    "中国重汽VGV": "中国重汽",
    "SWM斯威汽车": "鑫源",
    "创维汽车": "创维",
    "曹操汽车": "曹操",
    "凌宝汽车": "凌宝",
    "鑫源汽车": "鑫源",
    "启辰": "东风日产",
    "212": "北汽",
    "ROX极石": "极石",
    # 合资/外资品牌
    "大众": "大众",
    "丰田": "丰田",
    "本田": "本田",
    "日产": "日产",
    "宝马": "宝马",
    "奔驰": "奔驰",
    "奥迪": "奥迪",
    "凯迪拉克": "凯迪拉克",
    "沃尔沃": "沃尔沃",
    "福特": "福特",
    "别克": "别克",
    "雪佛兰": "雪佛兰",
    "雪铁龙": "雪铁龙",
    "标致": "标致",
    "现代": "现代",
    "起亚": "起亚",
    "马自达": "马自达",
    "路虎": "路虎",
    "捷豹": "捷豹",
    "英菲尼迪": "英菲尼迪",
    "林肯": "林肯",
    "smart": "smart",
    "福田": "福田",
    "灵悉": "灵悉",
    "纵横": "纵横",
    "示界": "示界",
    "埃尚": "埃尚",
    # 补充映射（从小众品牌/车型详情页获取）
    "江铃集团新能源": "江铃",
    "知豆电动车": "知豆",
    "知豆": "知豆",
    "合创汽车": "合创",
    "海马": "一汽",
    "斯柯达": "上汽大众",
    "白晔": "白晔",
}


def clean_manu_name(name):
    """Strip common suffixes (汽车制造厂, 汽车, 集团) from manufacturer names."""
    if not name:
        return name
    for suffix in ["汽车制造厂", "汽车", "集团"]:
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[:-len(suffix)]
    return name


def create_manu_map(brand_map):
    """Map brandid -> manufacturer using explicit BRAND_TO_MANUFACTURER, with fallback to cleaning."""
    result = {}
    for brandid, brand_name in brand_map.items():
        manu = BRAND_TO_MANUFACTURER.get(brand_name)
        if not manu:
            for key in BRAND_TO_MANUFACTURER:
                if key in brand_name or brand_name in key:
                    manu = BRAND_TO_MANUFACTURER[key]
                    break
        if not manu:
            manu = clean_manu_name(brand_name)
        result[brandid] = manu
    return result


def fill_missing_brands(brand_map, manu_map, series_by_brand):
    """Query series detail pages for brands not found in brand ranking API."""
    from .api import lookup_brand_from_series

    missing = {bid for bid in series_by_brand if bid not in brand_map}
    if not missing:
        return
    print(f"Filling {len(missing)} missing brands from series detail pages...")
    for brandid in sorted(missing):
        sid = series_by_brand[brandid][0]
        bname, manu = lookup_brand_from_series(brandid, sid)
        if bname:
            brand_map[brandid] = bname
            if manu:
                manu_map[brandid] = manu
            print(f"  brandid={brandid}: brand={bname}, manu={manu}")
        time.sleep(0.3)


def resolve_brands(brand_map, manu_map, series_by_brand):
    """Complete brand resolution pipeline: fetch -> map -> fill missing -> re-apply mapping."""
    previously_missing = {bid for bid in series_by_brand if bid not in brand_map}
    fill_missing_brands(brand_map, manu_map, series_by_brand)
    new_manu = create_manu_map(brand_map)
    for bid in previously_missing:
        if bid in new_manu:
            manu_map[bid] = new_manu[bid]
    return previously_missing
