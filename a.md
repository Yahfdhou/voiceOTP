# VoiceOTP Gateway — ما طُلب، ما أُنجز، وكيف تستفيد منه خدمة أخرى

> ملف داخلي للطالب: تقييم صادق أمام الأستاذ + دليل إدماج للأنظمة الخارجية.  
> الواجهة الإدارية بالفرنسية. المنتج هو **Web Service** وليس تطبيق الهاتف ذي الشاشات الأربع.  
> آخر تحديث: أغسطس 2026 — يشمل الحصص اليومية، نافذة الوصول الشهرية، المفاتيح التجريبية، حذف الشركة، ومراقبة الأرصدة.

---

## 1. هل نفّذت ما طلبه الأستاذ بشكل حقيقي؟

**نعم، بالنسبة للعرض الجامعي / المختبر: الطلب الأساسي مُنفَّذ بشكل حقيقي، وليس مجرد شاشات تجميل.**

ما طلبه الأستاذ (الروح):

- المنتج = **خدمة ويب** تُدمج في حلول أخرى، وليست الشاشات الأربع وحدها.
- تصور **مضبوط وآمن على شكل حساب** (compte): كل شركة لها مفتاح، خطة، حصص، وإمكانية القطع.
- المختبر محلي؛ البيع لاحقاً يحتاج VPS + HTTPS.
- الصوت اليوم = امتداد Linphone `1000` على الشبكة المحلية **أو** جذع SIP (Telnyx) إن ضُبط `VOICE_PROVIDER=trunk`. بدون رقم أمريكي مُشترى ومُفعَّل، المكالمة للجوال الحقيقي غير جاهزة تجارياً.

ما يوجد فعلياً اليوم:

| طلب الأستاذ / النقص السابق | الحالة | أين |
|---|---|---|
| Web Service (4 endpoints) | منجز | Flask `POST /v1/otp/voice\|sms\|email` + `/v1/otp/verify` |
| لوحة إدارة الشركات والمفاتيح | منجز | Nuxt `http://localhost:3000/accounts` |
| تعطيل شركة فوراً | منجز | زر **Désactiver** → `403 account_revoked` |
| إعادة تفعيل | منجز | زر **Réactiver** |
| **حذف شركة نهائياً** | منجز | زر **Supprimer** → `DELETE /admin/partners/:id` (المفاتيح تموت، سجلات OTP تبقى) |
| إحصائيات لكل شركة | منجز | صفحة `/accounts/:id` + عمود الطلبات (`partner_id`) |
| Rate limiting لكل شركة | منجز | 20 طلب / 5 دقائق حسب `X-Api-Key` + سقف يومي حسب الخطة |
| **حصص يومية + رصيد متبقٍ** | منجز | Starter 100 / Pro 1000 / Business 5000 — إعادة ضبط منتصف الليل UTC |
| **نافذة وصول شهرية** | منجز | `access_until` — بعد الانتهاء `403 subscription_expired` حتى التجديد |
| **تجديد بعد الدفع** | منجز | **+1 mois** / **Renouveler** → `POST /admin/partners/:id/renew` |
| **مفتاح اختبار منفصل** | منجز | `sk_live_` للإنتاج + `sk_test_` للتطوير (خارج الحصة والإحصاءات) |
| إعادة توليد المفتاح | منجز | **Régénérer la clé** — المفتاح القديم يموت فوراً |
| واجهة تسجيل الشركات | منجز | نموذج الإنشاء في **Comptes** (الأدمن ينشئ، الشركة لا تسجّل وحدها) — مدة 7ج / 30ج / 90ج / 365ج |
| فصل مفتاح المدير | منجز | `X-Admin-Key` للإدارة ≠ `X-Api-Key` للشريك |
| PDF خاص بكل شركة | منجز | يختلف لأن المفتاح والخطة والقنوات تختلف (`sk_live_` + `sk_test_`) |
| بحث + تفاصيل + تعديل + صفحات | منجز | الجدول في Comptes |
| مراقبة الأرصدة والتنبيهات | منجز | Tableau de bord → **Solde par société** + **Sociétés à renouveler** |
| دليل صوتي حسب القسم | منجز | زر **Écouter** |
| تشغيل مختبر بضغطة | منجز | `voice-otp/run-server.bat` → Flask Waitress :5000 + Nuxt :3000 |

