# راه‌اندازی در دیتاسنترها

فهرست کامل فایل‌ها، گزینه‌ها و فرمان‌ها در [README فارسی](../README.fa.md) آمده است. برای هر دیتاسنتر **کل فایل** را در قسمت مربوط قرار بده:

| دیتاسنتر | فایل |
| --- | --- |
| Linode / Akamai | [`stackscript.sh`](../stackscript.sh) |
| AWS EC2 / Lightsail | [`aws.sh`](../aws.sh) |
| Google Cloud | [`providers/gcp-startup.sh`](../providers/gcp-startup.sh) |
| Vultr | [`providers/vultr-startup.sh`](../providers/vultr-startup.sh) |
| Hetzner، DigitalOcean، OVH، Oracle، Scaleway، UpCloud، Azure | [`3xi.yaml`](3xi.yaml) روی ایمیج دارای cloud-init |
| VPS معمولی | [`bootstrap.sh`](../scripts/bootstrap.sh) |

سیستم: Ubuntu 24.04+ یا Debian 12+، systemd، amd64/arm64. دامنه اختیاری است: خالی یعنی **گواهی محلی + Full**؛ دارای دامنه یعنی **Let’s Encrypt + Full (strict)** برای همان نام. توکن Cloudflare لازم نیست.

در StackScript فیلد `THREEXI_DOMAIN` را پر کن یا خالی بگذار. در فایل کامل cloud-init فقط فرمان پایانی را برای صدور معتبر تغییر بده:

```yaml
runcmd:
  - [bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main, --domain, your-domain.example]
```

در حالت بدون دامنه، جفت `--domain` و مقدارش را حذف کن. افزودن `--clean-install` یعنی حذف عمدی نصب قبلی بدون بکاپ. بخش `write_files` در فایل کامل همچنان لازم است. برای حفظ DNS دیتاسنتر، ابتدای فهرست فرمان از `env, THREEXI_DNS_MODE=preserve` استفاده کن؛ مثال کامل در README اصلی است.

در اسکریپت شل هم می‌توانی بعد از shebang اضافه کنی:

```bash
export THREEXI_DOMAIN=your-domain.example
export THREEXI_ACME_EMAIL=admin@your-domain.example
```

اگر دامنه داده شود، DNS و مسیر HTTP-01 پورت ۸۰ باید آماده باشند. اصلاح DNS پیش از APT/GitHub اجرا می‌شود و نصب کامل در اجرای بعدی startup تکرار نمی‌شود. checksum دیتابیس و SHA سورس بررسی/ثبت می‌شوند.

```bash
sudo cloud-init status --long
sudo tail -n 80 /var/log/3xi-bootstrap.log
sudo cat /etc/3xi/access.txt
sudo x-ui
sudo 3xi doctor
```
