# 3xi

## تنظیم gRPC از زمان نصب و تولید کد در پنل اکسیر

در پنل `exir-web-panel` مسیر **زیرساخت ← نصب سرور** (`/server-install`) برای مدیر دارای `admin.manage` اضافه شده است. دیتاسنتر، روش SSH / cloud-init / StackScript / startup، دامنه اختیاری، مسیر gRPC، authority، حالت multi/gun، آدرس کلاینت، DNS، ظرفیت و لاگ را انتخاب کنید و کد نصب را کپی یا دانلود کنید. انتخاب پیش‌فرض هر فیلد و دکمه «بازگشت به پیش‌فرض‌ها» همیشه در دسترس است. فرم دستوری روی سرور اجرا نمی‌کند.

نمونه نصب با مقادیر دلخواه:

```bash
sudo bash install.sh --grpc-path /exir.v2.Tunnel/ --grpc-authority edge.example.com --grpc-mode multi
```

| گزینه | متغیر محیطی / فیلد StackScript | پیش‌فرض |
| --- | --- | --- |
| `--grpc-service-name` یا `--grpc-path` | `THREEXI_GRPC_SERVICE_NAME` | مقدار دیتابیس: `google.internal.analytics.v1.Tracker` |
| `--grpc-authority` | `THREEXI_GRPC_AUTHORITY` | حفظ مقدار دیتابیس |
| `--grpc-mode multi` یا `gun` | `THREEXI_GRPC_MODE` | مقدار دیتابیس: `multi` |
| `--public-address` | `THREEXI_PUBLIC_ADDRESS` | آدرس کلاینت در دیتابیس |
| `--performance-profile` | `THREEXI_PERFORMANCE_PROFILE` | `high` |
| `--nginx-logs` | `THREEXI_NGINX_LOGS` | `off` |

این گزینه‌ها برای `scripts/bootstrap.sh` هم کار می‌کنند؛ bootstrap گزینه `--dns-mode public` یا `preserve` هم دارد. فیلد خالی StackScript یعنی حفظ مقدار دیتابیس. گزینه صریح `--grpc-authority ''` مقدار Host را خالی می‌کند تا کلاینت SNI خودش را انتخاب کند. `3xi links --sni DOMAIN` از authority صریح زمان نصب استفاده می‌کند؛ با `--authority ''` می‌توان برای همان خروجی دوباره SNI کلاینت را انتخاب کرد.

منظور از authority، همان Host در HTTP/2 است، نه رمز یا UUID. کاربران، شناسه‌ها و آمار حفظ می‌شوند و فایل اصلی `x-ui.db` تغییر نمی‌کند؛ تنظیمات فقط روی نسخه نصب‌شده اعمال می‌شوند. مسیر انتخابی در Nginx و Xray هماهنگ است. نام سرویس یا `/name/` را بدهید؛ `/Tun` و `/TunMulti` را اضافه نکنید. مسیر واقعی برای مثال بالا `/exir.v2.Tunnel/TunMulti` است. مسیر چندبخشیِ سفارشی متد در این نصاب پشتیبانی نمی‌شود.

دامنه گواهی (`--domain`) مستقل از authority است. بدون دامنه، گواهی محلی و حالت Full؛ با دامنه، صدور Let’s Encrypt و Full (strict). انتخاب دیتاسنتر فقط روش خروجی را پیشنهاد می‌کند؛ فایروال و شبکه دیتاسنتر باید در کنسول خودش تنظیم شوند. اسکریپت تولیدشده DNS را قبل از دانلود اصلاح می‌کند و به‌صورت پیش‌فرض نسخه ثابت و سازگار 3xi را می‌گیرد؛ انتخاب `main` هم ممکن است.

این تنظیمات مخصوص نصب هستند. اجرای دوباره روی نصب کامل‌شده، بدون `--clean-install` آن را بازنویسی نمی‌کند. برای تغییر ظرفیت و لاگ سرور موجود، کد hot update انتهای همین راهنما را اجرا کنید.

ترکیب نصب و تنظیمات سیستم **xrm-1** با درگاه **Nginx + gRPC در XUPDATE** و سایت چندرسانه‌ای جدید **3xi Atlas**. دو مخزن قدیمی مستقل می‌مانند.

[English](README.md) · [فایل‌های راه‌اندازی ابری](cloud-init/README.fa.md) · [نتایج آزمون](VALIDATION.md) · [منابع تصاویر و رسانه](website/ASSETS.md)

## انتخاب روش نصب