هذا **حقيقي** بمعنى: شركة خارجية تستدعي HTTP بمفتاح؛ إن أُلغي الحساب أو انتهت المدة أو حُذف الحساب يتوقف فوراً؛ المفتاح يُعرض مرة واحدة ويُحفظ مشفّراً (SHA-256).

هذا **ليس** بيعاً تجارياً جاهزاً (انظر القسم 2).

---

## 2. هل التطبيق جاهز للإنتاج؟

**لا. جاهز لمناقشة الأستاذ والمختبر المحلي. غير جاهز للإنتاج ولا للبيع كخدمة عامة.**

| نقطة | المختبر الحالي | الإنتاج الحقيقي يحتاج |
|---|---|---|
| العنوان | `http://127.0.0.1:5000` | VPS + **HTTPS** |
| مفتاح الأدمن | في `.env` (`ADMIN_API_KEY`) | سر قوي مختلف عن المختبر |
| Flask | `serve_prod.py` = **Waitress** على Windows (`FLASK_DEBUG=0`) | gunicorn/uwsgi خلف nginx على Linux/AWS |
| الصوت | `VOICE_PROVIDER=lab` → امتداد SIP **1000** (Linphone على LAN) | جذع SIP / رقم DID أمريكي (`VOICE_PROVIDER=trunk`) بعد KYC المزوّد |
| SMS | ChinqIT (مدفوع، مفتاح في `.env`) | حساب إنتاج + رصيد + مراقبة |
| البريد | Gmail SMTP (حجم مختبر) | مزوّد معاملات (لا Gmail الحر) |
| CORS | `*` مسموح في المختبر | أصول محددة فقط |
| الأسرار | `.env` محلي | غير مُلتزم في Git، تدوير المفاتيح |
| القاعدة | SQLite ملف محلي | نسخ احتياطي؛ لاحقاً Postgres إن لزم |
| Redis | إن وُجد؛ وإلا ذاكرة محلية | Redis إلزامي لعدة عمال |
| المراقبة | لوحة Nuxt محلية (حصص + انتهاء الوصول) | سجلات، تنبيهات، نسخ احتياطي |

**جملة واحدة للأستاذ:**  
*Solution de laboratoire intégrable par API, conception contrôlée par compte (quota journalier, fenêtre d’accès, révocation et suppression). Pas encore un service commercial (HTTPS, SIP trunk vérifié, secrets, debug off).*

---

## 3. ماذا فعلنا (سجل العمل)

### 3.1 المنتج: Web Service وليس الشاشات الأربع

- Flask يعرّض كتالوج الآلة: `GET /v1` و `GET /v1/formula`.
- أربع عمليات فقط للشريك: إرسال صوت / SMS / بريد + تحقق واحد.
- التطبيق React (4 شاشات، المنفذ 5173) بقي **مختبراً محلياً**؛ لم يُطلب من الشركات تثبيته.
- صفحات HTML القديمة (`/v1/accounts`, `/v1/docs`, embed) أُزيلت؛ الإدارة صارت **Nuxt**.

### 3.2 الحسابات (conception sous forme de compte)

- جدول SQLite `partner_accounts`.
- خطط **دائمة حتى يلغيها أو يحذفها الأدمن**:
  - **starter** — SMS + e-mail، 100/يوم
  - **pro** — 3 قنوات، 1000/يوم
  - **business** — 3 قنوات، 5000/يوم
- المفتاح `sk_live_…` يُولَّد مرة، يُعرض مرة، يُخزَّن **hash SHA-256** فقط.
- حصص يومية، رفض القناة خارج الخطة (`403 channel_not_in_plan`).
- Rate limit: `20 per 5 minutes` بمفتاح الشركة.
- OTP: 6 أرقام CSPRNG، HMAC في Redis، TTL 180 ثا، 3 محاولات تحقق، استخدام واحد.

### 3.3 لوحة الأدمن Nuxt (`http://localhost:3000`)

القائمة:

