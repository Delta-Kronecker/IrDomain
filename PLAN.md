# IrDomain — نقشه دقیق اجرای پروژه

## ۰. هدف کلان

ساخت دیتابیس جامع از سایت‌های ایرانی (شامل دامنه‌های `.ir` **و** دامنه‌های غیر `.ir` مثل `aparat.com`) با امتیاز اعتماد (`confidence`)، قابل استفاده برای تحلیل، تحقیق و جستجو.

**شاخص‌های موفقیت (KPI):**

| فاز | هدف |
|---|---|
| فاز ۱ | ≥ ۲۰۰,۰۰۰ دامنه/زیردامنه یکتا با ثبت منبع |
| فاز ۲ | ≥ ۵۰,۰۰۰ دامنه با برچسب ایرانی‌بودن و `confidence` |
| فاز ۳ | ≥ ۳۰۰ سایت پربازدید ایرانی (غیر `.ir`) صحیح‌سنجی‌شده |
| کیفیت | دقت برچسب‌زنی ≥ ۹۰٪ در نمونه دستی ۲۰۰تایی |

**محدودیت‌ها:** رعایت `robots.txt` و rate limit؛ عدم ذخیره/انتشار اطلاعات شخصی مالکان WHOIS؛ بدون استفاده از سرویس‌های پولی (مثل SimilarWeb API) در فاز اولیه.

---

## ۱. ساختار مخزن

```
IrDomain/
├── PLAN.md                  # همین سند (مبنای اجرا)
├── README.md
├── requirements.txt
├── .gitignore               # data/raw/, *.db, logs/, .env
├── src/irdata/
│   ├── __init__.py
│   ├── config.py            # مسیرها، UA، rate limitها
│   ├── collectors/
│   │   ├── crtsh.py         # زیردامنه‌های .ir از CT logs
│   │   ├── commoncrawl.py   # URLهای .ir از ایندکس Common Crawl
│   │   ├── radar.py         # دامنه‌های پربازدید ایران (Cloudflare Radar)
│   │   ├── tranco.py        # فیلتر .ir از لیست Tranco
│   │   └── lists.py         # ریپازیتوری‌های GitHub / دیتاست‌های آماده
│   ├── classify/
│   │   ├── fetcher.py       # fetch موازی صفحه اصلی (httpx async)
│   │   ├── features.py      # استخراج سیگنال‌ها (فارسی، توکن‌ها، lang)
│   │   └── scorer.py        # محاسبه ir_score و verdict
│   ├── enrich/
│   │   ├── whois.py         # whois.nic.ir + کشور مالک
│   │   └── asn.py           # DNS A → ASN (iptoasn)
│   ├── storage/
│   │   └── db.py            # SQLite: schema، insert، گزارش
│   └── utils/
│       └── net.py           # retry, rate-limit, normalize domain
├── scripts/                 # entrypointهای CLI (python -m scripts.X)
│   ├── collect.py           # فاز ۱
│   ├── classify.py          # فاز ۲
│   ├── enrich.py            # فاز ۳
│   └── report.py            # گزارش آماری
├── data/
│   ├── raw/                 # خام (gitignored)
│   └── processed/           # seed_domains.csv، verdicts.csv (کامیت می‌شود)
├── logs/                    # gitignored
└── tests/
```

---

## ۲. مدل داده (SQLite در فاز ۱–۳)

```sql
CREATE TABLE domains (
  domain       TEXT PRIMARY KEY,      -- نرمال‌شده، lowercase
  is_tld_ir    INTEGER,               -- 1 اگر پسوند .ir باشد
  first_seen   TEXT,
  last_seen    TEXT
);

CREATE TABLE sources (                -- منبع/منابع هر دامنه
  domain       TEXT REFERENCES domains(domain),
  source       TEXT,                  -- crtsh|commoncrawl|radar|tranco|github|...
  collected_at TEXT
);

CREATE TABLE fetches (                -- نتیجه فاز ۲ برای هر دامنه
  domain         TEXT REFERENCES domains(domain),
  fetched_at     TEXT,
  status         INTEGER,
  final_url      TEXT,
  title          TEXT,
  lang           TEXT,
  persian_ratio  REAL,
  token_hits     TEXT,                -- JSON آرایه توکن‌های یافته‌شده
  ir_score       REAL,                -- 0..1
  verdict        TEXT                 -- iranian|uncertain|foreign
);

CREATE TABLE enrichment (             -- فاز ۳
  domain             TEXT REFERENCES domains(domain),
  registrant_country TEXT,
  registrar          TEXT,
  ip                 TEXT,
  asn                TEXT,
  rank_country       REAL
);
```

---

## ۳. فاز ۱ — جمع seed list

| منبع | Endpoint / روش | جزئیات | تخمین حجم |
|---|---|---|---|
| crt.sh | `https://crt.sh/?q=%.ir&output=json` | زیردامنه‌های `.ir`؛ پارس JSON و نرمال‌سازی نام دامنه؛ استراحت بین درخواست‌ها (سرویس عمومی) | ۱۰۰k+ |
| Common Crawl | `https://index.commoncrawl.org/CC-MAIN-<نسخه>-index?url=*.ir&output=json` | صفحه‌بندی با `&page=N`؛ فقط `urlkey`/host استخراج شود؛ از ۲ نسخه آخر ایندکس | ۵۰۰k+ URL → ده‌ها k دامنه |
| Cloudflare Radar | `GET /client/v4/radar/ranking/top?location=IR&limit=1000` | نیازمند توکن رایگان CF (در `.env`)؛ **مهم‌ترین منبع برای دامنه‌های غیر `.ir`** | ۱k+ |
| Tranco | `https://tranco-list.eu/top-1m.csv.zip` | فیلتر پسوند `.ir` | ۱۰–۲۰k |
| GitHub/Kaggle | clone/cloning ریپازیتوری‌های `iranian-domains` / `persian-domains` | در زمان اجرا با جستجو به‌روزرسانی شود | متغیر |