| روش / دیتاسنتر | فایل آماده | محل استفاده |
| --- | --- | --- |
| نصب با SSH | [`install.sh`](install.sh) | ابتدا مخزن را clone کن و نصب‌کننده را اجرا کن |
| اسکریپت مستقل | [`scripts/bootstrap.sh`](scripts/bootstrap.sh) | دریافت پروژه، بررسی checksum و اجرای نصب |
| Linode / Akamai | [`stackscript.sh`](stackscript.sh) | **کل محتوای فایل** را داخل StackScript قرار بده؛ فیلدهای اختیاری آماده‌اند |
| AWS EC2 / Lightsail | [`aws.sh`](aws.sh) | Shell user-data یا launch script |
| Google Compute Engine | [`providers/gcp-startup.sh`](providers/gcp-startup.sh) | Startup script؛ اجرای مجدد بعد از نصب، دیتابیس را بازنویسی نمی‌کند |
| Vultr | [`providers/vultr-startup.sh`](providers/vultr-startup.sh) | Boot/startup script |
| Hetzner، DigitalOcean، OVH/OpenStack، Oracle، Scaleway، UpCloud | [`cloud-init/3xi.yaml`](cloud-init/3xi.yaml) | بخش cloud-init / user-data ایمیج لینوکس |
| Azure | [`cloud-init/3xi.yaml`](cloud-init/3xi.yaml) | Custom data روی ایمیج دارای cloud-init |

سیستم موردنیاز: **Ubuntu 24.04 به بعد یا Debian 12 به بعد**، دارای systemd، معماری amd64 یا arm64 و دسترسی root. خروجی DNS/HTTPS/APT و ورودی TCP **80 و 443** باید برقرار باشد. فایروال و Security Group دیتاسنتر را از پنل همان ارائه‌دهنده تنظیم کن. اگر از XHTTPهای قبلی هم استفاده می‌کنی، پورت‌های آن‌ها جداگانه لازم‌اند.

## نصب معمولی، بدون دامنه

```bash
git clone https://github.com/exirhub/3xi.git
cd 3xi
sudo bash install.sh
```

در این حالت نصب هیچ دامنه، SNI، authority، کلید، گواهی یا توکن Cloudflare از تو نمی‌خواهد. روی هر سرور یک کلید و گواهی self-signed جداگانه ساخته می‌شود. در Cloudflare:

1. دامنهٔ موردنظر را با **Orange Cloud / Proxied** به IP سرور وصل کن.
2. حالت SSL/TLS را روی **Full** بگذار.
3. در بخش Network، گزینهٔ **gRPC** را روشن کن.
4. SNI و authority را در کلاینت، مطابق دامنهٔ انتخابی خودت قرار بده.

Nginx وابسته به یک دامنه نیست. دامنه‌های مختلفی که درست به همین سرور متصل شده‌اند، از همان سایت و درگاه استفاده می‌کنند. احراز هویت VLESS و UUID کاربران همچنان لازم است.

## نصب با گواهی معتبر برای دامنهٔ اختیاری

```bash
sudo bash install.sh --domain your-domain.example
```

به‌جای `your-domain.example` دامنهٔ واقعی خودت را بنویس. گواهی **Let’s Encrypt** خودکار برای همان دامنه صادر و تمدید می‌شود؛ در این حالت می‌توانی از **Full (strict)** استفاده کنی. ایمیل اختیاری است:

```bash
sudo bash install.sh --domain your-domain.example --acme-email admin@your-domain.example
```

برای صدور اولیه، DNS دامنه باید به همین سرور برسد و مسیر `/.well-known/acme-challenge/` روی پورت ۸۰ در دسترس باشد. می‌توانی موقع صدور اولیه ابر را موقتاً DNS-only کنی؛ یا مطمئن شوی Cloudflare این مسیر HTTP را بدون انتقال اجباری به HTTPS، چالش یا مسدودسازی WAF به سرور می‌فرستد. رکورد A/AAAA اشتباه، صدور گواهی را متوقف می‌کند. بعد از صدور، Orange Cloud و Full (strict) را فعال کن.

اگر دامنه داده باشی و صدور گواهی ناموفق شود، نصب **خطا می‌دهد و به self-signed برنمی‌گردد**. صدور پیش از حذف فایل‌های نصب قبلی انجام می‌شود؛ سرویس‌های مدیریت‌شده ممکن است موقتاً برای آزاد شدن پورت ۸۰ متوقف شوند و در صورت شکست دوباره بالا می‌آیند. انتخاب این حالت، ایجاد حساب ACME و پذیرش توافق‌نامهٔ Let’s Encrypt را دربر دارد؛ بدون ایمیل، حساب بدون نشانی تماس ثبت می‌شود.

