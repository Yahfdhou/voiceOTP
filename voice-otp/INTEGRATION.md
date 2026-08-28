# VoiceOTP Gateway — Web Service

L’interface admin est le **dashboard Nuxt** (`http://localhost:3000`) :

- `/accounts` — comptes partenaires (admin)
- `/integration` — formule des APIs (français)
- `/widget` — test des 4 canaux

Les pages HTML `/v1/docs` et `/v1/accounts` ont été retirées. Le contrat machine reste :

- `GET http://127.0.0.1:5000/v1`
- `GET http://127.0.0.1:5000/v1/formula`

Auth partenaire : header `X-Api-Key`  
Auth admin dashboard : `X-Admin-Key` (Nitro, jamais dans le navigateur)

| Canal | POST | Body |
|---|---|---|
| Voix | `/v1/otp/voice` | `{"userId":"pay-001","phoneNumber":"+222...","voiceMode":"live"}` |
| SMS | `/v1/otp/sms` | `{"userId":"pay-001","phoneNumber":"+222..."}` |
| WhatsApp | `/v1/otp/whatsapp` | `{"userId":"pay-001","phoneNumber":"+222..."}` |
| E-mail | `/v1/otp/email` | `{"userId":"pay-001","email":"..."}` |
| Vérifier | `/v1/otp/verify` | `{"userId":"pay-001","otp":"123456"}` |