**خروجی فاز ۱:** `data/processed/seed_domains.csv` با ستون‌های `domain, sources, first_seen` + ثبت در جدول‌های `domains/sources`.

**دستور اجرا:** `python -m scripts.collect`

**Acceptance:** تعداد دامنه‌های یکتا ≥ ۲۰۰k؛ بدون تکرار؛ دامنه‌های بدون host معتبر حذف شوند.

---

## ۴. فاز ۲ — تشخیص ایرانی‌بودن (Classifier)

**fetcher:** httpx AsyncClient؛ `concurrency=50`؛ `timeout=15s`؛ دنبال‌کردن redirect؛ UA برابر `IrDomainBot/0.1 (research; github.com/Delta-Kronecker/IrDomain)`؛ فقط صفحه اصلی (حداکثر ۵۰۰KB).

**سیگنال‌ها (features):**

1. `persian_ratio` = نسبت حروف فارسی (U+0600–06FF, U+0750–077F, Presentation Forms) به کل حروف
2. `lang` از `<html lang>` و هدر `Content-Language`
3. توکن‌های ایرانی (وزن‌دار): «زرین‌پال/zarinpal»، «نماد اعتماد/namad/enamad»، «ساماندهی»، «به‌پرداخت ملت»، «بانک سامان/پارسیان/ملت»، `+98`/`۰۹`، «ایران»، دامنه‌های درگاه پرداخت در منابع صفحه
4. سیگنال منفی: `hreflang`های غیرفارسی، محتوای انگلیسی خالص

**امتیازدهی:**

```
ir_score = 0.55 * min(persian_ratio / 0.30, 1)
         + 0.30 * token_score          # نرمال‌شده بر اساس تعداد توکن‌های یافته‌شده
         + 0.15 * lang_score           # lang=fa → 1، fa-IR → 1، en → 0
verdict:  ir_score ≥ 0.60 → "iranian"
         0.35 ≤ ir_score < 0.60 → "uncertain"
         ir_score < 0.35 → "foreign"
```

همه سیگنال‌های خام در `token_hits`/`fetches` ذخیره می‌شوند (قابلیت audit و تنظیم مجدد آستانه بدون fetch مجدد).

**دستور اجرا:** `python -m scripts.classify`

**Acceptance:** پوشش ≥ ۹۰٪ دامنه‌های seed (بقیه = مرده/offline با برچسب `dead`)؛ لاگ خطاها در `logs/`.

---

## ۵. فاز ۳ — غنی‌سازی

- **WHOIS:** سرور `whois.nic.ir` برای `.ir`ها؛ برای دامنه‌های غیر `.ir` سرور whois مربوط به TLD؛ استخراج فقط `registrant country` و `registrar` (بدون ذخیره نام/تلفن اشخاص)؛ rate limit ملایم.
- **ASN:** resolve رکورد A → جستجو در دیتاست رایگان `iptoasn` (ASNهای ایرانی = سیگنال ضعیف).
- **رتبه:** ستون `rank_country` از Radar در صورت وجود.

**دستور اجرا:** `python -m scripts.enrich`

---

## ۶. فاز ۴ — خزش عمیق (پس از تثبیت دیتاست)

- Scrapy با کشف `sitemap.xml`، عمق ۲، تأخیر ≥ ۵ ثانیه per-domain، رعایت `robots.txt`
- جدول `links (src, dst)` → خروجی گراف لینک (فرمت WebGraph/CSV)
- زمان‌بندی دوره‌ای (هفتگی) برای بروزرسانی `last_seen`

---

## ۷. نقشه زمانی

| بازه | خروجی |
|---|---|
| روز ۱ | ساختار پروژه + فاز ۱ → `seed_domains.csv` |
| روز ۲ | فاز ۲ → `verdicts.csv` + گزارش آماری |
| روز ۳ | فاز ۳ → غنی‌سازی WHOIS/ASN + گزارش کیفیت |
| هفته ۲ | فاز ۴ (خزش عمیق و گراف لینک) |

---

## ۸. قرارداد اجرا در این مخزن

- تمام کد، طرح‌ها، اجراها و خروجی‌های کوچک (CSV تا چند مگابایت) در همین مخزن؛ `data/raw/`، `*.db`، `logs/` در `.gitignore`
- همه دستورها از ریشه مخزن و با `python -m scripts.<نام>` اجرا می‌شوند
- پیشرفت هر فاز در همین سند و در README گزارش می‌شود
- هر commit پیش از push بررسی می‌شود که توکن/کلیدی وارد آن نشده باشد

## ۹. نکات امنیتی

- توکن دسترسی گیت‌هاب فقط در `.git/config` محلی (URL ریموت) استفاده می‌شود و **هرگز کامیت نمی‌شود**
- توکنی که در گفتگو اشتراک‌گذاری شده پس از پایان کار باید **revoke و بازتولید** شود
- در `.env` (gitignored) فقط برای توکن‌های عمومی مثل Cloudflare Radar