## حذف نصب قبلی و نصب تازه بدون بکاپ

```bash
sudo bash install.sh --clean-install
```

همراه با دامنهٔ اختیاری:

```bash
sudo bash install.sh --clean-install --domain your-domain.example
```

حالت clean نصب قبلی x-ui و درگاه‌های شناخته‌شدهٔ XUPDATE/3xi/xrm-site را از مسیرهای نصب سرور حذف می‌کند و دیتابیس همراه پروژه را وارد می‌کند؛ **از دیتابیس قبلی بکاپ نمی‌گیرد**. این فرمان را از مسیرهایی مانند `~/3xi` اجرا کن، نه از `/opt/3xi` یا مسیر نصب قبلی که قرار است حذف شود. سورس مخزن‌های قدیمی خارج از مسیرهای مدیریت‌شده پاک نمی‌شود.

اجرای مجدد بدون `--clean-install` روی یک نصب کامل، فقط سلامت را بررسی می‌کند؛ دیتابیس دوباره وارد نمی‌شود و حالت گواهی عوض نمی‌شود. نصب تازهٔ بدون clean یک کپی از seed ورودی زیر `/var/backups/3xi` نگه می‌دارد؛ clean چنین بکاپی ندارد. تنظیمات سیستم مثل DNS، swap، UFW و TCP با حذف برنامه به حالت قبل برنمی‌گردند.

## StackScript

کل فایل [`stackscript.sh`](stackscript.sh) را در StackScript دیتاسنتر Linode/Akamai قرار بده. فیلدها:

| فیلد | پیش‌فرض | کاربرد |
| --- | --- | --- |
| `THREEXI_REF` | `main` | نام branch، tag یا SHA کامل commit |
| `THREEXI_DOMAIN` | خالی | خالی: گواهی محلی / دارای دامنه: Let’s Encrypt |
| `THREEXI_ACME_EMAIL` | خالی | ایمیل اختیاری برای ACME |
| `THREEXI_DNS_MODE` | `public` | DNS عمومی مانند xrm؛ با `preserve` DNS دیتاسنتر حفظ می‌شود |
| `THREEXI_CLEAN_INSTALL` | `0` | مقدار `1` یعنی حذف نصب قبلی بدون بکاپ |

برای دامنه‌های متغیر، فیلد دامنه را خالی بگذار. برای گواهی معتبر، فقط همان فیلد را پر کن؛ نصب‌کننده و مسیر مدیریت یکسان است.

## cloud-init

**کل فایل** [`cloud-init/3xi.yaml`](cloud-init/3xi.yaml) را در User Data قرار بده. انتهای آن به‌طور پیش‌فرض این است:

```yaml
runcmd:
  - [bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main]
```

برای گواهی معتبر، فقط فرمان انتهایی را تغییر بده:

```yaml
runcmd:
  - [bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main, --domain, your-domain.example]
```

برای حفظ DNS دیتاسنتر:

```yaml
runcmd:
  - [env, THREEXI_DNS_MODE=preserve, bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main]
```

این قطعه‌ها جایگزین بخش `runcmd` در فایل کامل هستند؛ به‌تنهایی فایل نصب نیستند. برای جایگزینی نصب قبلی، `--clean-install` را هم به همان فهرست اضافه کن. فایل کامل، کد تنظیم DNS و bootstrap را در خود دارد؛ بنابراین تنظیم DNS **قبل از APT و دانلود GitHub** انجام می‌شود. حجم آن کمتر از 16 KiB است. کاربران SSH، کلیدهای SSH و تنظیم اینترفیس‌های شبکه بازنویسی نمی‌شوند.

در `aws.sh`، اسکریپت GCP یا Vultr هم می‌توانی بعد از خط اول اضافه کنی:

```bash
export THREEXI_DOMAIN=your-domain.example
export THREEXI_ACME_EMAIL=admin@your-domain.example
```

نبود متغیر دامنه یعنی حالت پیش‌فرضِ بدون وابستگی به دامنه. تمام روش‌ها از همان نسخهٔ نصب‌کننده، دیتابیس، checksum و کنترل اجرای مجدد استفاده می‌کنند.

## نصب با bootstrap دانلودی

```bash
curl -fL --retry 3 https://raw.githubusercontent.com/exirhub/3xi/main/scripts/bootstrap.sh -o /tmp/3xi-bootstrap.sh
sudo bash /tmp/3xi-bootstrap.sh
```