- Tableau de bord — KPI OTP، **Solde par société**، **Sociétés à renouveler**.
- **Comptes** — إنشاء (خطة + مدة وصول)، بحث، تفاصيل، تعديل، تعطيل/تفعيل، **حذف**، تجديد شهر، PDF، إحصائيات، صفحات.
- Formule APIs — عقد الـ 4 endpoints بالفرنسية.
- Widget — اختبار القنوات الثلاث بـ **`sk_test_` فقط** (لا يلمس حصة الإنتاج).
- Journaux · AI Control Center · Outils.

التصميم: ثيم ورقي (كريم / رمل / مرجان / أخضر Sage)، لغة الواجهة **fr**.

بعد أي تعديل Vue: **`npm run build` ثم `npm start`** في `d:\dashbord-admin`. `nuxt dev` ليس مسار التشغيل الحالي؛ الواجهة القديمة تبقى إن نُسي البناء.

### 3.4 أمان الأدمن مقابل الشريك

- الشريك: رأس `X-Api-Key` (`sk_live_` أو `sk_test_`).
- الأدمن: رأس `X-Admin-Key` على الخادم Nuxt فقط (`NUXT_ADMIN_API_KEY`)؛ لا يُرسل للمتصفح كسرّ عام.
- وكيل Nitro: المتصفح → `/api/admin/...` → Flask `/admin/...`.

### 3.5 PDF لكل شركة

- زر PDF يولّد ملفاً ملوّناً: الهوية، الخطة، **مفتاح هذه الشركة** (`sk_live_` + `sk_test_`)، الـ curl، الأخطاء.
- كل شركة ملف مختلف بسبب المفتاح.

### 3.6 إحصائيات لكل شركة

- الأحداث تُسجَّل مع `partner_id` (الطلبات **الجديدة** فقط).
- عمود `otp_events.is_test`: أحداث `sk_test_` **لا تدخل** منحنيات الإنتاج ولا الحصة.
- صفحة `/accounts/:id`: حجم، نجاح، قنوات، منحنى 7/14/30 يوماً.

### 3.7 تدوير المفتاح وتعطيل فوري

- **Désactiver** → الحالة `revoked` → أي استدعاء لاحق `403 account_revoked`.
- **Régénérer la clé** → الهاش القديم يُستبدل (`sk_live_` و `sk_test_`)؛ المفتاح الجديد مرة واحدة + PDF جديد.

### 3.8 واجهة الجدول

- بحث فوق الجدول.
- **Détail** نافذة وسط الشاشة.
- **Modifier** (اسم، بريد، خطة — المفتاح لا يتغيّر إلا بالتدوير).
- ترقيم صفحات (8 / 12 / 24).
- أعمدة **Reste** (الحصة المتبقية اليوم) و **Accès** (تاريخ نهاية النافذة).

### 3.9 زر Écouter

- يشرح **القسم الحالي** (لوحة، حسابات، صيغة API، ودجت، سجلات، AI، أدوات).
- يتوقف عند تغيير الصفحة.

### 3.10 مفتاحان لكل شركة: إنتاج + اختبار

هذا جزء أساسي من نموذج الحساب، وليس تجميلاً.

| | `sk_live_…` | `sk_test_…` |
|---|---|---|
| الاستخدام | إنتاج الشركة | تطوير / Widget / مختبر |
| الحصة اليومية | تُحسب وتُستهلك | **لا تُستهلك** |
| إحصاءات اللوحة | نعم | تُستبعد (`is_test=1`) |
| إرسال OTP حقيقي | نعم | نعم (الصوت/SMS/البريد يخرج فعلاً) |
| نافذة الوصول `access_until` | تُفرض | تُفرض أيضاً (`access_ok`) |
| التعطيل / الحذف | يوقف الاثنين | يوقف الاثنين |

عند الإنشاء يُعرض المفتاحان **مرة واحدة**. بعد ذلك يظهر فقط البادئة (`key_prefix` / `test_key_prefix`).

### 3.11 الحصة اليومية ومراقبة الرصيد

- الحقلان `used_today` + `used_on`. عند تغيّر اليوم (UTC) العداد يعود إلى 0 دون تدخل.
- لكل شركة: `remaining_today`، `remaining_pct`، `quota_state`:
  - `ok` — متبقٍ > 20٪
  - `low` — متبقٍ ≤ 20٪
  - `empty` — 0 متبقٍ → الإرسال الحي `429 quota_exceeded`
  - `revoked` — الحساب معطّل
