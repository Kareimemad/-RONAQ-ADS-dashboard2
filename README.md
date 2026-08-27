# نظام داشبورد Meta Ads الأوتوماتيكي

سيستم كامل شغال Cloud من غير سيرفر: بيسحب بيانات كل حساباتك الإعلانية من Meta Marketing API
يوميًا عن طريق GitHub Actions (مجاني)، ويحدّث داشبورد ويب ثابت على GitHub Pages (مجاني)
تفتحه وقت ما تحب وهو محدّث لوحده.

## هيكل المشروع

```
config/accounts.json         <- قايمة الحسابات وأرقامها (مش سري)
scripts/fetch_meta_ads.py    <- سكريبت السحب من Meta API
.github/workflows/daily-fetch.yml  <- الجدولة اليومية (Cron)
docs/index.html               <- الداشبورد (GitHub Pages بيعرض من هنا)
docs/data/*.json              <- البيانات، بتتحدث أوتوماتيك كل يوم
```

## خطوات التفعيل (مرة واحدة بس)

### 1) اعمل حساب GitHub (لو مالكش) وارفع المشروع ده كـ repo خاص (Private)
- روح github.com > New repository > اسمه مثلاً `meta-ads-dashboard` > Private
- ارفع كل الملفات دي عليه (drag & drop من واجهة GitHub، أو `git push` لو بتستخدم Git)

### 2) اعمل Meta App + System User Token (مرة واحدة، صالح دايمًا)
1. روح [developers.facebook.com/apps](https://developers.facebook.com/apps) واعمل App جديد، نوعه "Business"
2. من إعدادات الـ App، ضيف منتج **Marketing API**
3. روح [business.facebook.com](https://business.facebook.com) > Business Settings > **Users > System Users**
4. اعمل System User جديد (Admin access)، واربطه بكل الحسابات الإعلانية (ZITTZ, RONAQ, RIVANA... الخ) بصلاحية **Ads Read**
5. من نفس الشاشة، دوس **Generate New Token**، اختار الـ App اللي عملته، وحدد صلاحية `ads_read`
6. ده التوكن اللي هتستخدمه — **ماتشاركوش مع حد**، واحفظه في مكان آمن

> ملحوظة: توكن الـ System User ده بيفضل شغال طول ما الـ App والـ System User موجودين، مش بينتهي زي التوكن الشخصي العادي.

### 3) هات أرقام الحسابات الإعلانية (Ad Account ID)
من Meta Ads Manager، فوق شمال بيبان رقم الحساب بالشكل `act_1234567890`.
افتح `config/accounts.json` وحط كل رقم مكان الـ `act_XXXXXXXXXXXX` بتاعه.

### 4) ضيف التوكن كـ Secret في GitHub
في الـ repo بتاعك: **Settings > Secrets and variables > Actions > New repository secret**
- الاسم: `META_ACCESS_TOKEN`
- القيمة: التوكن اللي عملته في خطوة 2

### 5) فعّل GitHub Pages
**Settings > Pages** > Source: اختار `Deploy from a branch` > Branch: `main` > Folder: `/docs` > Save

هياخد كام دقيقة، وهتلاقي لينك الداشبورد ظاهر فوق (شكله يكون
`https://<username>.github.io/meta-ads-dashboard/`)

### 6) شغّل السحب أول مرة يدويًا
**Actions tab** > اختار workflow اسمه `Daily Meta Ads Fetch` > **Run workflow**
هيسحب آخر 30 يوم لكل حساب ويحطهم في `docs/data/`، وبعد كام دقيقة هتلاقي الداشبورد اتحدث لوحده.

بعد كده هيشتغل تلقائي كل يوم الساعة 4 صباحًا UTC (6-7 صباحًا بتوقيت القاهرة) من غير ما تعمل حاجة.

## تعديلات محتملة

- **تغيير نوع النتيجة المحسوبة**: السكريبت افتراضيًا بيحسب `purchase` كـ "أوردر". لو حساب معين بيقيس حاجة تانية، عدّل `PURCHASE_ACTION_TYPES` في `scripts/fetch_meta_ads.py`.
- **تغيير عدد أيام السحب**: غيّر `LOOKBACK_DAYS` في نفس الملف (افتراضي 30 يوم).
- **إضافة حساب جديد**: ضيف سطر جديد في `config/accounts.json` بس.
- **مستوى الحملة بدل الحساب**: السكريبت دلوقتي بيسحب على مستوى الحساب كله (`level: "account"`). لو عايز تفاصيل لكل حملة، غيّرها لـ `"campaign"` في `fetch_insights()` — بس هتحتاج تعدّل الداشبورد كمان يعرض تفصيل الحملات.

## تنبيه أمان

- ملف `config/accounts.json` مش فيه أي بيانات سرية (أرقام الحسابات مش سرية)، فمينفعش يتحط public لو الـ repo هيبقى public — بس عمومًا خليه Private عشان بيانات الأداء نفسها حساسة.
- التوكن (`META_ACCESS_TOKEN`) لازم يفضل Secret جوه GitHub بس، وممنوع يتحط في أي ملف كود.