گزینه‌های `--domain`، `--acme-email`، `--ref` و `--clean-install` قابل استفاده‌اند. اگر DNS از ابتدا خراب است و حتی `curl` یا `git` اجرا نمی‌شود، کل cloud-init یا StackScript را در پنل دیتاسنتر قرار بده؛ اسکریپت پیش از دانلودشدن نمی‌تواند DNS را اصلاح کند.

## پنل x-ui، سایت و کانفیگ کلاینت

```bash
sudo x-ui
sudo cat /etc/3xi/access.txt
sudo 3xi doctor
```

`x-ui` منوی ترمینالی رسمی نسخهٔ پین‌شده است. سایت در ریشهٔ دامنه باز می‌شود: `https://YOUR-PROXIED-DOMAIN/`. برای پنل، مسیر ثبت‌شده در `access.txt` را به انتهای همان دامنه اضافه کن. نام کاربری و رمز پنل از دیتابیس ارسالی حفظ می‌شوند.

برای ساخت لینک واقعی کاربران gRPC، با UUID موجود در دیتابیس نصب‌شده:

```bash
sudo 3xi links --sni your-domain.example
```

با IP مشخص Cloudflare و authority دلخواه:

```bash
sudo 3xi links --sni your-domain.example --authority your-domain.example --address 188.114.97.6
```

این فرمان فقط لینک‌ها را چاپ می‌کند و دیتابیس یا درگاه را تغییر نمی‌دهد. دامنهٔ انتخابی باید در Cloudflare معتبر، Proxied و متصل به این سرور باشد. معمولاً SNI و authority را یکسان قرار بده.

| فیلد کلاینت | مقدار |
| --- | --- |
| Protocol | VLESS |
| Port | `443` |
| Transport | **gRPC** |
| TLS | روشن؛ اعتبارسنجی عادی گواهی سمت کلاینت روشن می‌ماند |
| SNI / authority | دامنهٔ Proxied انتخابی تو |
| ALPN | `h2` |
| Fingerprint | `chrome` |
| serviceName | `google.internal.analytics.v1.Tracker` |
| Mode | `multi` |
| مسیر درخواست gRPC | `/google.internal.analytics.v1.Tracker/TunMulti` |

در فیلد serviceName کلاینت فقط نام سرویس را بنویس؛ `/` اول یا `/TunMulti` آخر را به آن اضافه نکن.

## دیتابیس همراه پروژه

فایل [`x-ui.db`](x-ui.db) دقیقاً همان `51.83.251.103_2026-09-25_053713.db` ارسالی، با حجم **1,003,520 بایت** است. checksum در [`x-ui.db.sha256`](x-ui.db.sha256) ثبت شده است. این فایل شامل یک کاربر پنل، هشت رکورد کلاینت، دوازده اتصال کلاینت به inbound، شش inbound فعال و یک Host است.

| بخش | رفتار در نصب جدید |
| --- | --- |
| gRPC با ID 14 | `127.0.0.1:10001` پشت Nginx روی 443 |
| پنج XHTTP موجود | پورت‌های `2082`، `2083`، `2084`، `2087` و `8080` و تنظیماتشان حفظ می‌شوند |
| کاربران، UUID، آمار، توکن‌ها، routing | حفظ می‌شوند |
| پنل و subscription | روی loopback؛ TLS در Nginx خاتمه پیدا می‌کند |

فایل داخل مخزن تغییر نمی‌کند. نصب، کپی اجرایی `/etc/x-ui/x-ui.db` را برای درگاه آماده می‌کند. Host موجود تکراری ساخته نمی‌شود؛ در حالت دامنهٔ صریح، SNI/host آن به دامنهٔ داده‌شده تغییر می‌کند. مسیر اصلی پنل همان مسیر دیتابیس است.

گواهی موجود در inbound دیگرِ XHTTP برای Nginx جدید استفاده نمی‌شود؛ همان‌طور که هست در تنظیمات XHTTP می‌ماند. تولید و تمدید گواهی 3xi فقط مربوط به **فرانت‌اند 443** است.

## رفتار سیستم، مطابق xrm-1