- API: `GET /admin/partners/balances` وأيضاً داخل `GET /admin/stats/dashboard` كـ `partner_balances`.
- اللوحة: جدول **Solde par société** + عمود **Reste** في Comptes.

### 3.12 نافذة الوصول الشهرية (abonnement)

الخطة **لا تنتهي وحدها**. ما ينتهي هو **حق الاستدعاء الحي** لمدة ممنوحة عند الإنشاء (افتراضي 30 يوماً).

- أعمدة: `access_started_at`، `access_until`.
- عند الإنشاء يختار الأدمن: **7 أيام / 30 يوماً / 90 يوماً / 365 يوماً**.
- الحسابات القديمة أُعيد ملؤها بـ **اليوم + 30** حتى لا تُقطع فجأة.
- `access_state`: `ok` · `expiring` (≤ 7 أيام) · `expired` · `revoked`.
- إن انتهت المدة: أي `/v1/otp/...` → `403 subscription_expired` (حتى بمفتاح `sk_test_`).
- **Renouveler / +1 mois**: يكدّس +N يوماً من تاريخ النهاية الحالي، أو من اليوم إن كان منتهياً. يعيد الحالة `active`.
- التنبيه الأحمر **Sociétés à renouveler** يظهر **فقط** إذا وُجدت شركات `expiring` أو `expired` — لا يظهر إن بقي للجميع نحو 30 يوماً.

```
[شركة] --sk_live_--> require_partner
                         |-- مفتاح خاطئ        → 401 invalid_api_key
                         |-- Désactiver        → 403 account_revoked
                         |-- access_until فائت → 403 subscription_expired
                         |-- قناة خارج الخطة   → 403 channel_not_in_plan
                         |-- حصة اليوم = 0     → 429 quota_exceeded
                         |-- 20 طلب / 5 دقائق  → 429
                         \-- وإلا              → إرسال OTP
```

### 3.13 حذف الشركة

- **Supprimer** في كل صف (Comptes)، وفي نافذة التفاصيل، وفي صفحة `/accounts/:id`.
- تأكيد عبر `ConfirmDialog` قبل التنفيذ.
- `POST /admin/partners/:id/delete` أو `DELETE /admin/partners/:id`.
- يُمسح صف `partner_accounts` → المفاتيح تموت فوراً.
- سجلات `otp_events` **تبقى** (أثر تاريخي). المفاتيح المحفوظة محلياً في المتصفح تُنسى (`forgetPartnerKeys`).
- **Désactiver** = إيقاف مؤقت (يمكن Réactiver). **Supprimer** = نهائي.

### 3.14 الصوت: مختبر Linphone أو جذع SIP

- `VOICE_PROVIDER=lab` (الافتراضي): الوجهة = امتداد `1000` (Linphone على LAN).
- `VOICE_PROVIDER=trunk`: الوجهة = رقم الجوال في الطلب (`phoneNumber`)، عبر Asterisk + جذع (Telnyx). يتطلب رقم Caller ID أمريكي (`SIP_TRUNK_CALLER_ID`) بعد KYC المزوّد. بدون رقم `+1` مُشترى، هذا المسار غير جاهز للبيع.

### 3.15 تشغيل الإنتاج المحلي

- `python serve_prod.py` — Waitress على Windows، gunicorn على Linux.
- `run-server.bat` يشغّل API :5000 ولوحة :3000 ويفتح المتصفح.
- `FLASK_SECRET_KEY` و `ADMIN_API_KEY` إلزاميان في `backend/.env`.

### 3.16 ما لم يُكسر عمداً

- مسار توليد/تحقق OTP الأساسي لم يُغيَّر إلا بإضافة الحسابات والحصص ونافذة الوصول و`partner_id` و`is_test`.
- التطبيق React المخبري بقي للعرض المحلي (`/auth/...`).
- الذكاء الاصطناعي لا يرى الرمز ولا الأرقام الكاملة.

---

## 4. كيف تستفيد أي خدمة أخرى منه

### الفكرة