| مورد | پیش‌فرض | گزینهٔ جایگزین |
| --- | --- | --- |
| DNS | `1.1.1.1`، `8.8.8.8`، `9.9.9.9` و دسترسی `0644` برای resolv.conf | `THREEXI_DNS_MODE=preserve` |
| UFW | غیرفعال می‌شود | `THREEXI_FIREWALL_MODE=preserve` |
| Swap | اگر swap فعالی نباشد، فایل 1 GiB ایجاد می‌شود؛ فایل نامرتبط بازنویسی نمی‌شود | `THREEXI_SWAP=0` |
| TCP | بافرهای 64 MiB، backlog برابر 100000، keepalive برابر 60/10/6 | فایل `/etc/sysctl.d/99-3xi-network.conf` |

مثال حفظ DNS و فایروال دیتاسنتر و ردکردن ایجاد swap:

```bash
sudo env THREEXI_DNS_MODE=preserve THREEXI_FIREWALL_MODE=preserve THREEXI_SWAP=0 bash install.sh
```

Nginx اختصاصی با نام `threexi-nginx.service` پورت‌های 80 و 443 را می‌گیرد. سایت، gRPC، پنل و مسیرهای subscription در همان درگاه تفکیک می‌شوند. سرویس معمولی `nginx.service` نباید هم‌زمان برای همین پورت‌ها اجرا شود.

## دو حالت گواهی و تمدید

| نصب اولیه | گواهی origin | تنظیم Cloudflare |
| --- | --- | --- |
| بدون `--domain` | self-signed با کلید تازه روی خود سرور | **Full** |
| با `--domain` | Let’s Encrypt برای همان دامنه | **Full (strict)** |

کلاینت در هر دو حالت، گواهی لبهٔ Cloudflare را می‌بیند. Full ارتباط origin را رمز می‌کند ولی اعتبار گواهی origin را بررسی نمی‌کند؛ Strict بررسی می‌کند. بازکردن مستقیم IP سرور با گواهی محلی، اخطار اعتماد مرورگر خواهد داشت. اگر در حالت Strict دامنه را عوض کنی، گواهی باید نام جدید را هم پوشش بدهد.

`threexi-tls.timer` روزانه بررسی می‌کند. گواهی محلی زمانی که کمتر از ۳۰ روز اعتبار داشته باشد، جایگزین می‌شود. Let’s Encrypt طبق سیاست Certbot و با webroot تمدید می‌شود. اطلاعات ACME در `/etc/3xi-acme` باقی می‌ماند تا clean-install موجب صدور بی‌دلیل دوباره نشود. پس از اعتبارسنجی گواهی جدید، Nginx با reload آرام به‌روزرسانی می‌شود؛ اگر reload شکست بخورد، جفت قبلی برمی‌گردد.

```bash
sudo 3xi renew
systemctl list-timers threexi-tls.timer
```

برای گواهی درگاه از `3xi renew` استفاده کن؛ فیلدهای گواهی داخلی پنل باید خالی بمانند. نصب بدون دامنه نیازی به ارتباط با ACME ندارد. منابع رسمی: [Full](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full/)، [Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)، [gRPC](https://developers.cloudflare.com/network/grpc-connections/)، [Certbot](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot).

## سایت چندرسانه‌ای

**3xi Atlas** شامل سه منظرهٔ دیجیتال اختصاصی، سه فیلم ۱۶ثانیه‌ای H.264/AAC، سه قطعهٔ موسیقی ambient حدود ۶۴ثانیه‌ای، مقاله‌های خواندنی، گالری با کنترل صفحه‌کلید، ذخیرهٔ علاقه‌مندی‌ها، پلیر موسیقی و منوی موبایل است. تمام فایل‌ها محلی هستند و روی سرور به build یا CDN فایل‌های رابط نیاز نیست.

فیلم‌ها حرکت آرام روی تصاویر دیجیتال‌اند و موسیقی‌ها اختصاصی و مصنوعی ساخته شده‌اند. پخش پس از انتخاب کاربر شروع می‌شود. ترافیک جعلی، بازدیدکنندهٔ ساختگی یا درخواست‌های پس‌زمینه برای بالا بردن آمار ساخته نمی‌شود.

## افزایش ظرفیت اتصال gRPC

برای تغییری که **فقط Nginx** را به‌روزرسانی کند، از [کد hot update در انتهای همین راهنما](#nginx-hot-update) استفاده کن.

نصب‌های جدید از پروفایل **high** استفاده می‌کنند. برای اعمال روی نصب فعلی، داخل پوشهٔ clone پروژه اجرا کن:

```bash
git pull --ff-only
sudo python3 -m threexi tune --profile high --nginx-logs off
```

| تنظیم | نصب قبلی | standard | high، پیش‌فرض جدید |
| --- | --- | --- | --- |
| اتصال هر worker در Nginx | 4096 | 16384 | **65536** |
| سقف فایل باز Nginx و سرویس Xray | 65536 | 131072 | **262144** |
| استریم هم‌زمان هر اتصال HTTP/2 | 128 | 128 | **256** |
| نوشتن لاگ Nginx در فایل | فعال | پیش‌فرض خاموش | **پیش‌فرض خاموش** |

فرمان ابتدا `nginx -t` را روی تنظیم پیشنهادی اجرا می‌کند، سقف فایل‌های باز پردازش‌های زنده و فرزندانشان را بالا می‌برد، تنظیمات systemd و پروفایل را ذخیره می‌کند، ماژول‌های مدیریت تنظیمات در `/opt/3xi` را ارتقا می‌دهد و Nginx را با reload آرام به‌روزرسانی می‌کند. **Xray ری‌استارت نمی‌شود و دیتابیس دوباره وارد نمی‌شود.** تایمر `refresh` مقادیر جدید را حفظ می‌کند؛ اجرای تکراری با همان تنظیمات، reload بی‌دلیل ندارد.

لاگ‌ها پیش‌فرض خاموش‌اند: `access_log off;` و `error_log /dev/null emerg;`. برای درخواست‌های معمول رکورد access log ساخته نمی‌شود و خطاهای زمان اجرای Nginx در فایل نوشته نمی‌شوند. از `error_log off;` استفاده نشده، چون Nginx کلمهٔ `off` را نام فایل در نظر می‌گیرد. انتخاب لاگ بعد از refresh و reboot حفظ می‌شود؛ فقط با `--nginx-logs on` دوباره فعال می‌شود. workerهای قدیمی که اتصال در حال تخلیه دارند ممکن است آن اتصال را با تنظیم قبلی تمام کنند؛ پیام‌های بررسی `nginx -t` و وضعیت systemd باقی می‌مانند.

برای پیش‌نمایش `--dry-run` اضافه کن. بعد از اجرای نخست، `sudo 3xi tune --profile high` هم در دسترس است. گزینه‌های عددی `--worker-connections`، `--nofile` و `--h2-streams` قابل تنظیم‌اند. برای سرور کوچک‌تر می‌توانی `--profile standard` انتخاب کنی؛ افزایش سقف‌ها در بار واقعی حافظهٔ بیشتری مصرف می‌کند. سقف زنده‌ای که از مقدار انتخابی بالاتر باشد کم نمی‌شود؛ انتخاب پروفایل کوچک‌تر، سقف سرویس‌ها و workerهای بعدی را تغییر می‌دهد.

فرمان با نصب و refresh قفل مشترک دارد؛ سقف کرنل و systemd را بررسی می‌کند و تغییر دستی نامرتبط در nginx.conf را بازنویسی نمی‌کند. در صورت خطا، فایل‌ها و سقف‌های زندهٔ تغییرکرده برگردانده می‌شوند؛ اگر بازگردانی کامل نباشد، صریحاً اعلام می‌شود. افزایش زندهٔ hard limit به مجوز سیستم‌عامل، معمولاً `CAP_SYS_RESOURCE` روی سرور میزبان، نیاز دارد؛ در صورت نبود مجوز، ری‌استارت خودکار انجام نمی‌شود.

برای نصب جدید می‌توانی `sudo bash install.sh --performance-profile standard` بدهی؛ بدون این گزینه، `high` انتخاب می‌شود، از جمله در cloud-init و StackScript. لاگ در هر دو پروفایل پیش‌فرض خاموش است و با `--nginx-logs on` فعال می‌شود. `git pull` یا اجرای دوبارهٔ نصبِ کامل‌شده، به‌تنهایی تنظیم نصب فعلی را عوض نمی‌کند؛ فرمان `tune` بالا لازم است.

**ظرفیت اتصال با پهنای باند یکی نیست.** در Nginx پروژه سقف سرعت ۲۰ مگابایت‌برثانیه تنظیم نشده است. اگر واحد MB/s باشد، ۲۰ تقریباً ۱۶۰ مگابیت‌برثانیه و ۴۰ تا ۷۰ تقریباً ۳۲۰ تا ۵۶۰ مگابیت‌برثانیه است. افزایش این سقف‌ها رسیدن به آن سرعت را تضمین نمی‌کند؛ توان سرور، لینک دیتاسنتر، ترکیب ترافیک و مسیر CDN مؤثرند. این فرمان timeout، ترنسپورت Xray، مسیرها و گواهی را تغییر نمی‌دهد.

## خطای EOF و تعداد اتصال زیاد

**حتی پروفایل high برای ۱۰۰ هزار اتصال هم‌زمان تأیید نشده و تست بار نشده است.** نصب‌های قبلی تا اجرای `tune` مقادیر قدیمی را حفظ می‌کنند. اتصال TCP داخلی به یک آدرس/پورت ثابت همچنان محدودیت پورت موقت دارد. عدد `netdev_max_backlog=100000` اندازهٔ صف بسته‌هاست، نه ظرفیت اتصال. تعداد کاربران، سوکت‌های TCP و استریم‌های gRPC یکسان نیستند.

هنگام بروز قطع‌ووصلی، از پوشهٔ clone پروژه اجرا کن:

```bash
git pull --ff-only
sudo python3 scripts/diagnose-capacity.py
```

گزارش، سقف و مصرف واقعی فایل‌های بازِ پردازش‌ها، RAM، CPU، اتصال‌های TCP، بازهٔ پورت موقت و خطاهای اخیر را نشان می‌دهد. **سرویس ری‌استارت نمی‌شود و دیتابیس یا تنظیمات شبکه تغییر نمی‌کند.** نصب مجدد یا `--clean-install` لازم نیست. حتی اگر نسخهٔ نصب‌شده در `/opt/3xi` قدیمی باشد، این ابزار مستقل از داخل clone اجرا می‌شود.

خروجی را همراه متن دقیق خطای کلاینت، ساعت و منطقهٔ زمانی آن، نسخهٔ کلاینت و core بفرست. پنجرهٔ پیش‌فرض لاگ ۳۰ دقیقه است، ولی فقط انتهای محدود فایل خوانده می‌شود؛ نبود خطا در گزارش، سالم‌بودن قطعی همهٔ مسیر را ثابت نمی‌کند. افزایش timeout در Nginx، محدودیت‌های Cloudflare را تغییر نمی‌دهد.

[تحلیل ظرفیت، معنی خطاها و برنامهٔ آزمون ۱۰۰ هزار اتصال](docs/CAPACITY.md) شامل بررسی سوکت Unix یا چند backend، محدودیت فایل‌های باز، پهنای باند، توزیع بار و آزمون واقعی VLESS است؛ این تغییرها هنوز به تنظیم عملیاتی اعمال نشده‌اند.

## بررسی و رفع اشکال

```bash
sudo 3xi doctor
sudo 3xi doctor --public your-domain.example
sudo bash scripts/diagnose.sh
sudo nginx -t -c /etc/3xi/nginx.conf
sudo systemctl status x-ui threexi-nginx --no-pager
sudo journalctl -u x-ui -u threexi-nginx -n 80 --no-pager
sudo ss -lntp '( sport = :80 or sport = :443 or sport = :10001 )'
```

| خطا | بررسی لازم |
| --- | --- |
| APT: `Temporary failure resolving` | تست DNS با کاربر `_apt` و خوانابودن `/etc/resolv.conf`؛ `scripts/dns.sh` تنظیم عمومی را دوباره اعمال می‌کند. اگر دیتاسنتر DNS عمومی را مسدود کرده، از DNS خودش و حالت `preserve` استفاده کن. |
| اشغال پورت 80 توسط nginx | معمولاً مالک درست، `threexi-nginx` است؛ دو Nginx را هم‌زمان اجرا نکن. |
| Cloudflare 526 | self-signed به Full نیاز دارد؛ Strict گواهی معتبر مطابق نام می‌خواهد. |
| Cloudflare 521/525 | IP origin، پورت 443، فایروال دیتاسنتر، سرویس Nginx و TLS را بررسی کن. timeout بلند، اتصال TCP ردشده را درست نمی‌کند. |
| gRPC 403 | gRPC دامنه و رخدادهای امنیتی/قواعد Cloudflare را بررسی کن. |
| preface / reset | SNI، authority، ALPN، TLS و serviceName را تطبیق بده. خود این خطا به‌تنهایی علت را ثابت نمی‌کند. |
| شکست صدور گواهی | `/var/log/3xi-acme/letsencrypt.log`، رکوردهای A/AAAA، پورت 80 و مسیر challenge را بررسی کن. |

آزمون DNS از دید APT:

```bash
sudo -u _apt getent ahosts security.ubuntu.com
sudo chmod 0644 /etc/resolv.conf
```

لاگ bootstrap: `/var/log/3xi-bootstrap.log`؛ لاگ cloud-init: `/var/log/cloud-init-output.log`؛ SHA نسخهٔ نصب‌شده: `/var/lib/3xi-bootstrap/source-commit.txt`؛ وضعیت نصب: `/etc/3xi/installed.json`.

تایمر `3xi refresh` تغییر serviceName را پس از اعتبارسنجی با Nginx هماهنگ می‌کند. inbound مدیریت‌شده باید روی loopback و پورت 10001، با `grpc` و `security: none` بماند. تغییر مسیر/پورت پنل یا TLS داخلی به تنظیم متناظر درگاه نیاز دارد.

## آزمون و توسعه

```bash
python3 -m unittest discover -s tests -v
python3 scripts/render-cloud-init.py --check
bash -n install.sh
node --check website/assets/site.js
python3 -m threexi render --output /tmp/3xi-preview
```

فرمان render فقط پوشهٔ خروجی تازه می‌سازد؛ نصب و دست‌کاری سرویس‌ها انجام نمی‌دهد. گواهی مورد استفاده در preview دامنه‌دار موقتی است؛ صدور معتبر هنگام نصب اجرا می‌شود. نصب‌کننده پیش از حذف برنامهٔ قبلی، checksum آرشیو، کانفیگ Xray و کانفیگ Nginx را بررسی می‌کند.

نسخهٔ پنل و منوی ترمینالی روی **3x-ui v3.8.5** پین شده است. نتیجهٔ آزمون‌ها و مرز بررسی واقعی را در [`VALIDATION.md`](VALIDATION.md) بخوان. نمایش محتوای وب و timeoutهای درگاه، تضمین بلاک‌نشدن یا نامرئی‌بودن ترافیک نیست.

<a id="nginx-hot-update"></a>

## Hot update فقط برای Nginx روی نصب فعلی

کد زیر را روی **سروری که 3xi از قبل نصب شده** اجرا کن. برای نصب‌های cloud-init و StackScript هم کار می‌کند؛ به پوشهٔ clone یا نصب پکیج جدید نیاز ندارد. نسخهٔ فعلی پروژه موقتاً دانلود می‌شود و فقط مقادیر جدید Nginx اعمال می‌شوند:

- اتصال هر worker: `65536`؛ سقف فایل باز worker و سرویس Nginx: `262144`.
- استریم هم‌زمان هر اتصال HTTP/2: `256`؛ access log خاموش؛ error log به `/dev/null` با سطح `emerg`.
- **دامنه، SNI/authority، گواهی، پورت‌ها، مسیر gRPC، تنظیمات پنل، کاربران و آمار مصرف حفظ می‌شوند. سرویس Xray و سقف زندهٔ آن تغییر نمی‌کنند و ری‌استارت نمی‌شود.**

تنظیمات در مدیریت پروژه هم ثبت می‌شوند تا تایمر refresh آن‌ها را برنگرداند. ابتدا `nginx -t` اجرا می‌شود، سقف‌های زندهٔ Nginx بالا می‌روند و سپس reload آرام انجام می‌شود. در صورت شکست اعمال، تنظیمات قبلی بازگردانده می‌شوند. این کد `install.sh` را اجرا نمی‌کند و `x-ui.db` را وارد نمی‌کند.

```bash
sudo bash <<'BASH'
set -Eeuo pipefail
if [[ ! -f /etc/3xi/installed.json ]]; then
    echo "An existing 3xi installation is required." >&2
    exit 1
fi
update_dir="$(mktemp -d /var/tmp/3xi-nginx-update.XXXXXX)"
trap 'rm -rf -- "$update_dir"' EXIT
curl -fL --retry 5 --retry-delay 2 --connect-timeout 15 --max-time 180 \
    https://codeload.github.com/exirhub/3xi/tar.gz/refs/heads/main \
    -o "$update_dir/source.tar.gz"
mkdir "$update_dir/source"
tar -xzf "$update_dir/source.tar.gz" --strip-components=1 --no-same-owner -C "$update_dir/source"
bash "$update_dir/source/scripts/hot-update-nginx.sh"
BASH
```

اگر پوشهٔ clone را داری، معادل کوتاه آن در همان پوشه `git pull --ff-only && sudo bash scripts/hot-update-nginx.sh` است. برای پیش‌نمایش، `--dry-run` را به فراخوانی اسکریپت اضافه کن. این اعداد سقف هم‌زمانی‌اند؛ تضمین سرعت ثابت ۴۰ تا ۷۰ مگابایت‌برثانیه یا ظرفیت ۱۰۰ هزار نشست نیستند.