الخدمة الأخرى **لا تثبّت VoiceOTP**.  
هي تطبيق بنك / دفع / دخول: تستدعي 2 إلى 4 طلبات HTTP بمفتاحها.

```
[تطبيق الشركة]  --X-Api-Key-->  [VoiceOTP Gateway :5000/v1]
                                      |-- صوت (ext 1000 في المختبر / جذع إن trunk)
                                      |-- SMS (ChinqIT)
                                      |-- E-mail (SMTP)
```

الأدمن عندكم ينشئ الحساب ويعطي الشركة **PDF + المفتاحين**. الشركة لا تدخل لوحة Nuxt.

### الخطوات للشركة الشريكة

1. تستلم `sk_live_…` و `sk_test_…` (مرة واحدة) والـ PDF.
2. تخزّن `sk_live_` في **خادم الإنتاج** و `sk_test_` في بيئة التطوير (ليس في تطبيق جوّال عام).
3. عند حاجة OTP:
   - `POST` قناة واحدة مع `userId` ثابت لنفس العملية.
   - المستخدم يدخل الرمز.
   - `POST /v1/otp/verify` بنفس `userId`.
4. إذا `ok: true` تكمل الدفع/الدخول؛ وإلا ترفض.
5. إن رجع `subscription_expired`: تتوقف حتى يجدّد الأدمن بعد الدفع.

### العناوين (مختبر)

القاعدة: `http://127.0.0.1:5000`

| العملية | الطريقة | المسار | الجسم |
|---|---|---|---|
| كتالوج | GET | `/v1` | — |
| صوت | POST | `/v1/otp/voice` | `{"userId":"pay-001"}` (مختبر) أو + `"phoneNumber":"+222…"` إن trunk |
| SMS | POST | `/v1/otp/sms` | `{"userId":"pay-001","phoneNumber":"+222…"}` |
| بريد | POST | `/v1/otp/email` | `{"userId":"pay-001","email":"…"}` |
| تحقق (كل القنوات) | POST | `/v1/otp/verify` | `{"userId":"pay-001","otp":"123456"}` |

رؤوس إلزامية:

```
Content-Type: application/json
X-Api-Key: sk_live_xxxxxxxx
```

### مثال curl (غيّر المفتاح)

```bash
curl -X POST http://127.0.0.1:5000/v1/otp/sms \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: VOTRE_CLE" \
  -d "{\"userId\":\"pay-001\",\"phoneNumber\":\"+222XXXXXXXX\"}"

curl -X POST http://127.0.0.1:5000/v1/otp/verify \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: VOTRE_CLE" \
  -d "{\"userId\":\"pay-001\",\"otp\":\"123456\"}"
```

### النجاح

- إرسال: `{"status":"sent","channel":"sms","expiresIn":180}` — **الرمز لا يُرجع في JSON**.
- تحقق: `{"ok":true,"channel":"sms"}`.

### الأخطاء التي يجب أن تعالجها الخدمة الأخرى

| رمز | `detail` | المعنى |
|---|---|---|
| 401 | `invalid_api_key` | مفتاح خاطئ أو PDF شركة أخرى |
| 403 | `account_revoked` | الأدمن عطّل الحساب |
| 403 | `subscription_expired` | نافذة الوصول انتهت — يلزم تجديد |
| 403 | `channel_not_in_plan` | قناة ليست في الخطة (مثلاً صوت على Starter) |
| 429 | `quota_exceeded` | استنفدت الحصة اليومية (live فقط) |
| 429 | — | 20 طلب/5 دقائق أو 3 تحققات فاشلة |
| 400 | — | رمز خاطئ / منتهٍ / ناقص |
| 502 | — | القناة غير متاحة (SMS / SMTP / صوت) |

### قواعد أمان للشريك

- نفس `userId` عند الإرسال والتحقق.
- لا تضع `X-Api-Key` في تطبيق جوّال عام.
- لا تستخدم أبداً `X-Admin-Key` (خاص بلوحتكم).
- TTL 180 ثانية، 3 محاولات، الرمز لمرة واحدة.
- `sk_test_` للتطوير فقط؛ الإنتاج بـ `sk_live_`.

### من يفعل ماذا

| أنتم (صاحب VoiceOTP) | الشركة الشريكة |
|---|---|
| إنشاء الحساب في `/accounts` (خطة + مدة) | استدعاء `/v1/...` فقط |
| اختيار الخطة والحصص | تخزين المفتاح في خادمها |
| PDF + المفتاحان | لا تدخل لوحة الأدمن |
| تجديد الشهر بعد الدفع | تتوقف تلقائياً إن انتهى الشهر |
| تعطيل / تدوير / **حذف** | تحديث المفتاح إن دُوِّر |
| تشغيل Flask + Redis + (اختياري) Linphone | لا Docker إجباري عندها |

### اختبار سريع بدون كود الشركة

لوحة الأدمن → **Widget** → يُستخدم تلقائياً `sk_test_` للشركة المختارة → تجربة صوت / SMS / بريد دون استهلاك الحصة.

---

## 5. كيف تشغّل المختبر (أمام الأستاذ)

الطريقة الموصى بها — ملف واحد:

```
d:\voice-otpbackendotp\voice-otp\run-server.bat
```

يفتح:

1. **Flask (Waitress)** — `python serve_prod.py` → `http://127.0.0.1:5000`
2. **Nuxt admin (بناء إنتاج)** — `npm start` في `d:\dashbord-admin` → `http://localhost:3000`
3. المتصفح على لوحة الأدمن.

يدوياً:

```cmd
cd d:\voice-otpbackendotp\voice-otp\backend
python serve_prod.py
```

```cmd
cd d:\dashbord-admin
npm run build
npm start
```

اختياري أمام الأستاذ: React المخبري `voice-otp/frontend` → المنفذ `5173` (الشاشات الأربع، مسارات `/auth/...` وليست عقد الشريك `/v1`).

إيقاف Flask **لا يوقف** Nuxt: الواجهة تبقى وتعرض بيانات قديمة حتى **Actualiser**.  
سجلات Flask تظهر فقط عند طلب **جديد** يصل إلى المنفذ 5000.

بعد تعديل واجهة Vue: أعد `npm run build` ثم `npm start`، ثم **Ctrl+F5** في المتصفح.

متغيرات مهمة (`backend/.env` + `dashbord-admin/.env`):

- `ADMIN_API_KEY` (Flask) و `NUXT_ADMIN_API_KEY` (Nuxt) — نفس القيمة.
- `FLASK_SECRET_KEY` إلزامي.
- `FLASK_DEBUG=0` قبل أي نشر.
- `VOICE_PROVIDER=lab` للمختبر (Linphone 1000).
- لا تلتزم ملفات `.env` ولا مفاتيح ChinqIT/SMTP/Telnyx في Git.

---

## 6. خريطة الملفات المهمة (بعد التعديلات)

```text
voice-otp/backend/
  app.py                 نقطة Flask (blueprints)
  serve_prod.py          Waitress / gunicorn
  partners.py            الحسابات، الحصص، الوصول، الحذف، الأرصدة
  product_config.py      VOICE_PROVIDER, CORS, debug
  routes/v1.py           عقد الشريك + require_partner / quota / access
  routes/admin.py        CRUD شركاء + renew + delete + balances
  otp/partner_flow.py    إرسال/تحقق مع تمييز live/test
  db.py                  otp_events.partner_id + is_test

dashbord-admin/
  pages/index.vue        KPI + Solde + Sociétés à renouveler
  pages/accounts/index.vue  جدول، إنشاء، Reste، Accès، Supprimer
  pages/accounts/[id].vue   تفاصيل، تجديد، حذف
  pages/widget/index.vue    اختبار بـ sk_test_ فقط
  composables/useAdminApi.ts
  utils/partnerKitPdf.ts
```

---

## 7. جملة ختامية جاهزة للأستاذ

*Le produit n’est pas les 4 écrans : c’est une passerelle HTTP. Chaque système externe a un compte, deux clés (sk_live_ / sk_test_), un plan, un quota journalier, une fenêtre d’accès renouvelable, une révocation et une suppression. L’admin (Nuxt) crée le compte, surveille le solde, renouvelle après paiement, et envoie un PDF. Le partenaire n’appelle que `/v1`. C’est une solution de laboratoire contrôlée ; la production exige HTTPS, un trunk SIP vérifié pour la voix mobile, et des secrets hors développement.*
